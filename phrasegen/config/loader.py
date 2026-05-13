"""YAML configuration loader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from phrasegen.config.entities import ProjectConfig


def load_project_config(path: Path) -> ProjectConfig:
    """Load a UTF-8 YAML config file into a typed project config."""
    resolved_path = path.resolve()
    with resolved_path.open("r", encoding="utf-8") as file_obj:
        raw = yaml.safe_load(file_obj) or {}
    _ensure_mapping(raw, "root")
    return ProjectConfig.from_dict(raw, resolved_path)


def _ensure_mapping(value: Any, name: str) -> None:
    """Raise a clear error if a config section is not a mapping."""
    if not isinstance(value, dict):
        raise TypeError(f"Config section '{name}' must be a mapping")
