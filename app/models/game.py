from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.player import Player
    from app.models.turn import Turn
    from app.models.notable_moment import NotableMoment


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(String, default="youtube", nullable=False)
    video_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)

    title: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(nullable=True)
    total_turns: Mapped[int | None] = mapped_column(nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # queued → processing → complete | failed
    status: Mapped[str] = mapped_column(String, default="queued", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now(), onupdate=func.now()
    )

    players: Mapped[list["Player"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )
    turns: Mapped[list["Turn"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )
    notable_moments: Mapped[list["NotableMoment"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )
