"""Callback contracts used by the generator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypeAlias


CallbackAnchor: TypeAlias = str
PreExtensionReturn: TypeAlias = str | tuple[str, CallbackAnchor | None]
PreExtensionCallback = Callable[[str], PreExtensionReturn]
PostValidationCallback = Callable[..., tuple[bool, str]]


@dataclass
class PreExtensionResult:
    """Normalized result of pre-extension callbacks."""

    prompt: str
    anchor: CallbackAnchor | None = None


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

    def apply(self, prompt: str) -> PreExtensionResult:
        """Apply each pre-extension callback to the prompt."""
        result = prompt
        anchor: CallbackAnchor | None = None
        for callback in self.callbacks:
            callback_result = self._normalize_result(callback(result))
            result = callback_result.prompt
            if callback_result.anchor is not None:
                if anchor is not None and anchor != callback_result.anchor:
                    raise TypeError("Only one distinct callback anchor is supported per prompt")
                anchor = callback_result.anchor
        return PreExtensionResult(prompt=result, anchor=anchor)

    def _normalize_result(self, raw_result: PreExtensionReturn) -> PreExtensionResult:
        """Validate and normalize a pre-extension callback return value."""
        if isinstance(raw_result, str):
            return PreExtensionResult(prompt=raw_result)
        if not isinstance(raw_result, tuple) or len(raw_result) != 2:
            raise TypeError("PreExtensionCallback must return str or tuple[str, str | None]")
        prompt, anchor = raw_result
        if not isinstance(prompt, str):
            raise TypeError("PreExtensionCallback prompt return value must be str")
        if anchor is not None and not isinstance(anchor, str):
            raise TypeError("PreExtensionCallback anchor return value must be str or None")
        return PreExtensionResult(prompt=prompt, anchor=anchor)


class PostValidationChain:
    """Applies post-validation callbacks in order."""

    def __init__(self, callbacks: list[PostValidationCallback]) -> None:
        """Store callbacks in execution order."""
        self.callbacks = callbacks

    def validate(self, text: str, anchor: CallbackAnchor | None = None) -> PostValidationResult:
        """Return the first callback rejection or success."""
        for callback in self.callbacks:
            raw_result = callback(text, anchor) if anchor is not None else callback(text)
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
