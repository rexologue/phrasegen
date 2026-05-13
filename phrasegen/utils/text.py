"""Text utility functions shared by checks, prompts, and deduplication."""

from __future__ import annotations

import re


WORD_RE = re.compile(r"\S+")
CYRILLIC_RE = re.compile(r"[ЁёА-Яа-я]")
LATIN_RE = re.compile(r"[A-Za-z]")
DIGIT_RE = re.compile(r"\d")


def count_words(text: str) -> int:
    """Count whitespace-separated words in text."""
    return len(WORD_RE.findall(text))


def strip_fragments(text: str, fragments: list[str], case_sensitive: bool = True) -> str:
    """Remove configured fragments from text before secondary analysis."""
    result = text
    for fragment in sorted(fragments, key=len, reverse=True):
        if not fragment:
            continue
        if case_sensitive:
            result = result.replace(fragment, " ")
        else:
            result = re.sub(re.escape(fragment), " ", result, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", result).strip()


def count_cyrillic(text: str) -> int:
    """Count Cyrillic characters in text."""
    return len(CYRILLIC_RE.findall(text))


def count_latin(text: str) -> int:
    """Count Latin characters in text."""
    return len(LATIN_RE.findall(text))


def contains_digit(text: str) -> bool:
    """Return whether text contains at least one decimal digit."""
    return bool(DIGIT_RE.search(text))


def format_list(items: list[str], empty: str = "- none") -> str:
    """Render a list as bullet lines for prompt templates."""
    if not items:
        return empty
    return "\n".join(f"- {item}" for item in items)


def format_mapping(mapping: dict[str, list[str]], empty: str = "- none") -> str:
    """Render a mapping of sampled diversity dimensions for prompt templates."""
    if not mapping:
        return empty
    lines: list[str] = []
    for key, values in mapping.items():
        joined = ", ".join(values) if values else "none"
        lines.append(f"- {key}: {joined}")
    return "\n".join(lines)
