from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.player import Player
    from app.models.turn import Turn
    from app.models.card import Card
    from app.models.zone_card_counter import ZoneCardCounter


class ZoneCard(Base):
    """
    Cumulative zone state per player per turn.
    Each row = one card known to be in a given zone at end of that turn.
    """
    __tablename__ = "zone_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    turn_id: Mapped[int] = mapped_column(ForeignKey("turns.id", ondelete="CASCADE"), nullable=False)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), nullable=False)

    # battlefield / graveyard / exile / hand / command
    zone: Mapped[str] = mapped_column(String, nullable=False)
    is_tapped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    effective_power: Mapped[int | None] = mapped_column(nullable=True)
    effective_toughness: Mapped[int | None] = mapped_column(nullable=True)

    player: Mapped["Player"] = relationship(back_populates="zone_cards")
    turn: Mapped["Turn"] = relationship(back_populates="zone_cards")
    card: Mapped["Card"] = relationship(back_populates="zone_cards")
    counters: Mapped[list["ZoneCardCounter"]] = relationship(
        back_populates="zone_card", cascade="all, delete-orphan"
    )
