"""
Scryfall card metadata lookup.
Uses the fuzzy endpoint so small typos in card names are tolerated.
"""
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.card import Card


SCRYFALL_FUZZY_URL = "https://api.scryfall.com/cards/named"


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
    scryfall_data = await _fetch_scryfall(name)

    if scryfall_data is None:
        # Graceful fallback — unknown card, insert minimal row
        card = Card(name=name)
        db.add(card)
        await db.flush()
        return card

    canonical_name = scryfall_data.get("name", name)

    # 3. Check again by canonical name (may differ from input)
    result = await db.execute(select(Card).where(Card.name == canonical_name))
    card = result.scalar_one_or_none()
    if card:
        return card

    # 4. Insert full card row
    type_line = scryfall_data.get("type_line", "") or ""
    card = Card(
        name=canonical_name,
        mana_cost=scryfall_data.get("mana_cost"),
        cmc=scryfall_data.get("cmc"),
        type_line=type_line,
        oracle_text=scryfall_data.get("oracle_text"),
        power=scryfall_data.get("power"),
        toughness=scryfall_data.get("toughness"),
        loyalty=scryfall_data.get("loyalty"),
        colors="".join(scryfall_data.get("colors", [])),
        is_land="Land" in type_line,
        scryfall_id=scryfall_data.get("id"),
    )
    db.add(card)
    await db.flush()
    return card


async def _fetch_scryfall(name: str) -> dict | None:
    """Call the Scryfall fuzzy endpoint. Returns None on 404."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(SCRYFALL_FUZZY_URL, params={"fuzzy": name})
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
