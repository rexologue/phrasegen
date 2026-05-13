"""Example callbacks for config files."""

from __future__ import annotations


def add_workplace_hint(prompt: str) -> str:
    """Append a small prompt hint before the API request."""
    return prompt + "\n\nAdditional instruction: prefer natural workplace wording."


def reject_placeholder_text(text: str) -> tuple[bool, str]:
    """Reject obvious placeholder candidates."""
    lowered = text.lower()
    if "lorem" in lowered or "placeholder" in lowered:
        return False, "placeholder_text"
    return True, ""
