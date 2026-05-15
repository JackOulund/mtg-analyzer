"""
Pure transcript chunking helpers.
No side effects — no HTTP, no DB, no async.
"""
from app.schemas.analysis import TranscriptChunk, _ChunkBoundary
from app.schemas.youtube import TranscriptSegment


def build_chunks_from_boundaries(
    boundaries: list[_ChunkBoundary],
    segments: list[TranscriptSegment],
) -> list[TranscriptChunk]:
    """
    Reconstruct TranscriptChunk objects by slicing the original segments
    according to the boundaries Claude identified.

    This avoids asking Claude to echo back the (potentially enormous) transcript
    in its output — Stage 1 returns boundaries only, and we do the text
    reconstruction here in Python.
    """
    chunks: list[TranscriptChunk] = []
    sorted_segs = sorted(segments, key=lambda s: s.start_seconds)

    for boundary in boundaries:
        matching = [
            s for s in sorted_segs
            if boundary.start_seconds <= s.start_seconds <= boundary.end_seconds
        ]
        text = " ".join(s.text for s in matching) if matching else ""
        chunks.append(TranscriptChunk(
            chunk_index=boundary.chunk_index,
            start_seconds=boundary.start_seconds,
            end_seconds=boundary.end_seconds,
            estimated_context=boundary.estimated_context,
            text=text,
        ))

    return chunks
