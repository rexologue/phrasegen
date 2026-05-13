"""Callback contracts used by the generator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


PreExtensionCallback = Callable[[str], str]
PostValidationCallback = Callable[[str], tuple[bool, str]]


@dataclass
class PostValidationResult:
    """Normalized result of a post-validation callback."""

    accepted: bool
    reason: str = ""

    @classmethod
    def ok(cls) -> "PostValidationResult":
        """Create a successful post-validation result."""
        return cls(accepted=True, reason="")

    @classmethod
    def reject(cls, reason: str) -> "PostValidationResult":
        """Create a failed post-validation result."""
        return cls(accepted=False, reason=reason)


class PreExtensionChain:
    """Applies prompt-extension callbacks in order."""

    def __init__(self, callbacks: list[PreExtensionCallback]) -> None:
        """Store callbacks in execution order."""
        self.callbacks = callbacks

    def apply(self, prompt: str) -> str:
        """Apply each pre-extension callback to the prompt."""
        result = prompt
        for callback in self.callbacks:
            result = callback(result)
            if not isinstance(result, str):
                raise TypeError("PreExtensionCallback must return str")
        return result


class PostValidationChain:
    """Applies post-validation callbacks in order."""

    def __init__(self, callbacks: list[PostValidationCallback]) -> None:
        """Store callbacks in execution order."""
        self.callbacks = callbacks

    def validate(self, text: str) -> PostValidationResult:
        """Return the first callback rejection or success."""
        for callback in self.callbacks:
            raw_result = callback(text)
            result = self._normalize_result(raw_result)
            if not result.accepted:
                return result
        return PostValidationResult.ok()

    def _normalize_result(self, raw_result: tuple[bool, str]) -> PostValidationResult:
        """Validate and normalize a callback return value."""
        if not isinstance(raw_result, tuple) or len(raw_result) != 2:
            raise TypeError("PostValidationCallback must return tuple[bool, str]")
        accepted, reason = raw_result
        if not isinstance(accepted, bool):
            raise TypeError("PostValidationCallback first return value must be bool")
        if not isinstance(reason, str):
            raise TypeError("PostValidationCallback second return value must be str")
        return PostValidationResult(accepted=accepted, reason=reason)
