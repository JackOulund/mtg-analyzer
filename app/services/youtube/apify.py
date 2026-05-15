"""
YouTube transcript fetcher via Apify's streamers/youtube-scraper actor.
Returns transcript + metadata only — no video file.
"""
import logging

from apify_client import ApifyClientAsync

from app.config import settings
from app.schemas.apify import ApifyVideoItem
from app.schemas.youtube import YouTubeTranscript
from app.services.youtube.mock import MOCK_TRANSCRIPT
from app.services.youtube.parsing import extract_video_id, parse_subtitles

logger = logging.getLogger(__name__)


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
    segments = parse_subtitles(video_item.subtitles)
    transcript_text = " ".join(s.text for s in segments)

    return YouTubeTranscript(
        video_id=video_id,
        title=video_item.title,
        duration_seconds=video_item.duration,
        transcript_text=transcript_text,
        transcript_segments=segments,
    )
