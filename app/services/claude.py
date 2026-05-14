"""
Three-stage MTG Commander analysis pipeline.

Stage 1 (Haiku)  — split transcript into logical turn chunks
Stage 2 (Haiku)  — analyse each chunk in parallel (transcript-only in v1)
Stage 3 (Sonnet) — aggregate all chunks into a final GameAnalysis

Call shape mirrors moodyapi:
    client.messages.parse(..., output_format=PydanticModel)
    response.parsed_output
"""

import asyncio
import json
import logging

import anthropic

from app.config import settings
from app.schemas.analysis import (
    ChunkAnalysis,
    GameAnalysis,
    TranscriptChunk,
    ZoneSnapshot,
    CardInteraction,
)
from app.schemas.apify.youtube import TranscriptSegment
from app.services.mocks.claude import (
    MOCK_GAME_ANALYSIS,
    mock_analyze_chunk,
    mock_split_into_chunks,
)

logger = logging.getLogger(__name__)


# ── Stage 1 ──────────────────────────────────────────────────────────────────

STAGE1_SYSTEM = """\
You are an expert Magic: The Gathering rules analyst.
Given a timestamped transcript of a Commander game, split it into logical chunks.
Each chunk should correspond to roughly one player's turn or a major interaction.
Preserve the start_seconds and end_seconds from the transcript segments.
Return the chunks in order."""


async def split_into_chunks(
    segments: list[TranscriptSegment],
) -> list[TranscriptChunk]:
    if settings.mock_external:
        return mock_split_into_chunks(segments)

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    formatted = "\n".join(
        f"[{seg.start_seconds:.1f}s - {seg.end_seconds:.1f}s] {seg.text}"
        for seg in segments
    )

    from app.schemas.analysis import _ChunkList  # local import to keep top clean

    response = client.messages.parse(
        model="claude-haiku-4-5",
        max_tokens=4096,
        system=STAGE1_SYSTEM,
        messages=[{"role": "user", "content": formatted}],
        output_format=_ChunkList,
    )
    return response.parsed_output.chunks


# ── Stage 2 ──────────────────────────────────────────────────────────────────

STAGE2_SYSTEM = """\
You are an expert Magic: The Gathering Commander analyst.
Given a transcript chunk from a game, extract:
- The turn number and active player (if determinable)
- Every action taken, with the MTG phase it occurred in
- Every card interaction (cast, activated, triggered, attacked, blocked, sacrificed, discarded, tapped, untapped)
- Zone snapshots: what cards are on each player's battlefield, graveyard, exile, hand, or command zone
- Life totals and poison/energy counters for each player (if mentioned)
Be precise. Only include information explicitly stated or strongly implied by the transcript."""


async def analyze_chunk(chunk: TranscriptChunk) -> ChunkAnalysis:
    if settings.mock_external:
        return mock_analyze_chunk(chunk)

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    prompt = f"Context: {chunk.estimated_context}\n\nTranscript:\n{chunk.text}"

    response = client.messages.parse(
        model="claude-haiku-4-5",
        max_tokens=2048,
        system=STAGE2_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        output_format=ChunkAnalysis,
    )
    return response.parsed_output


# ── Stage 3 ──────────────────────────────────────────────────────────────────

STAGE3_SYSTEM = """\
You are an expert Magic: The Gathering Commander analyst.
You will receive a series of per-turn analyses from a Commander game.
Your job is to:
1. Resolve any conflicts or duplicates across chunks
2. Determine the final winner
3. Fill in any gaps where information can be inferred
4. Produce a complete, coherent GameAnalysis with all players, turns, and notable moments
5. Write a 2-3 sentence summary of the game

Be accurate — only include information from the provided analyses."""


async def aggregate_game(
    chunk_analyses: list[ChunkAnalysis],
    title: str | None,
    duration_seconds: int | None,
) -> GameAnalysis:
    if settings.mock_external:
        return MOCK_GAME_ANALYSIS

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    context_header = f"Video: {title or 'Unknown'}\nDuration: {duration_seconds or 'Unknown'} seconds\n\n"
    analyses_json = json.dumps(
        [a.model_dump() for a in chunk_analyses],
        indent=2,
    )
    prompt = context_header + "Per-turn analyses:\n" + analyses_json

    response = client.messages.parse(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=STAGE3_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        output_format=GameAnalysis,
    )
    return response.parsed_output


# ── Full pipeline ─────────────────────────────────────────────────────────────


async def run_pipeline(
    segments: list[TranscriptSegment],
    title: str | None,
    duration_seconds: int | None,
) -> GameAnalysis:
    """
    Convenience wrapper: runs all three stages and returns a GameAnalysis.
    Concurrency for Stage 2 is bounded by settings.claude_max_concurrency.
    """
    logger.info(
        "Stage 1: splitting transcript into chunks (%d segments)", len(segments)
    )
    chunks = await split_into_chunks(segments)
    logger.info("Stage 1 complete: %d chunks", len(chunks))

    logger.info(
        "Stage 2: analysing %d chunks (concurrency=%d)",
        len(chunks),
        settings.claude_max_concurrency,
    )
    sem = asyncio.Semaphore(settings.claude_max_concurrency)

    async def _one(c: TranscriptChunk) -> ChunkAnalysis:
        async with sem:
            return await analyze_chunk(c)

    chunk_analyses = await asyncio.gather(*[_one(c) for c in chunks])
    logger.info("Stage 2 complete")

    logger.info("Stage 3: aggregating into GameAnalysis")
    analysis = await aggregate_game(list(chunk_analyses), title, duration_seconds)
    logger.info("Stage 3 complete")

    return analysis
