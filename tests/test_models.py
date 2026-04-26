"""Schema-level tests for the unified Item model."""
from datetime import datetime, timezone

from tech_radar.models import Item


def test_item_dedup_key_normalizes_trailing_slash_and_case():
    a = Item(source="hackernews", title="A", url="https://Example.com/Foo/")
    b = Item(source="github_trending", title="B", url="https://example.com/foo")
    assert a.dedup_key() == b.dedup_key()


def test_item_default_fetched_at_is_utc_aware():
    a = Item(source="hackernews", title="x", url="https://example.com/")
    assert a.fetched_at.tzinfo is not None
    assert a.fetched_at.tzinfo.utcoffset(a.fetched_at) == timezone.utc.utcoffset(
        datetime.now(timezone.utc)
    )


def test_item_extra_dict_accepts_strings_and_ints():
    a = Item(
        source="github_trending",
        title="x",
        url="https://example.com/",
        extra={"language": "Python", "stars_gained_recent": 120},
    )
    assert a.extra["language"] == "Python"
    assert a.extra["stars_gained_recent"] == 120
