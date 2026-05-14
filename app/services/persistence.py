"""
Persist a GameAnalysis into the database.

Walks the GameAnalysis Pydantic model and writes all ORM rows
in a single transaction. Requires a pre-built name→card_id lookup
(built by card_names.resolve() before calling this function).
"""
import logging

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
from app.schemas.analysis import GameAnalysis

logger = logging.getLogger(__name__)


async def persist_game_analysis(
    game_id: int,
    analysis: GameAnalysis,
    name_to_card_id: dict[str, int],
    db: AsyncSession,
) -> None:
    """
    Write all ORM rows for a completed GameAnalysis.
    All inserts happen in one transaction — caller must commit.

    name_to_card_id maps raw card name strings (as emitted by Claude)
    to cards.id values resolved via card_names.resolve().
    """
    # 1. Update top-level game fields
    from sqlalchemy import select
    result = await db.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one()
    game.total_turns = analysis.total_turns
    game.summary = analysis.summary

    # 2. Players — indexed by name for turn lookups
    player_map: dict[str, Player] = {}
    for p_data in analysis.players:
        player = Player(
            game_id=game_id,
            name=p_data.name,
            commander_name=p_data.commander_name,
            is_winner=p_data.is_winner,
            seat_order=p_data.seat_order,
        )
        db.add(player)
        player_map[p_data.name] = player

    await db.flush()  # get player ids

    # 3. Turns
    for turn_data in analysis.turns:
        active_player = player_map.get(turn_data.active_player)
        if active_player is None:
            logger.warning("Unknown active player '%s' on turn %d — skipping turn",
                           turn_data.active_player, turn_data.turn_number)
            continue

        turn = Turn(
            game_id=game_id,
            active_player_id=active_player.id,
            turn_number=turn_data.turn_number,
        )
        db.add(turn)
        await db.flush()  # get turn.id

        # 3a. Actions
        for action in turn_data.actions:
            db.add(TurnAction(
                turn_id=turn.id,
                phase=action.phase,
                description=action.description,
                order_index=action.order_index,
            ))

        # 3b. Card interactions
        for interaction in turn_data.card_interactions:
            card_id = name_to_card_id.get(interaction.card_name)
            if card_id is None:
                logger.warning("No card_id for '%s' — skipping interaction", interaction.card_name)
                continue
            player = player_map.get(interaction.player)
            if player is None:
                logger.warning("Unknown player '%s' in interaction — skipping", interaction.player)
                continue
            db.add(TurnCard(
                turn_id=turn.id,
                player_id=player.id,
                card_id=card_id,
                action_type=interaction.action_type,
                phase=interaction.phase,
                target=interaction.target,
            ))

        # 3c. Board states (life totals, poison, energy)
        all_players = set(turn_data.life_totals) | set(turn_data.poison_counters) | set(turn_data.energy_counters)
        for player_name in all_players:
            player = player_map.get(player_name)
            if player is None:
                continue
            db.add(BoardState(
                player_id=player.id,
                turn_id=turn.id,
                life_total=turn_data.life_totals.get(player_name),
                poison_counters=turn_data.poison_counters.get(player_name, 0),
                energy_counters=turn_data.energy_counters.get(player_name, 0),
            ))

        # 3d. Zone snapshots
        for snapshot in turn_data.zone_snapshots:
            player = player_map.get(snapshot.player)
            if player is None:
                logger.warning("Unknown player '%s' in zone snapshot — skipping", snapshot.player)
                continue
            for zc_data in snapshot.cards:
                card_id = name_to_card_id.get(zc_data.card_name)
                if card_id is None:
                    logger.warning("No card_id for '%s' in zone snapshot — skipping", zc_data.card_name)
                    continue
                zone_card = ZoneCard(
                    player_id=player.id,
                    turn_id=turn.id,
                    card_id=card_id,
                    zone=snapshot.zone,
                    is_tapped=zc_data.is_tapped,
                    effective_power=zc_data.effective_power,
                    effective_toughness=zc_data.effective_toughness,
                )
                db.add(zone_card)
                await db.flush()

                for counter_data in zc_data.counters:
                    db.add(ZoneCardCounter(
                        zone_card_id=zone_card.id,
                        counter_type=counter_data.counter_type,
                        count=counter_data.count,
                    ))

    # 4. Notable moments
    for moment_data in analysis.notable_moments:
        db.add(NotableMoment(
            game_id=game_id,
            turn_number=moment_data.turn_number,
            description=moment_data.description,
            order_index=moment_data.order_index,
        ))

    await db.flush()
    logger.info("Persisted game analysis for game_id=%d", game_id)
