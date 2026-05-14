from datetime import datetime

from pydantic import BaseModel


class GameCreate(BaseModel):
    source_url: str


class GameListItem(BaseModel):
    id: int
    title: str | None
    status: str
    total_turns: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PlayerResponse(BaseModel):
    id: int
    name: str
    commander_name: str | None
    is_winner: bool
    seat_order: int

    model_config = {"from_attributes": True}


class TurnActionResponse(BaseModel):
    phase: str
    description: str
    order_index: int

    model_config = {"from_attributes": True}


class TurnCardResponse(BaseModel):
    card_id: int
    action_type: str
    phase: str
    target: str | None

    model_config = {"from_attributes": True}


class TurnResponse(BaseModel):
    id: int
    turn_number: int
    active_player_id: int
    actions: list[TurnActionResponse]
    turn_cards: list[TurnCardResponse]

    model_config = {"from_attributes": True}


class NotableMomentResponse(BaseModel):
    turn_number: int | None
    description: str
    order_index: int

    model_config = {"from_attributes": True}


class GameResponse(BaseModel):
    id: int
    source_url: str
    video_id: str
    title: str | None
    duration_seconds: int | None
    total_turns: int | None
    summary: str | None
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    players: list[PlayerResponse]
    turns: list[TurnResponse]
    notable_moments: list[NotableMomentResponse]

    model_config = {"from_attributes": True}
