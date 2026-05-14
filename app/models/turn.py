from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.game import Game
    from app.models.player import Player
    from app.models.turn_action import TurnAction
    from app.models.turn_card import TurnCard
    from app.models.board_state import BoardState
    from app.models.zone_card import ZoneCard


class Turn(Base):
    __tablename__ = "turns"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    active_player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    turn_number: Mapped[int] = mapped_column(nullable=False)

    game: Mapped["Game"] = relationship(back_populates="turns")
    active_player: Mapped["Player"] = relationship(back_populates="active_turns")
    actions: Mapped[list["TurnAction"]] = relationship(
        back_populates="turn", cascade="all, delete-orphan"
    )
    turn_cards: Mapped[list["TurnCard"]] = relationship(
        back_populates="turn", cascade="all, delete-orphan"
    )
    board_states: Mapped[list["BoardState"]] = relationship(
        back_populates="turn", cascade="all, delete-orphan"
    )
    zone_cards: Mapped[list["ZoneCard"]] = relationship(
        back_populates="turn", cascade="all, delete-orphan"
    )
