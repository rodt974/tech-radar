"""Unified item schema across all sources."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


SourceName = Literal["hackernews", "github_trending"]


class Item(BaseModel):
    """One scraped item, normalized across sources.

    Every source maps its native fields onto this shape. Anything the source
    does not provide stays None. Downstream consumers (CSV / JSON writers,
    deduplication) only ever see this schema.
    """

    source: SourceName
    title: str
    url: HttpUrl
    score: int | None = None
    author: str | None = None
    comments_count: int | None = None
    extra: dict[str, str | int] = Field(default_factory=dict)
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def dedup_key(self) -> str:
        """URL is the canonical dedup key. Two items pointing to the same target
        URL across sources collapse into one downstream."""
        return str(self.url).rstrip("/").lower()
