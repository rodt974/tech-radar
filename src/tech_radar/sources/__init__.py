"""Source adapters. Each module exposes an async `fetch(client) -> list[Item]`."""

from . import github_trending, hackernews

REGISTRY = {
    "hackernews": hackernews.fetch,
    "github_trending": github_trending.fetch,
}
