"""CSV and JSON writers."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from .models import Item

CSV_COLUMNS = [
    "source",
    "title",
    "url",
    "score",
    "author",
    "comments_count",
    "fetched_at",
    "extra",
]


def write_json(items: Iterable[Item], path: str | Path) -> int:
    items = list(items)
    Path(path).write_text(
        json.dumps(
            [item.model_dump(mode="json") for item in items],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return len(items)


def write_csv(items: Iterable[Item], path: str | Path) -> int:
    items = list(items)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for item in items:
            row = item.model_dump(mode="json")
            row["url"] = str(row["url"])
            row["extra"] = json.dumps(row["extra"], ensure_ascii=False)
            writer.writerow(row)
    return len(items)
