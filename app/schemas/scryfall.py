"""
Typed representation of Scryfall API responses.
Use ScryfallCard.model_validate(resp.json()) immediately after the HTTP call
so all downstream code uses attribute access instead of dict .get().
"""
from pydantic import BaseModel, field_validator


class ScryfallCard(BaseModel):
    """Fields we use from a Scryfall card object."""
    name: str
    type_line: str = ""
    mana_cost: str | None = None
    cmc: float | None = None
    oracle_text: str | None = None
    power: str | None = None
    toughness: str | None = None
    loyalty: str | None = None
    colors: list[str] = []
    id: str | None = None   # Scryfall UUID — named "id" in the API response

    @field_validator("type_line", mode="before")
    @classmethod
    def coerce_none_to_empty(cls, v: object) -> str:
        """Scryfall occasionally omits type_line on tokens; treat as empty."""
        return v or ""
