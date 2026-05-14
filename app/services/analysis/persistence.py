"""
Persist a GameAnalysis into the database.

Public entry point: persist_game_analysis()
  Walks the GameAnalysis Pydantic model and writes all ORM rows in a single
  transaction. Caller is responsible for committing.

Requires a pre-built name→card_id lookup (built by pipeline._resolve_all_card_names
before calling this function).
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board_state import BoardState
from app.models.game import Game
from app.models.notable_moment import NotableMoment
from app.models.player import Player
from app.models.turn import Turn
from app.models.turn_action import TurnAction
from app.models.turn_card import TurnCard
from app.models.zone_card import ZoneCard
from app.models.zone_card_counter import ZoneCardCounter
from app.schemas.analysis import (
    CardInteraction as CardInteractionSchema,
    GameAnalysis,
    NotableMoment as NotableMomentSchema,
    PlayerData,
    TurnAction as TurnActionSchema,
    TurnData,
    ZoneSnapshot,
)

logger = logging.getLogger(__name__)


# ── Public entry point ────────────────────────────────────────────────────────


async def persist_game_analysis(
    game_id: int,
    analysis: GameAnalysis,
    name_to_card_id: dict[str, int],
    db: AsyncSession,
) -> None:
    """
    Write all ORM rows for a completed GameAnalysis. Caller must commit.

    name_to_card_id maps raw card name strings (as emitted by Claude)
    to cards.id values resolved via card_names.resolve().
    """
    await _update_game_fields(game_id, analysis, db)

    player_map = await _persist_players(game_id, analysis.players, db)

    for turn_data in analysis.turns:
        await _persist_turn(game_id, turn_data, player_map, name_to_card_id, db)

    _persist_notable_moments(game_id, analysis.notable_moments, db)

    await db.flush()
    logger.info("Persisted game analysis for game_id=%d", game_id)


# ── Game fields ───────────────────────────────────────────────────────────────


async def _update_game_fields(
    game_id: int,
    analysis: GameAnalysis,
    db: AsyncSession,
) -> None:
    result = await db.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one()
    game.total_turns = analysis.total_turns
    game.summary = analysis.summary


# ── Players ───────────────────────────────────────────────────────────────────


async def _persist_players(
    game_id: int,
    players_data: list[PlayerData],
    db: AsyncSession,
) -> dict[str, Player]:
    """Insert all players and return a name→Player map for FK lookups."""
    player_map: dict[str, Player] = {}
    for p in players_data:
        player = Player(
            game_id=game_id,
            name=p.name,
            commander_name=p.commander_name,
            is_winner=p.is_winner,
            seat_order=p.seat_order,
        )
        db.add(player)
        player_map[p.name] = player
    await db.flush()  # populate player.id before turns reference them
    return player_map


# ── Turns ─────────────────────────────────────────────────────────────────────


async def _persist_turn(
    game_id: int,
    turn_data: TurnData,
    player_map: dict[str, Player],
    name_to_card_id: dict[str, int],
    db: AsyncSession,
) -> None:
    """Insert one turn and all its child rows."""
    active_player = player_map.get(turn_data.active_player)
    if active_player is None:
        logger.warning(
            "Unknown active player '%s' on turn %d — skipping turn",
            turn_data.active_player,
            turn_data.turn_number,
        )
        return

    turn = Turn(
        game_id=game_id,
        active_player_id=active_player.id,
        turn_number=turn_data.turn_number,
    )
    db.add(turn)
    await db.flush()  # populate turn.id before children reference it

    _persist_actions(turn.id, turn_data.actions, db)
    _persist_card_interactions(turn.id, turn_data.card_interactions, player_map, name_to_card_id, db)
    _persist_board_states(turn.id, turn_data, player_map, db)
    await _persist_zone_snapshots(turn.id, turn_data.zone_snapshots, player_map, name_to_card_id, db)


# ── Turn children ─────────────────────────────────────────────────────────────


def _persist_actions(
    turn_id: int,
    actions: list[TurnActionSchema],
    db: AsyncSession,
) -> None:
    for action in actions:
        db.add(TurnAction(
            turn_id=turn_id,
            phase=action.phase,
            description=action.description,
            order_index=action.order_index,
        ))


def _persist_card_interactions(
    turn_id: int,
    interactions: list[CardInteractionSchema],
    player_map: dict[str, Player],
    name_to_card_id: dict[str, int],
    db: AsyncSession,
) -> None:
    for interaction in interactions:
        card_id = name_to_card_id.get(interaction.card_name)
        if card_id is None:
            logger.warning("No card_id for '%s' — skipping interaction", interaction.card_name)
            continue
        player = player_map.get(interaction.player)
        if player is None:
            logger.warning("Unknown player '%s' in interaction — skipping", interaction.player)
            continue
        db.add(TurnCard(
            turn_id=turn_id,
            player_id=player.id,
            card_id=card_id,
            action_type=interaction.action_type,
            phase=interaction.phase,
            target=interaction.target,
        ))


def _persist_board_states(
    turn_id: int,
    turn_data: TurnData,
    player_map: dict[str, Player],
    db: AsyncSession,
) -> None:
    all_player_names = (
        set(turn_data.life_totals)
        | set(turn_data.poison_counters)
        | set(turn_data.energy_counters)
    )
    for player_name in all_player_names:
        player = player_map.get(player_name)
        if player is None:
            continue
        db.add(BoardState(
            player_id=player.id,
            turn_id=turn_id,
            life_total=turn_data.life_totals.get(player_name),
            poison_counters=turn_data.poison_counters.get(player_name, 0),
            energy_counters=turn_data.energy_counters.get(player_name, 0),
        ))


async def _persist_zone_snapshots(
    turn_id: int,
    snapshots: list[ZoneSnapshot],
    player_map: dict[str, Player],
    name_to_card_id: dict[str, int],
    db: AsyncSession,
) -> None:
    for snapshot in snapshots:
        player = player_map.get(snapshot.player)
        if player is None:
            logger.warning("Unknown player '%s' in zone snapshot — skipping", snapshot.player)
            continue
        for zc_data in snapshot.cards:
            await _persist_zone_card(turn_id, snapshot.zone, zc_data, player, name_to_card_id, db)


async def _persist_zone_card(
    turn_id: int,
    zone: str,
    zc_data,
    player: Player,
    name_to_card_id: dict[str, int],
    db: AsyncSession,
) -> None:
    card_id = name_to_card_id.get(zc_data.card_name)
    if card_id is None:
        logger.warning("No card_id for '%s' in zone snapshot — skipping", zc_data.card_name)
        return
    zone_card = ZoneCard(
        player_id=player.id,
        turn_id=turn_id,
        card_id=card_id,
        zone=zone,
        is_tapped=zc_data.is_tapped,
        effective_power=zc_data.effective_power,
        effective_toughness=zc_data.effective_toughness,
    )
    db.add(zone_card)
    await db.flush()  # need zone_card.id for counters

    for counter_data in zc_data.counters:
        db.add(ZoneCardCounter(
            zone_card_id=zone_card.id,
            counter_type=counter_data.counter_type,
            count=counter_data.count,
        ))


# ── Notable moments ───────────────────────────────────────────────────────────


def _persist_notable_moments(
    game_id: int,
    moments: list[NotableMomentSchema],
    db: AsyncSession,
) -> None:
    for moment in moments:
        db.add(NotableMoment(
            game_id=game_id,
            turn_number=moment.turn_number,
            description=moment.description,
            order_index=moment.order_index,
        ))
