from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.turn import Turn
    from app.models.player import Player
    from app.models.card import Card


class TurnCard(Base):
    """One row per card interaction within a turn."""
    __tablename__ = "turn_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    turn_id: Mapped[int] = mapped_column(ForeignKey("turns.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), nullable=False)

    # cast / activated / triggered / attacked / blocked / sacrificed / discarded / tapped / untapped
    action_type: Mapped[str] = mapped_column(String, nullable=False)
    phase: Mapped[str] = mapped_column(String, nullable=False)
    target: Mapped[str | None] = mapped_column(String, nullable=True)

    turn: Mapped["Turn"] = relationship(back_populates="turn_cards")
    player: Mapped["Player"] = relationship(back_populates="turn_cards")
    card: Mapped["Card"] = relationship(back_populates="turn_cards")
