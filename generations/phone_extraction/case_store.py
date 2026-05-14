"""JSONL-backed storage helpers for phone extraction callbacks."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class PhoneCaseStore:
    """Loads phone variants and serves them by index or case id."""

    def __init__(self, cases_path: Path) -> None:
        """Load cases from a JSONL file."""
        self.cases_path = cases_path
        self.cases = self._load_cases(cases_path)
        self.by_id = {str(case["case_id"]): case for case in self.cases}

    def by_index(self, index: int) -> dict[str, Any]:
        """Return a case by cyclic index."""
        if not self.cases:
            raise ValueError(f"No cases found in {self.cases_path}")
        return self.cases[index % len(self.cases)]

    def get(self, case_id: str) -> dict[str, Any]:
        """Return a case by id."""
        case = self.by_id.get(case_id)
        if case is None:
            raise KeyError(f"Unknown phone extraction case_id: {case_id}")
        return case

    def _load_cases(self, path: Path) -> list[dict[str, Any]]:
        """Load all JSONL cases from disk."""
        if not path.exists():
            raise FileNotFoundError(f"Phone extraction cases file not found: {path}")
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as file_obj:
            for line_number, line in enumerate(file_obj, 1):
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    raise ValueError(f"Invalid case row at {path}:{line_number}")
                rows.append(obj)
        return rows


def count_jsonl_rows(path: Path) -> int:
    """Count non-empty lines in a JSONL file."""
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as file_obj:
        return sum(1 for line in file_obj if line.strip())


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    """Append one JSON payload to a UTF-8 JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file_obj:
        file_obj.write(json.dumps(payload, ensure_ascii=False) + "\n")


def now_payload() -> dict[str, float]:
    """Return a small timestamp payload for JSONL bookkeeping."""
    return {"created_at_unix": time.time()}
