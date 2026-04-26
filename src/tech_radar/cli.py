"""Typer-based CLI: `tech-radar fetch --output report.csv`."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .client import PoliteClient
from .models import Item
from .output import write_csv, write_json
from .sources import REGISTRY

app = typer.Typer(
    add_completion=False,
    help="Daily tech launch aggregator. Scrapes Hacker News and GitHub Trending into a unified feed.",
)
console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _dedup(items: list[Item]) -> list[Item]:
    """Collapse items with the same canonical URL. The first occurrence wins,
    later sources contribute their score under `extra` for visibility."""
    seen: dict[str, Item] = {}
    for item in items:
        key = item.dedup_key()
        if key in seen:
            other = seen[key]
            if item.score is not None:
                other.extra[f"{item.source}_score"] = item.score
        else:
            seen[key] = item
    return list(seen.values())


async def _run(sources: list[str], hn_limit: int, gh_lang: str | None) -> list[Item]:
    async with PoliteClient(per_host_delay=0.6) as client:
        all_items: list[Item] = []
        for name in sources:
            fetcher = REGISTRY[name]
            console.log(f"[cyan]fetching[/cyan] {name}")
            try:
                if name == "hackernews":
                    items = await fetcher(client, limit=hn_limit)
                elif name == "github_trending":
                    items = await fetcher(client, language=gh_lang)
                else:
                    items = await fetcher(client)
            except Exception as e:  # noqa: BLE001
                console.log(f"[red]{name} failed:[/red] {e}")
                continue
            console.log(f"[green]{name}[/green]: {len(items)} items")
            all_items.extend(items)
        return _dedup(all_items)


@app.command()
def fetch(
    output: Path = typer.Option(
        Path("tech-radar.csv"), "--output", "-o", help="Output file (.csv or .json)"
    ),
    sources: list[str] = typer.Option(
        ["hackernews", "github_trending"], "--source", "-s", help="Sources to fetch"
    ),
    hn_limit: int = typer.Option(30, "--hn-limit", help="HN top stories to pull"),
    gh_lang: str | None = typer.Option(None, "--gh-lang", help="GitHub trending language filter"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Fetch all sources and write a deduplicated CSV or JSON file."""
    _setup_logging(verbose)
    items = asyncio.run(_run(sources, hn_limit, gh_lang))

    if output.suffix == ".json":
        n = write_json(items, output)
    else:
        n = write_csv(items, output)

    console.print(f"[bold green]wrote[/bold green] {n} items to [bold]{output}[/bold]")


@app.command()
def preview(
    sources: list[str] = typer.Option(
        ["hackernews", "github_trending"], "--source", "-s"
    ),
    hn_limit: int = typer.Option(10, "--hn-limit"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Fetch and print a table to the terminal. Nothing is written to disk."""
    _setup_logging(verbose)
    items = asyncio.run(_run(sources, hn_limit, None))

    table = Table(title="tech-radar preview", show_lines=False)
    table.add_column("Source", style="cyan", no_wrap=True)
    table.add_column("Score", style="magenta", justify="right")
    table.add_column("Title", style="white")

    items.sort(key=lambda i: i.score or 0, reverse=True)
    for item in items[:30]:
        table.add_row(item.source, str(item.score or "-"), item.title)
    console.print(table)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
