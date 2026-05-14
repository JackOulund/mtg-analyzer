from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.player import Player
    from app.models.turn import Turn


class BoardState(Base):
    """Snapshot of player-level counters at the end of each turn."""
    __tablename__ = "board_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    turn_id: Mapped[int] = mapped_column(ForeignKey("turns.id", ondelete="CASCADE"), nullable=False)

    life_total: Mapped[int | None] = mapped_column(nullable=True)
    poison_counters: Mapped[int] = mapped_column(default=0, nullable=False)
    energy_counters: Mapped[int] = mapped_column(default=0, nullable=False)

    player: Mapped["Player"] = relationship(back_populates="board_states")
    turn: Mapped["Turn"] = relationship(back_populates="board_states")
