from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.zone_card import ZoneCard

# Canonical counter types — Claude output is validated against these
VALID_COUNTER_TYPES = {
    "+1/+1", "-1/-1", "loyalty", "charge", "poison",
    "energy", "oil", "age", "fade", "time", "verse",
    "quest", "level", "lore", "shield",
}


class ZoneCardCounter(Base):
    """One row per counter type on a permanent in a zone snapshot."""
    __tablename__ = "zone_card_counters"

    id: Mapped[int] = mapped_column(primary_key=True)
    zone_card_id: Mapped[int] = mapped_column(
        ForeignKey("zone_cards.id", ondelete="CASCADE"), nullable=False
    )
    counter_type: Mapped[str] = mapped_column(String, nullable=False)
    count: Mapped[int] = mapped_column(nullable=False)

    zone_card: Mapped["ZoneCard"] = relationship(back_populates="counters")
