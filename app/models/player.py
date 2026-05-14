from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.game import Game
    from app.models.turn import Turn
    from app.models.turn_card import TurnCard
    from app.models.board_state import BoardState
    from app.models.zone_card import ZoneCard


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    commander_name: Mapped[str | None] = mapped_column(String, nullable=True)
    is_winner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    seat_order: Mapped[int] = mapped_column(nullable=False)  # turn order, 1-based

    game: Mapped["Game"] = relationship(back_populates="players")
    active_turns: Mapped[list["Turn"]] = relationship(back_populates="active_player")
    turn_cards: Mapped[list["TurnCard"]] = relationship(back_populates="player")
    board_states: Mapped[list["BoardState"]] = relationship(back_populates="player")
    zone_cards: Mapped[list["ZoneCard"]] = relationship(back_populates="player")
