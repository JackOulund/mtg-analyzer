import logging
import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal, get_db
from app.models.game import Game
from app.models.player import Player
from app.models.turn import Turn
from app.models.turn_action import TurnAction
from app.models.turn_card import TurnCard
from app.models.notable_moment import NotableMoment
from app.schemas.game import GameCreate, GameListItem, GameResponse
from app.services import apify, claude, card_names, persistence

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/games", tags=["games"])


def _extract_video_id(url: str) -> str | None:
    match = re.search(r"(?:v=|youtu\.be/|/embed/|/v/)([A-Za-z0-9_-]{11})", url)
    return match.group(1) if match else None


def _full_game_query(game_id: int):
    return (
        select(Game)
        .where(Game.id == game_id)
        .options(
            selectinload(Game.players),
            selectinload(Game.notable_moments),
            selectinload(Game.turns).selectinload(Turn.actions),
            selectinload(Game.turns).selectinload(Turn.turn_cards),
        )
    )


async def _analyze_game(game_id: int, source_url: str) -> None:
    """
    Background task: runs the full Apify → Claude pipeline and persists results.
    All external calls happen here — POST /games only creates the queued row.
    """
    async with AsyncSessionLocal() as db:
        # Mark as processing
        result = await db.execute(select(Game).where(Game.id == game_id))
        game = result.scalar_one()
        game.status = "processing"
        await db.commit()

        try:
            # Step 1: fetch transcript from Apify
            transcript = await apify.get_youtube_transcript(source_url)

            # Step 2: update game metadata from transcript
            async with AsyncSessionLocal() as db2:
                result2 = await db2.execute(select(Game).where(Game.id == game_id))
                g = result2.scalar_one()
                g.title = transcript.title
                g.duration_seconds = transcript.duration_seconds
                await db2.commit()

            # Step 3: run the three-stage Claude pipeline
            analysis = await claude.run_pipeline(
                segments=transcript.transcript_segments,
                title=transcript.title,
                duration_seconds=transcript.duration_seconds,
            )

            # Step 4: resolve all card names → card_ids
            all_card_names: set[str] = set()
            for turn in analysis.turns:
                for interaction in turn.card_interactions:
                    all_card_names.add(interaction.card_name)
                for snapshot in turn.zone_snapshots:
                    for zc in snapshot.cards:
                        all_card_names.add(zc.card_name)

            async with AsyncSessionLocal() as db3:
                name_to_card_id: dict[str, int] = {}
                for name in all_card_names:
                    name_to_card_id[name] = await card_names.resolve(name, db3)
                await db3.commit()

            # Step 5: persist everything
            async with AsyncSessionLocal() as db4:
                await persistence.persist_game_analysis(
                    game_id, analysis, name_to_card_id, db4
                )
                result4 = await db4.execute(select(Game).where(Game.id == game_id))
                game4 = result4.scalar_one()
                game4.status = "complete"
                await db4.commit()

            logger.info("Game %d analysis complete", game_id)

        except Exception as exc:
            logger.exception("Game %d analysis failed", game_id)
            async with AsyncSessionLocal() as db_err:
                result_err = await db_err.execute(
                    select(Game).where(Game.id == game_id)
                )
                game_err = result_err.scalar_one_or_none()
                if game_err:
                    game_err.status = "failed"
                    game_err.error_message = repr(exc)[:1000]
                    await db_err.commit()


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_game(
    body: GameCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Queue a new Commander game analysis.
    Returns immediately with id + status=queued.
    All work (Apify, Claude) happens in the background.
    """
    video_id = _extract_video_id(body.source_url)
    if not video_id:
        raise HTTPException(
            status_code=422, detail="Could not extract YouTube video ID from URL"
        )

    game = Game(
        source_url=body.source_url,
        source_type="youtube",
        video_id=video_id,
        status="queued",
    )
    db.add(game)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="This video has already been analysed"
        )

    await db.commit()
    await db.refresh(game)

    background_tasks.add_task(_analyze_game, game.id, body.source_url)

    return {"id": game.id, "status": game.status}


@router.get("", response_model=list[GameListItem])
async def list_games(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Game).order_by(Game.created_at.desc()))
    return result.scalars().all()


@router.get("/{game_id}", response_model=GameResponse)
async def get_game(game_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(_full_game_query(game_id))
    game = result.scalar_one_or_none()
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return game
