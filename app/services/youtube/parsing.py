"""
Pure YouTube/subtitle parsing helpers.
No side effects — no HTTP, no DB, no async.
"""
import logging
import re

from app.schemas.apify import ApifySubtitleItem, SubtitleSegmentDict
from app.schemas.youtube import TranscriptSegment

logger = logging.getLogger(__name__)


def extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from common URL formats."""
    match = re.search(r"(?:v=|youtu\.be/|/embed/|/v/)([A-Za-z0-9_-]{11})", url)
    return match.group(1) if match else None


def parse_subtitles(raw: object) -> list[TranscriptSegment]:
    """
    Dispatch to the correct parser based on what the actor returned.

    The streamers/youtube-scraper actor can return subtitles in several shapes:
      - str  → raw SRT text (parse block by block)
      - list with "srt" key dicts → [{srt, language, type, srtUrl}]
      - list with "text" key dicts → [{text, start, dur}]
      - list[str] → SRT blocks already split into a list
      - anything else / empty → return []
    """
    if not raw:
        return []
    if isinstance(raw, str):
        return parse_srt(raw)
    if isinstance(raw, list):
        if not raw:
            return []
        if isinstance(raw[0], dict):
            if "srt" in raw[0]:
                items = [ApifySubtitleItem.model_validate(x) for x in raw]
                return parse_apify_subtitle_list(items)
            items = [SubtitleSegmentDict.model_validate(x) for x in raw]
            return parse_subtitle_dicts(items)
        # list of strings — join and treat as one SRT document
        return parse_srt("\n\n".join(str(item) for item in raw))
    logger.warning("Unexpected subtitles type %s — returning empty transcript", type(raw).__name__)
    return []


def parse_apify_subtitle_list(items: list[ApifySubtitleItem]) -> list[TranscriptSegment]:
    """
    Parse the Apify-format subtitle list: [{srt, language, type, srtUrl}, ...]

    Prefers the English entry; falls back to the first entry with any SRT content.
    """
    srt_text: str | None = None

    for item in items:
        if item.language == "en" and item.srt:
            srt_text = item.srt
            break

    if not srt_text:
        for item in items:
            if item.srt:
                srt_text = item.srt
                break

    if not srt_text:
        logger.warning("No SRT content found in Apify subtitle list")
        return []

    return parse_srt(srt_text)


def parse_srt(srt_text: str) -> list[TranscriptSegment]:
    """Parse a raw SRT string into TranscriptSegments."""
    segments: list[TranscriptSegment] = []
    if not srt_text.strip():
        return segments

    for block in re.split(r"\n\s*\n", srt_text.strip()):
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        # Line 0: sequence number  Line 1: timestamps  Line 2+: text
        time_line = lines[1]
        text = " ".join(lines[2:])
        match = re.match(
            r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)",
            time_line,
        )
        if not match:
            continue
        h1, m1, s1, ms1, h2, m2, s2, ms2 = (int(x) for x in match.groups())
        start = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000
        end = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000
        segments.append(TranscriptSegment(start_seconds=start, end_seconds=end, text=text))

    return segments


def parse_subtitle_dicts(items: list[SubtitleSegmentDict]) -> list[TranscriptSegment]:
    """
    Parse a list of typed subtitle segment dicts.
    Each item has: text, start (seconds float), and either dur or end.
    """
    segments: list[TranscriptSegment] = []
    for item in items:
        text = item.text.strip()
        if not text:
            continue
        start = item.start
        end = item.end if item.end is not None else start + (item.dur or 0.0)
        segments.append(TranscriptSegment(start_seconds=start, end_seconds=end, text=text))
    return segments
