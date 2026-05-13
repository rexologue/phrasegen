"""JSONL input and output helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonlWriter:
    """Buffered JSONL writer that appends UTF-8 records."""

    def __init__(self, path: Path, flush_every: int) -> None:
        """Initialize writer with a target path and flush threshold."""
        self.path = path
        self.flush_every = flush_every
        self.buffer: list[dict[str, Any]] = []
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict[str, Any]) -> None:
        """Append one record and flush when the buffer is full."""
        self.buffer.append(record)
        if len(self.buffer) >= self.flush_every:
            self.flush()

    def flush(self) -> None:
        """Write buffered records to disk."""
        if not self.buffer:
            return
        with self.path.open("a", encoding="utf-8") as file_obj:
            for record in self.buffer:
                file_obj.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.buffer.clear()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSONL records, skipping blank or invalid lines."""
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file_obj:
        for line in file_obj:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def truncate_file(path: Path) -> None:
    """Create or truncate a UTF-8 text file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
