"""
Pipeline orchestrator: YouTube → Claude → card resolution → DB persistence.

Coordinates all external service calls for a game analysis and writes the
result to the database. Called from the background task in routers/games.py
so that the router itself only handles HTTP concerns.
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.game import Game
from app.schemas.analysis import GameAnalysis
from app.services.analysis import claude, persistence
from app.services.cards.names import resolve as resolve_card_name
from app.services.youtube.apify import get_youtube_transcript

logger = logging.getLogger(__name__)


# ── Public entry point ────────────────────────────────────────────────────────


async def run_analysis(game_id: int, source_url: str) -> None:
    """
    Full pipeline: YouTube → Claude → card resolution → DB persistence.

    Updates game.status at each milestone so pollers see progress in real time.
    On any unhandled exception: sets status='failed' and stores the message.
    """
    try:
        await _set_status(game_id, "processing")

        transcript = await get_youtube_transcript(source_url)
        await _update_game_metadata(
            game_id,
            title=transcript.title,
            duration_seconds=transcript.duration_seconds,
        )

        analysis = await claude.run_pipeline(
            segments=transcript.transcript_segments,
            title=transcript.title,
            duration_seconds=transcript.duration_seconds,
        )

        name_to_card_id = await _resolve_all_card_names(analysis)

        async with AsyncSessionLocal() as db:
            await persistence.persist_game_analysis(game_id, analysis, name_to_card_id, db)
            await _mark_complete(game_id, db)
            await db.commit()

        logger.info("Game %d analysis complete", game_id)

    except Exception as exc:
        logger.exception("Game %d analysis failed", game_id)
        await _set_status(game_id, "failed", error_message=repr(exc)[:1000])


# ── Status helpers ─────────────────────────────────────────────────────────────


async def _set_status(game_id: int, status: str, **extra_fields) -> None:
    """Open a short-lived session to update game.status (plus any extra fields)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Game).where(Game.id == game_id))
        game = result.scalar_one()
        game.status = status
        for field, value in extra_fields.items():
            setattr(game, field, value)
        await db.commit()


async def _update_game_metadata(
    game_id: int,
    title: str | None,
    duration_seconds: int | None,
) -> None:
    """Patch title and duration_seconds after the transcript has been fetched."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Game).where(Game.id == game_id))
        game = result.scalar_one()
        game.title = title
        game.duration_seconds = duration_seconds
        await db.commit()


async def _mark_complete(game_id: int, db: AsyncSession) -> None:
    """Set status='complete' within an already-open session (no commit)."""
    result = await db.execute(select(Game).where(Game.id == game_id))
    game = result.scalar_one()
    game.status = "complete"


# ── Card name resolution ───────────────────────────────────────────────────────


def _collect_card_names(analysis: GameAnalysis) -> set[str]:
    """Return every card name referenced anywhere in the analysis."""
    names: set[str] = set()
    for turn in analysis.turns:
        for interaction in turn.card_interactions:
            names.add(interaction.card_name)
        for snapshot in turn.zone_snapshots:
            for zone_card in snapshot.cards:
                names.add(zone_card.card_name)
    return names


async def _resolve_all_card_names(analysis: GameAnalysis) -> dict[str, int]:
    """Resolve every card name in the analysis to a cards.id in one session."""
    names = _collect_card_names(analysis)
    async with AsyncSessionLocal() as db:
        name_to_card_id: dict[str, int] = {}
        for name in names:
            name_to_card_id[name] = await resolve_card_name(name, db)
        await db.commit()
    return name_to_card_id
