from pydantic import BaseModel, field_validator


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

    @field_validator("duration_seconds", mode="before")
    @classmethod
    def parse_duration(cls, v):
        """Accept both an integer (seconds) and a 'HH:MM:SS' string."""
        if v is None or isinstance(v, int):
            return v
        if isinstance(v, str):
            parts = v.strip().split(":")
            try:
                if len(parts) == 3:          # HH:MM:SS
                    h, m, s = parts
                    return int(h) * 3600 + int(m) * 60 + int(s)
                if len(parts) == 2:          # MM:SS
                    m, s = parts
                    return int(m) * 60 + int(s)
                return int(v)                # plain numeric string
            except ValueError:
                return None                  # unparseable — treat as unknown
        return v
