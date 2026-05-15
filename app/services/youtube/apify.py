"""
YouTube transcript fetcher via Apify's streamers/youtube-scraper actor.
Returns transcript + metadata only — no video file.
"""

from app.services.youtube.mock import MOCK_TRANSCRIPT
from app.schemas.youtube import TranscriptSegment, YouTubeTranscript
from app.schemas.apify import ApifySubtitleItem, ApifyVideoItem, SubtitleSegmentDict
from app.config import settings
import logging
import re

from apify_client import ApifyClientAsync

logger = logging.getLogger(__name__)


def extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from common URL formats."""
    match = re.search(r"(?:v=|youtu\.be/|/embed/|/v/)([A-Za-z0-9_-]{11})", url)
    return match.group(1) if match else None


async def get_youtube_transcript(url: str) -> YouTubeTranscript:
    if settings.mock_external:
        return MOCK_TRANSCRIPT

    client = ApifyClientAsync(settings.apify_token)

    run = await client.actor("streamers/youtube-scraper").call(
        run_input={
            "startUrls": [{"url": url}],
            "maxResults": 1,
            "downloadSubtitles": True,
            "subtitlesLanguage": "en",
            "subtitlesFormat": "srt",
        }
    )
    if not run:
        raise RuntimeError("Apify run returned no result")

    items = (await client.dataset(run["defaultDatasetId"]).list_items()).items
    if not items:
        raise ValueError(f"No results returned for URL: {url}")

    video_item = ApifyVideoItem.model_validate(items[0])
    video_id = extract_video_id(url) or video_item.id

    logger.debug(
        "subtitles type=%s, preview=%r",
        type(video_item.subtitles).__name__,
        str(video_item.subtitles)[:120],
    )
    segments = _parse_subtitles(video_item.subtitles)
    transcript_text = " ".join(s.text for s in segments)

    return YouTubeTranscript(
        video_id=video_id,
        title=video_item.title,
        duration_seconds=video_item.duration,
        transcript_text=transcript_text,
        transcript_segments=segments,
    )


def _parse_subtitles(raw: object) -> list[TranscriptSegment]:
    """
    Dispatch to the correct parser based on what the actor returned.

    The streamers/youtube-scraper actor can return subtitles in several shapes:
      - str  → raw SRT text (parse block by block)
      - list[ApifySubtitleItem] with "srt" key  → [{srt, language, type, srtUrl}]
      - list[SubtitleSegmentDict] with "text" key → [{text, start, dur}]
      - list[str]  → SRT blocks already split into a list
      - anything else / empty → return []
    """
    if not raw:
        return []
    if isinstance(raw, str):
        return _parse_srt(raw)
    if isinstance(raw, list):
        if not raw:
            return []
        if isinstance(raw[0], dict):
            if "srt" in raw[0]:
                subtitle_items = [ApifySubtitleItem.model_validate(x) for x in raw]
                return _parse_apify_subtitle_list(subtitle_items)
            segment_items = [SubtitleSegmentDict.model_validate(x) for x in raw]
            return _parse_subtitle_dicts(segment_items)
        # list of strings — join and treat as one SRT document
        return _parse_srt("\n\n".join(str(item) for item in raw))
    logger.warning(
        "Unexpected subtitles type %s — returning empty transcript", type(raw).__name__
    )
    return []


def _parse_apify_subtitle_list(
    items: list[ApifySubtitleItem],
) -> list[TranscriptSegment]:
    """
    Parse the Apify-format subtitle list: [{srt, language, type, srtUrl}, ...]

    Prefers the English entry; falls back to the first entry with any SRT content.
    """
    srt_text: str | None = None

    # Prefer English
    for item in items:
        if item.language == "en" and item.srt:
            srt_text = item.srt
            break

    # Fall back to any language
    if not srt_text:
        for item in items:
            if item.srt:
                srt_text = item.srt
                break

    if not srt_text:
        logger.warning("No SRT content found in Apify subtitle list")
        return []

    return _parse_srt(srt_text)


def _parse_srt(srt_text: str) -> list[TranscriptSegment]:
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
        segments.append(
            TranscriptSegment(start_seconds=start, end_seconds=end, text=text)
        )

    return segments


def _parse_subtitle_dicts(items: list[SubtitleSegmentDict]) -> list[TranscriptSegment]:
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
        if item.end is not None:
            end = item.end
        else:
            end = start + (item.dur or 0.0)
        segments.append(
            TranscriptSegment(start_seconds=start, end_seconds=end, text=text)
        )
    return segments
