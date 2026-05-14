"""
Mock responses for the Claude service.
Used when settings.mock_external is True.
"""
from app.schemas.analysis import (
    CardInteraction,
    ChunkAnalysis,
    GameAnalysis,
    NotableMoment,
    PlayerData,
    TranscriptChunk,
    TurnAction,
    TurnData,
)
from app.schemas.apify.youtube import TranscriptSegment

MOCK_GAME_ANALYSIS = GameAnalysis(
    players=[
        PlayerData(
            name="Alice",
            commander_name="Atraxa, Praetors' Voice",
            is_winner=True,
            seat_order=1,
        ),
        PlayerData(
            name="Bob",
            commander_name="The Ur-Dragon",
            is_winner=False,
            seat_order=2,
        ),
        PlayerData(
            name="Carol",
            commander_name="Meren of Clan Nel Toth",
            is_winner=False,
            seat_order=3,
        ),
        PlayerData(
            name="Dave",
            commander_name="Krenko, Mob Boss",
            is_winner=False,
            seat_order=4,
        ),
    ],
    total_turns=10,
    summary=(
        "A 10-turn Commander game where Alice's Atraxa proliferate engine "
        "outpaced the table, ultimately winning through an infinite counters combo "
        "while Dave's goblin swarm kept early pressure on the group."
    ),
    notable_moments=[
        NotableMoment(
            turn_number=2,
            description="Alice lands Atraxa on turn 2 via Sol Ring ramp.",
            order_index=0,
        ),
        NotableMoment(
            turn_number=4,
            description="Bob deploys The Ur-Dragon and immediately swings for lethal-threatening damage.",
            order_index=1,
        ),
        NotableMoment(
            turn_number=10,
            description="Alice assembles infinite counters combo and wins.",
            order_index=2,
        ),
    ],
    turns=[
        TurnData(
            turn_number=1,
            active_player="Alice",
            actions=[
                TurnAction(
                    phase="main1",
                    description="Alice plays Forest and passes.",
                    order_index=0,
                )
            ],
            card_interactions=[],
            zone_snapshots=[],
            life_totals={"Alice": 40, "Bob": 40, "Carol": 40, "Dave": 40},
        ),
        TurnData(
            turn_number=2,
            active_player="Alice",
            actions=[
                TurnAction(
                    phase="main1",
                    description="Alice casts Sol Ring, then casts Atraxa.",
                    order_index=0,
                ),
            ],
            card_interactions=[
                CardInteraction(
                    card_name="Sol Ring",
                    player="Alice",
                    action_type="cast",
                    phase="main1",
                ),
                CardInteraction(
                    card_name="Atraxa, Praetors' Voice",
                    player="Alice",
                    action_type="cast",
                    phase="main1",
                ),
            ],
            zone_snapshots=[],
            life_totals={"Alice": 38, "Bob": 40, "Carol": 40, "Dave": 40},
        ),
    ],
)


def mock_split_into_chunks(segments: list[TranscriptSegment]) -> list[TranscriptChunk]:
    """Return one chunk per transcript segment (no Claude call)."""
    return [
        TranscriptChunk(
            chunk_index=i,
            text=seg.text,
            start_seconds=seg.start_seconds,
            end_seconds=seg.end_seconds,
            estimated_context=f"Segment {i}",
        )
        for i, seg in enumerate(segments)
    ]


def mock_analyze_chunk(chunk: TranscriptChunk) -> ChunkAnalysis:
    """Return a minimal ChunkAnalysis stub (no Claude call)."""
    return ChunkAnalysis(
        turn_number=chunk.chunk_index + 1,
        active_player=None,
        actions=[],
        card_interactions=[],
        zone_snapshots=[],
    )
