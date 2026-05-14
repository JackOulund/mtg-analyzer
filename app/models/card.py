from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.turn_card import TurnCard
    from app.models.zone_card import ZoneCard


class Card(Base):
    """
    Scryfall-backed card registry. Surrogate PK so Claude's near-miss names
    never cause FK violations — card_names.resolve() normalises before insert.
    """
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)

    mana_cost: Mapped[str | None] = mapped_column(String, nullable=True)
    cmc: Mapped[float | None] = mapped_column(Float, nullable=True)
    type_line: Mapped[str | None] = mapped_column(String, nullable=True)
    oracle_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    power: Mapped[str | None] = mapped_column(String, nullable=True)
    toughness: Mapped[str | None] = mapped_column(String, nullable=True)
    loyalty: Mapped[str | None] = mapped_column(String, nullable=True)
    colors: Mapped[str | None] = mapped_column(String, nullable=True)  # e.g. "WUB"
    is_land: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scryfall_id: Mapped[str | None] = mapped_column(String, nullable=True)

    turn_cards: Mapped[list["TurnCard"]] = relationship(back_populates="card")
    zone_cards: Mapped[list["ZoneCard"]] = relationship(back_populates="card")
