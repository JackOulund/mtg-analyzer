"""
Pydantic models that define the Claude analysis pipeline contract.

Stage 1  → list[TranscriptChunk]
Stage 2  → list[ChunkAnalysis]
Stage 3  → GameAnalysis   (single source of truth written to DB)
"""
from pydantic import BaseModel


# ── Stage 1 output ──────────────────────────────────────────────────────────

class TranscriptChunk(BaseModel):
    chunk_index: int
    text: str
    start_seconds: float
    end_seconds: float
    estimated_context: str   # e.g. "Turn 3 — Alice's main phase"


# ── Stage 2 output ──────────────────────────────────────────────────────────

class Counter(BaseModel):
    counter_type: str   # "+1/+1", "-1/-1", "loyalty", "charge", etc.
    count: int


class ZoneCard(BaseModel):
    card_name: str
    is_tapped: bool = False
    effective_power: int | None = None
    effective_toughness: int | None = None
    counters: list[Counter] = []


class ZoneSnapshot(BaseModel):
    player: str
    zone: str   # battlefield / graveyard / exile / hand / command
    cards: list[ZoneCard]


class CardInteraction(BaseModel):
    card_name: str
    player: str
    # cast / activated / triggered / attacked / blocked /
    # sacrificed / discarded / tapped / untapped
    action_type: str
    phase: str
    target: str | None = None


class TurnAction(BaseModel):
    # untap / upkeep / draw / main1 / begin_combat / attackers /
    # blockers / combat_damage / end_combat / main2 / end_step / cleanup
    phase: str
    description: str
    order_index: int


class ChunkAnalysis(BaseModel):
    turn_number: int | None = None
    active_player: str | None = None
    actions: list[TurnAction] = []
    card_interactions: list[CardInteraction] = []
    zone_snapshots: list[ZoneSnapshot] = []
    life_totals: dict[str, int] = {}
    poison_counters: dict[str, int] = {}
    energy_counters: dict[str, int] = {}


# ── Stage 3 output (GameAnalysis) ───────────────────────────────────────────

class PlayerData(BaseModel):
    name: str
    commander_name: str | None = None
    is_winner: bool = False
    seat_order: int


class TurnData(BaseModel):
    turn_number: int
    active_player: str
    actions: list[TurnAction] = []
    card_interactions: list[CardInteraction] = []
    zone_snapshots: list[ZoneSnapshot] = []
    life_totals: dict[str, int] = {}
    poison_counters: dict[str, int] = {}
    energy_counters: dict[str, int] = {}


class NotableMoment(BaseModel):
    turn_number: int | None = None
    description: str
    order_index: int


class GameAnalysis(BaseModel):
    """
    The final contract between the Claude pipeline and DB persistence.
    persistence.persist_game_analysis() walks this model and writes all ORM rows.
    """
    players: list[PlayerData]
    total_turns: int
    summary: str
    notable_moments: list[NotableMoment] = []
    turns: list[TurnData] = []


# ── Internal helpers for Stage 1 structured output ──────────────────────────

class _ChunkBoundary(BaseModel):
    """
    What Stage 1 actually asks Claude to produce — boundaries only, no text.
    The pipeline reconstructs TranscriptChunk.text from the original segments
    so we never ask Claude to echo back the (potentially huge) transcript.
    """
    chunk_index: int
    start_seconds: float
    end_seconds: float
    estimated_context: str   # e.g. "Turn 3 — Alice's main phase"


class _ChunkList(BaseModel):
    """Wrapper so Stage 1 can return a list via structured output."""
    chunks: list[_ChunkBoundary]
