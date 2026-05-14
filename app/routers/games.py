"""
Games router.

Handles HTTP for /games — request validation, duplicate detection, response
shaping. All business logic (Apify, Claude, DB persistence) lives in
app/services/pipeline.py and is run as a background task.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.game import Game
from app.models.turn import Turn
from app.schemas.game import GameCreate, GameListItem, GameResponse
from app.services.youtube.apify import extract_video_id
from app.services.analysis.pipeline import run_analysis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/games", tags=["games"])


# ── Query helpers ─────────────────────────────────────────────────────────────


def _full_game_query(game_id: int):
    """Eagerly load all nested relations needed for GameResponse."""
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


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_game(
    body: GameCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Queue a new Commander game analysis.
    Returns immediately (202) with id + status=queued.
    All work (Apify, Claude, persistence) runs in the background.
    """
    video_id = extract_video_id(body.source_url)
    if not video_id:
        raise HTTPException(
            status_code=422,
            detail="Could not extract YouTube video ID from URL",
        )

    # Check for an existing row with this video_id
    result = await db.execute(select(Game).where(Game.video_id == video_id))
    existing = result.scalar_one_or_none()

    if existing is not None:
        if existing.status != "failed":
            raise HTTPException(
                status_code=409,
                detail=f"This video has already been submitted (status: {existing.status})",
            )
        # Re-queue a previously failed analysis
        existing.status = "queued"
        existing.error_message = None
        await db.commit()
        await db.refresh(existing)
        background_tasks.add_task(run_analysis, existing.id, body.source_url)
        return {"id": existing.id, "status": existing.status}

    game = Game(
        source_url=body.source_url,
        source_type="youtube",
        video_id=video_id,
        status="queued",
    )
    db.add(game)
    await db.commit()
    await db.refresh(game)

    background_tasks.add_task(run_analysis, game.id, body.source_url)

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
