"""
YouTube transcript fetcher via Apify's streamers/youtube-scraper actor.
Returns transcript + metadata only — no video file.
"""
import re

from apify_client import ApifyClientAsync

from app.config import settings
from app.schemas.apify.youtube import TranscriptSegment, YouTubeTranscript
from app.services.mocks.apify import MOCK_TRANSCRIPT


def _extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from common URL formats."""
    patterns = [
        r"(?:v=|youtu\.be/|/embed/|/v/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


async def get_youtube_transcript(url: str) -> YouTubeTranscript:
    if settings.mock_external:
        return MOCK_TRANSCRIPT

    client = ApifyClientAsync(settings.apify_token)

    run = await client.actor("streamers/youtube-scraper").call(
        run_input={
            "startUrls": [{"url": url}],
            "maxResults": 1,
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
    video_id = _extract_video_id(url) or item.get("id", "")

    # Parse SRT subtitles into segments
    raw_subtitles = item.get("subtitles", "") or ""
    segments = _parse_srt(raw_subtitles)
    transcript_text = " ".join(s.text for s in segments)

    return YouTubeTranscript(
        video_id=video_id,
        title=item.get("title"),
        duration_seconds=item.get("duration"),
        transcript_text=transcript_text,
        transcript_segments=segments,
    )


def _parse_srt(srt_text: str) -> list[TranscriptSegment]:
    """Parse SRT subtitle format into TranscriptSegment list."""
    segments: list[TranscriptSegment] = []
    if not srt_text.strip():
        return segments

    # SRT blocks separated by blank lines
    blocks = re.split(r"\n\s*\n", srt_text.strip())
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        # Line 0: sequence number, Line 1: timestamps, Line 2+: text
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
