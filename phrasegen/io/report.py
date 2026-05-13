"""Mutable run report written as one JSON file."""

from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RuleReport:
    """Mutable report section for one rule."""

    rule_id: str
    target: int
    status: str = "pending"
    accepted: int = 0
    api_requests: int = 0
    parsed_candidates: int = 0
    rejected: Counter[str] = field(default_factory=Counter)
    errors: Counter[str] = field(default_factory=Counter)
    rejection_samples: list[dict[str, Any]] = field(default_factory=list)
    started_at_unix: float | None = None
    updated_at_unix: float | None = None
    finished_at_unix: float | None = None

    def to_json(self) -> dict[str, Any]:
        """Return a JSON-safe rule report."""
        return {
            "rule_id": self.rule_id,
            "target": self.target,
            "status": self.status,
            "accepted": self.accepted,
            "remaining": max(self.target - self.accepted, 0),
            "api_requests": self.api_requests,
            "parsed_candidates": self.parsed_candidates,
            "rejected": dict(self.rejected),
            "errors": dict(self.errors),
            "rejection_samples": self.rejection_samples,
            "started_at_unix": self.started_at_unix,
            "updated_at_unix": self.updated_at_unix,
            "finished_at_unix": self.finished_at_unix,
        }


class RunReport:
    """Top-level mutable report for the whole generator run."""

    def __init__(self, path: Path, run_name: str, model: str, rejection_sample_limit: int) -> None:
        """Initialize a report at a target path."""
        self.path = path
        self.run_name = run_name
        self.model = model
        self.rejection_sample_limit = rejection_sample_limit
        self.status = "pending"
        self.started_at_unix = time.time()
        self.updated_at_unix = self.started_at_unix
        self.finished_at_unix: float | None = None
        self.rules: dict[str, RuleReport] = {}

    def ensure_rule(self, rule_id: str, target: int) -> RuleReport:
        """Return an existing rule report or create a new one."""
        if rule_id not in self.rules:
            self.rules[rule_id] = RuleReport(rule_id=rule_id, target=target)
        return self.rules[rule_id]

    def mark_running(self) -> None:
        """Mark the run as running and persist the report."""
        self.status = "running"
        self.touch()

    def mark_done(self) -> None:
        """Mark the run as complete and persist the report."""
        self.mark_finished("done")

    def mark_finished(self, status: str) -> None:
        """Mark the run as finished with a specific terminal status."""
        self.status = status
        self.finished_at_unix = time.time()
        self.touch()

    def mark_failed(self, error: str) -> None:
        """Mark the run as failed and persist the error."""
        self.status = "failed"
        self.finished_at_unix = time.time()
        payload = self.to_json()
        payload["fatal_error"] = error
        self._write(payload)

    def add_rejection_sample(self, rule_id: str, sample: dict[str, Any]) -> None:
        """Add a bounded rejection sample to a rule report."""
        report = self.rules[rule_id]
        if len(report.rejection_samples) < self.rejection_sample_limit:
            report.rejection_samples.append(sample)

    def touch(self) -> None:
        """Update timestamps and persist the report."""
        self.updated_at_unix = time.time()
        self._write(self.to_json())

    def to_json(self) -> dict[str, Any]:
        """Return a JSON-safe report payload."""
        accepted_total = sum(rule.accepted for rule in self.rules.values())
        target_total = sum(rule.target for rule in self.rules.values())
        return {
            "run_name": self.run_name,
            "status": self.status,
            "model": self.model,
            "started_at_unix": self.started_at_unix,
            "updated_at_unix": self.updated_at_unix,
            "finished_at_unix": self.finished_at_unix,
            "totals": {
                "target": target_total,
                "accepted": accepted_total,
                "remaining": max(target_total - accepted_total, 0),
            },
            "rules": {rule_id: report.to_json() for rule_id, report in self.rules.items()},
        }

    def _write(self, payload: dict[str, Any]) -> None:
        """Write the report JSON atomically enough for local runs."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(self.path)
