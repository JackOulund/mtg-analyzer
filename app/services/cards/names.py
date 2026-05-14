"""
Card-name normalization and resolution layer.

Bridges Claude's free-form card name strings to cards.id (int).
Resolution order:
  1. Exact DB match
  2. Normalized DB match (lowercase, stripped punctuation)
  3. Scryfall fuzzy lookup + upsert
"""
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card
from app.services.cards import scryfall


def normalize(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    name = name.lower()
    name = re.sub(r"[^\w\s]", "", name)    # remove punctuation
    name = re.sub(r"\s+", " ", name).strip()
    return name


async def resolve(name: str, db: AsyncSession) -> int:
    """
    Return card_id for the given (potentially messy) card name.
    Always returns an id — creates a minimal fallback row if needed.
    """
    # 1. Exact match
    result = await db.execute(select(Card).where(Card.name == name))
    card = result.scalar_one_or_none()
    if card:
        return card.id

    # 2. Normalized match against all existing cards
    norm = normalize(name)
    result = await db.execute(select(Card))
    for card in result.scalars().all():
        if normalize(card.name) == norm:
            return card.id

    # 3. Scryfall fuzzy lookup + upsert
    card = await scryfall.resolve_and_upsert(name, db)
    return card.id
