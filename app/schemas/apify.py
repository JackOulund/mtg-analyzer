"""
Typed representations of Apify API response shapes.
Use model_validate() at the HTTP boundary so downstream code uses attribute access.
"""
from typing import Any

from pydantic import BaseModel


class ApifySubtitleItem(BaseModel):
    """One entry in the Apify subtitle list: {srt, language, type, srtUrl}."""
    srt: str | None = None
    language: str | None = None
    type: str | None = None
    srtUrl: str | None = None


class SubtitleSegmentDict(BaseModel):
    """One entry in a plain subtitle segment list: {text, start, dur?, end?}."""
    text: str = ""
    start: float = 0.0
    dur: float | None = None
    end: float | None = None


class ApifyVideoItem(BaseModel):
    """
    One dataset item from streamers/youtube-scraper.

    `subtitles` is left as Any because its shape varies across actor versions
    and is dispatched by _parse_subtitles() in apify.py.
    `duration` is left as Any because the actor returns either an int (seconds)
    or a "HH:MM:SS" string; YouTubeTranscript.parse_duration handles both.
    """
    id: str = ""
    title: str | None = None
    duration: Any = None
    subtitles: Any = None
