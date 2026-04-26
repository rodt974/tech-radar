"""Hacker News top stories.

Strategy:
- Use the public Firebase API for the top story ID list (cheap, indexed).
- Fetch each story's metadata via the same API in parallel (chunked).
- No HTML scraping needed for HN. The public API is the right tool here.
  Many client jobs ask "scrape HN" without knowing the API exists; using it
  is the production answer, not a sign of laziness.
"""
from __future__ import annotations

import asyncio
import logging

from ..client import PoliteClient
from ..models import Item

logger = logging.getLogger(__name__)

API_BASE = "https://hacker-news.firebaseio.com/v0"
DEFAULT_LIMIT = 30


async def _fetch_story(client: PoliteClient, story_id: int) -> Item | None:
    r = await client.get(f"{API_BASE}/item/{story_id}.json")
    if r.status_code != 200:
        logger.warning("HN story %s returned %s, skipping", story_id, r.status_code)
        return None
    data = r.json()
    if data is None or data.get("type") != "story":
        return None
    # Self-posts (Ask HN, Show HN without a link) point at the HN thread itself.
    url = data.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
    return Item(
        source="hackernews",
        title=data.get("title", "(no title)"),
        url=url,
        score=data.get("score"),
        author=data.get("by"),
        comments_count=data.get("descendants"),
        extra={"hn_id": story_id},
    )


async def fetch(client: PoliteClient, limit: int = DEFAULT_LIMIT) -> list[Item]:
    r = await client.get(f"{API_BASE}/topstories.json")
    r.raise_for_status()
    ids: list[int] = r.json()[:limit]

    # Run story fetches concurrently, but PoliteClient enforces per-host pacing,
    # so they end up serialized at the network layer. The gather just keeps the
    # code simple.
    results = await asyncio.gather(*(_fetch_story(client, i) for i in ids))
    return [item for item in results if item is not None]
