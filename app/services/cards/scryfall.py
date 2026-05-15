"""
Scryfall card metadata lookup.
Uses the fuzzy endpoint so small typos in card names are tolerated.

Scryfall's usage policy asks for 50–100 ms between requests.  We sleep
_SCRYFALL_DELAY_S after every fetch and retry up to _MAX_RETRIES times on 429.
"""
import asyncio
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card
from app.schemas.scryfall import ScryfallCard

logger = logging.getLogger(__name__)

SCRYFALL_FUZZY_URL = "https://api.scryfall.com/cards/named"
_SCRYFALL_DELAY_S = 0.1   # 100 ms between requests
_MAX_RETRIES = 5
_RETRY_BACKOFF_S = 2.0    # base wait on 429; doubles each retry


async def resolve_and_upsert(name: str, db: AsyncSession) -> Card:
    """
    Look up a card by name. Checks the local DB first, then Scryfall.
    Always inserts using the canonical Scryfall name (not the raw input).
    Falls back to a minimal Card row if Scryfall returns 404.
    """
    # 1. Exact match in DB
    result = await db.execute(select(Card).where(Card.name == name))
    card = result.scalar_one_or_none()
    if card:
        return card

    # 2. Fetch from Scryfall (fuzzy)
    scryfall_card = await _fetch_scryfall(name)

    if scryfall_card is None:
        # Graceful fallback — unknown card, insert minimal row
        card = Card(name=name)
        db.add(card)
        await db.flush()
        return card

    # 3. Check again by canonical name (may differ from input)
    result = await db.execute(select(Card).where(Card.name == scryfall_card.name))
    card = result.scalar_one_or_none()
    if card:
        return card

    # 4. Insert full card row
    card = Card(
        name=scryfall_card.name,
        mana_cost=scryfall_card.mana_cost,
        cmc=scryfall_card.cmc,
        type_line=scryfall_card.type_line,
        oracle_text=scryfall_card.oracle_text,
        power=scryfall_card.power,
        toughness=scryfall_card.toughness,
        loyalty=scryfall_card.loyalty,
        colors="".join(scryfall_card.colors),
        is_land="Land" in scryfall_card.type_line,
        scryfall_id=scryfall_card.id,
    )
    db.add(card)
    await db.flush()
    return card


async def _fetch_scryfall(name: str) -> ScryfallCard | None:
    """
    Call the Scryfall fuzzy endpoint. Returns None on 404.
    Retries with exponential backoff on 429, and always sleeps
    _SCRYFALL_DELAY_S after a successful fetch to respect rate limits.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        backoff = _RETRY_BACKOFF_S
        for attempt in range(_MAX_RETRIES + 1):
            resp = await client.get(SCRYFALL_FUZZY_URL, params={"fuzzy": name})
            if resp.status_code == 404:
                await asyncio.sleep(_SCRYFALL_DELAY_S)
                return None
            if resp.status_code == 429:
                if attempt >= _MAX_RETRIES:
                    resp.raise_for_status()
                logger.warning(
                    "Scryfall 429 for %r — waiting %.1fs (attempt %d/%d)",
                    name, backoff, attempt + 1, _MAX_RETRIES,
                )
                await asyncio.sleep(backoff)
                backoff *= 2
                continue
            resp.raise_for_status()
            await asyncio.sleep(_SCRYFALL_DELAY_S)
            return ScryfallCard.model_validate(resp.json())
    return None  # unreachable, satisfies type checker
