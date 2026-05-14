"""
YouTube transcript fetcher via Apify's streamers/youtube-scraper actor.
Returns transcript + metadata only — no video file.
"""
import logging
import re

from apify_client import ApifyClientAsync

logger = logging.getLogger(__name__)

from app.config import settings
from app.schemas.youtube import TranscriptSegment, YouTubeTranscript
from app.services.youtube.mock import MOCK_TRANSCRIPT


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

    item = items[0]
    video_id = extract_video_id(url) or item.get("id", "")

    raw_subtitles = item.get("subtitles") or ""
    logger.debug("subtitles type=%s, preview=%r", type(raw_subtitles).__name__, str(raw_subtitles)[:120])
    segments = _parse_subtitles(raw_subtitles)
    transcript_text = " ".join(s.text for s in segments)

    return YouTubeTranscript(
        video_id=video_id,
        title=item.get("title"),
        duration_seconds=item.get("duration"),
        transcript_text=transcript_text,
        transcript_segments=segments,
    )


def _parse_subtitles(raw) -> list[TranscriptSegment]:
    """
    Dispatch to the correct parser based on what the actor returned.

    The streamers/youtube-scraper actor can return subtitles in several shapes:
      - str  → raw SRT text (parse block by block)
      - list[dict] with "srt" key  → Apify format: [{srt, language, type, srtUrl}]
      - list[dict] with "text" key → segment dicts with "text"/"start"/"dur" keys
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
                return _parse_apify_subtitle_list(raw)
            return _parse_subtitle_dicts(raw)
        # list of strings — join and treat as one SRT document
        return _parse_srt("\n\n".join(str(item) for item in raw))
    logger.warning("Unexpected subtitles type %s — returning empty transcript", type(raw).__name__)
    return []


def _parse_apify_subtitle_list(items: list[dict]) -> list[TranscriptSegment]:
    """
    Parse the Apify-format subtitle list: [{srt, language, type, srtUrl}, ...]

    Prefers the English entry; falls back to the first entry with any SRT content.
    """
    srt_text = None

    # Prefer English
    for item in items:
        if item.get("language") == "en" and item.get("srt"):
            srt_text = item["srt"]
            break

    # Fall back to any language
    if not srt_text:
        for item in items:
            if item.get("srt"):
                srt_text = item["srt"]
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
        end   = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000
        segments.append(TranscriptSegment(start_seconds=start, end_seconds=end, text=text))

    return segments


def _parse_subtitle_dicts(items: list[dict]) -> list[TranscriptSegment]:
    """
    Parse a list of subtitle dicts.
    Expected keys: "text", "start" (seconds float), and either "dur" or "end".
    """
    segments: list[TranscriptSegment] = []
    for item in items:
        text = (item.get("text") or "").strip()
        if not text:
            continue
        try:
            start = float(item.get("start", 0))
            if "end" in item:
                end = float(item["end"])
            else:
                end = start + float(item.get("dur", 0))
        except (TypeError, ValueError):
            continue
        segments.append(TranscriptSegment(start_seconds=start, end_seconds=end, text=text))
    return segments
