from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.turn import Turn

# Valid MTG turn phases
VALID_PHASES = {
    "untap", "upkeep", "draw",
    "main1", "begin_combat", "attackers", "blockers",
    "combat_damage", "end_combat", "main2",
    "end_step", "cleanup",
}


class TurnAction(Base):
    __tablename__ = "turn_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    turn_id: Mapped[int] = mapped_column(ForeignKey("turns.id", ondelete="CASCADE"), nullable=False)
    phase: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(nullable=False)

    turn: Mapped["Turn"] = relationship(back_populates="actions")
