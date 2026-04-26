"""GitHub Trending repositories (HTML scraping).

GitHub does not expose a public API for the trending list. The page is server-
rendered HTML so a single request returns everything. No JavaScript needed.

We parse:
- Repo owner/name
- Description
- Primary language
- Star count
- Stars gained "today" / "this week"

The selectors below are stable within a layout version. When GitHub redesigns
this page (rare but it happens), update the four CSS selectors here. Because
this module is a thin parser around HTML, that change stays small and local.
"""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from ..client import PoliteClient
from ..models import Item

logger = logging.getLogger(__name__)

URL = "https://github.com/trending"


def _parse_int(s: str) -> int | None:
    """Parse '1,234' or '1.2k' style counts. Returns None if it cannot."""
    s = s.strip().replace(",", "")
    m = re.match(r"^([\d.]+)([kKmM]?)$", s)
    if not m:
        return None
    n = float(m.group(1))
    suffix = m.group(2).lower()
    if suffix == "k":
        n *= 1_000
    elif suffix == "m":
        n *= 1_000_000
    return int(n)


async def fetch(client: PoliteClient, language: str | None = None) -> list[Item]:
    url = URL if language is None else f"{URL}/{language}"
    r = await client.get(url)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")
    items: list[Item] = []

    for article in soup.select("article.Box-row"):
        link = article.select_one("h2 a")
        if link is None:
            continue
        href = link.get("href", "").strip()
        if not href:
            continue
        slug = href.strip("/")  # 'owner/repo'
        title = slug

        repo_url = f"https://github.com/{slug}"

        desc_el = article.select_one("p")
        description = desc_el.get_text(strip=True) if desc_el else None

        lang_el = article.select_one('[itemprop="programmingLanguage"]')
        language_name = lang_el.get_text(strip=True) if lang_el else None

        # Star count: first <a> with href ending in /stargazers
        star_el = article.select_one('a[href$="/stargazers"]')
        stars = _parse_int(star_el.get_text(strip=True)) if star_el else None

        # Stars gained recently: span with svg.octicon-star inside the bottom row
        gained = None
        for span in article.select("div.f6 span.d-inline-block"):
            txt = span.get_text(strip=True)
            m = re.search(r"([\d,.]+)\s+stars?\s+(today|this week|this month)", txt)
            if m:
                gained = _parse_int(m.group(1))
                break

        owner, _, _name = slug.partition("/")
        items.append(
            Item(
                source="github_trending",
                title=title,
                url=repo_url,
                score=stars,
                author=owner,
                comments_count=None,
                extra={
                    k: v
                    for k, v in {
                        "description": description,
                        "language": language_name,
                        "stars_gained_recent": gained,
                    }.items()
                    if v is not None
                },
            )
        )

    logger.info("github_trending parsed %d items", len(items))
    return items
