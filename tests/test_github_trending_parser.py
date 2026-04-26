"""Parser test: feed a frozen GitHub Trending HTML snippet and verify the parsed
fields. This guards against silent breakage when GitHub changes the layout."""
from unittest.mock import patch

import httpx
import pytest

from tech_radar.client import PoliteClient
from tech_radar.sources import github_trending

# A minimal, frozen excerpt of the GitHub Trending HTML structure as of mid-2026.
# If GitHub redesigns this page, update this fixture and the four selectors in
# tech_radar/sources/github_trending.py.
SAMPLE_HTML = """
<html><body>
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/microsoft/typescript">microsoft / typescript</a>
  </h2>
  <p class="col-9 color-fg-muted my-1 pr-4">TypeScript is a superset of JavaScript that compiles to clean output.</p>
  <div class="f6 color-fg-muted mt-2">
    <span class="d-inline-block ml-0 mr-3" itemprop="programmingLanguage">TypeScript</span>
    <a href="/microsoft/typescript/stargazers" class="Link Link--muted d-inline-block mr-3">98,234</a>
    <span class="d-inline-block float-sm-right">
      <svg class="octicon octicon-star" /> 124 stars today
    </span>
  </div>
</article>
<article class="Box-row">
  <h2 class="h3 lh-condensed">
    <a href="/openai/gpt-something">openai / gpt-something</a>
  </h2>
  <p class="col-9 color-fg-muted my-1 pr-4">A demo project.</p>
  <div class="f6 color-fg-muted mt-2">
    <span class="d-inline-block ml-0 mr-3" itemprop="programmingLanguage">Python</span>
    <a href="/openai/gpt-something/stargazers" class="Link Link--muted d-inline-block mr-3">1.2k</a>
  </div>
</article>
</body></html>
"""


@pytest.mark.asyncio
async def test_parse_two_trending_repos():
    async with PoliteClient(per_host_delay=0) as client:
        # Patch the underlying HTTP request, not the parser, so the parsing logic
        # runs against the real BeautifulSoup pipeline.
        with patch.object(
            client,
            "get",
            return_value=httpx.Response(200, text=SAMPLE_HTML, request=httpx.Request("GET", "https://github.com/trending")),
        ):
            items = await github_trending.fetch(client)

    assert len(items) == 2
    a, b = items
    assert a.source == "github_trending"
    assert str(a.url) == "https://github.com/microsoft/typescript"
    assert a.title == "microsoft/typescript"
    assert a.score == 98234
    assert a.author == "microsoft"
    assert a.extra.get("language") == "TypeScript"
    assert a.extra.get("stars_gained_recent") == 124

    assert b.score == 1200  # '1.2k'
    assert b.extra.get("stars_gained_recent") is None
