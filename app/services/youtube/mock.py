"""
Mock YouTube transcript.
Used when settings.mock_external is True.
"""
from app.schemas.youtube import TranscriptSegment, YouTubeTranscript

MOCK_TRANSCRIPT = YouTubeTranscript(
    video_id="dQw4w9WgXcQ",
    title="Commander Gameplay - Atraxa vs Ur-Dragon vs Meren vs Krenko",
    duration_seconds=5400,
    transcript_text=(
        "Welcome to Commander night! Today we have four players. "
        "Alice is on Atraxa Praetors Voice. Bob is playing Ur-Dragon. "
        "Carol has Meren of Clan Nel Toth. Dave is on Krenko Mob Boss. "
        "Turn 1, Alice plays a forest and passes. Bob plays an island. "
        "Carol plays a swamp. Dave plays a mountain. "
        "Turn 2, Alice casts Sol Ring then Atraxa. Bob plays Cultivate. "
        "Carol casts Golgari Signet. Dave casts Krenko and attacks Alice for two. "
        "Alice is now at 38. Turn 3, Alice proliferates with Evolution Sage. "
        "Bob swings with Savage Ventmaw for six at Dave. Dave is at 34. "
        "Carol casts Jarad Golgari Lich Lord. Dave uses Krenko to make goblins. "
        "Turn 4, big turn — Bob plays Ur-Dragon and starts swinging. "
        "Carol sacrifices creatures to Jarad dealing damage. "
        "Dave sacs goblins for damage. Alice at 20, Bob at 40, Carol at 30, Dave at 18. "
        "Turn 10, Alice wins with Atraxa infinite counters combo."
    ),
    transcript_segments=[
        TranscriptSegment(
            start_seconds=0.0,
            end_seconds=30.0,
            text=(
                "Welcome to Commander night! Today we have four players. "
                "Alice is on Atraxa Praetors Voice. Bob is playing Ur-Dragon. "
                "Carol has Meren of Clan Nel Toth. Dave is on Krenko Mob Boss."
            ),
        ),
        TranscriptSegment(
            start_seconds=30.0,
            end_seconds=90.0,
            text=(
                "Turn 1, Alice plays a forest and passes. Bob plays an island. "
                "Carol plays a swamp. Dave plays a mountain."
            ),
        ),
        TranscriptSegment(
            start_seconds=90.0,
            end_seconds=180.0,
            text=(
                "Turn 2, Alice casts Sol Ring then Atraxa. Bob plays Cultivate. "
                "Carol casts Golgari Signet. Dave casts Krenko and attacks Alice for two."
            ),
        ),
        TranscriptSegment(
            start_seconds=180.0,
            end_seconds=300.0,
            text=(
                "Turn 3, Alice proliferates with Evolution Sage. "
                "Bob swings with Savage Ventmaw for six at Dave. "
                "Carol casts Jarad Golgari Lich Lord. Dave uses Krenko to make goblins."
            ),
        ),
        TranscriptSegment(
            start_seconds=300.0,
            end_seconds=5400.0,
            text=(
                "Turn 4, big turn — Bob plays Ur-Dragon and starts swinging. "
                "Carol sacrifices creatures to Jarad dealing damage. "
                "Dave sacs goblins for damage. Turn 10, Alice wins with Atraxa infinite counters combo."
            ),
        ),
    ],
)
