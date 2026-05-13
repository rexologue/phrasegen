"""Base types for text checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from phrasegen.config.entities import CheckConfig


@dataclass
class CheckResult:
    """Result of one text check."""

    accepted: bool
    reason: str = ""

    @classmethod
    def ok(cls) -> "CheckResult":
        """Create a successful check result."""
        return cls(accepted=True, reason="")

    @classmethod
    def reject(cls, reason: str) -> "CheckResult":
        """Create a failed check result with a machine-readable reason."""
        return cls(accepted=False, reason=reason)


class TextCheck(Protocol):
    """Protocol implemented by all built-in text checks."""

    name: str

    def validate(self, text: str) -> CheckResult:
        """Validate one text candidate."""
        ...

    def describe(self) -> str:
        """Return a human-readable check description for prompts and reports."""
        ...


class CheckBuilder(Protocol):
    """Protocol for factory functions that create checks from config."""

    def __call__(self, config: CheckConfig) -> TextCheck:
        """Build a check from its configuration."""
        ...
