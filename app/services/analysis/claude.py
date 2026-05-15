"""
Three-stage MTG Commander analysis pipeline.

Stage 1 (Haiku)  — split transcript into logical turn chunks
Stage 2 (Haiku)  — analyse each chunk in parallel
Stage 3 (Sonnet) — aggregate all chunks into a final GameAnalysis
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
    _ChunkList,
)
from app.schemas.youtube import TranscriptSegment
from app.services.analysis.chunks import build_chunks_from_boundaries
from app.services.analysis.mock import (
    MOCK_GAME_ANALYSIS,
    mock_analyze_chunk,
    mock_split_into_chunks,
)

logger = logging.getLogger(__name__)


# ── Stage 1 ──────────────────────────────────────────────────────────────────

STAGE1_SYSTEM = """\
You are an expert Magic: The Gathering rules analyst.
Given a timestamped transcript of a Commander game, identify the logical chunk boundaries.
Each chunk should correspond to roughly one player's turn or a major interaction.
For each chunk return ONLY: chunk_index, start_seconds, end_seconds, and a brief estimated_context label.
Do NOT reproduce any transcript text — boundaries and labels only."""


async def split_into_chunks(segments: list[TranscriptSegment]) -> list[TranscriptChunk]:
    if settings.mock_external:
        return mock_split_into_chunks(segments)

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, max_retries=6)
    formatted = "\n".join(
        f"[{seg.start_seconds:.1f}s - {seg.end_seconds:.1f}s] {seg.text}"
        for seg in segments
    )
    response = await client.messages.parse(
        model="claude-haiku-4-5",
        max_tokens=4096,
        system=STAGE1_SYSTEM,
        messages=[{"role": "user", "content": formatted}],
        output_format=_ChunkList,
    )
    boundaries = response.parsed_output.chunks
    logger.info("Stage 1: %d boundaries received", len(boundaries))
    return build_chunks_from_boundaries(boundaries, segments)


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

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, max_retries=6)
    prompt = f"Context: {chunk.estimated_context}\n\nTranscript:\n{chunk.text}"
    response = await client.messages.parse(
        model="claude-haiku-4-5",
        max_tokens=4096,
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

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, max_retries=6)
    context_header = f"Video: {title or 'Unknown'}\nDuration: {duration_seconds or 'Unknown'} seconds\n\n"
    analyses_json = json.dumps([a.model_dump() for a in chunk_analyses], indent=2)
    prompt = context_header + "Per-turn analyses:\n" + analyses_json

    response = await client.messages.parse(
        model="claude-sonnet-4-6",
        max_tokens=16384,
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
    """Run all three stages and return a GameAnalysis."""
    logger.info("Stage 1: splitting transcript into chunks (%d segments)", len(segments))
    chunks = await split_into_chunks(segments)
    logger.info("Stage 1 complete: %d chunks", len(chunks))

    logger.info("Stage 2: analysing %d chunks sequentially", len(chunks))
    chunk_analyses: list[ChunkAnalysis] = []
    for i, chunk in enumerate(chunks):
        logger.info("Stage 2: chunk %d/%d (%s)", i + 1, len(chunks), chunk.estimated_context)
        chunk_analyses.append(await analyze_chunk(chunk))
        if i < len(chunks) - 1:
            await asyncio.sleep(settings.claude_stage2_delay_seconds)
    logger.info("Stage 2 complete")

    logger.info("Stage 3: aggregating into GameAnalysis")
    analysis = await aggregate_game(list(chunk_analyses), title, duration_seconds)
    logger.info("Stage 3 complete")

    return analysis
