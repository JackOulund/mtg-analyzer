from pydantic import BaseModel


class TranscriptSegment(BaseModel):
    """One timestamped line from the YouTube transcript."""
    start_seconds: float
    end_seconds: float
    text: str


class YouTubeTranscript(BaseModel):
    """Parsed output from streamers/youtube-scraper Apify actor."""
    video_id: str
    title: str | None = None
    duration_seconds: int | None = None
    transcript_text: str               # full joined transcript
    transcript_segments: list[TranscriptSegment]
