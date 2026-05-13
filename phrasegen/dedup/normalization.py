"""Text normalization for deduplication."""

from __future__ import annotations

import re

from phrasegen.config.entities import NormalizationConfig


TRIM_PUNCTUATION = " \t\r\n.,;:!?\"'`«»()[]{}"


class TextNormalizer:
    """Normalize text consistently for deduplication checks."""

    def __init__(self, config: NormalizationConfig) -> None:
        """Store normalization settings."""
        self.config = config

    def normalize(self, text: str) -> str:
        """Apply configured normalization operations to text."""
        value = text.strip()
        if self.config.collapse_spaces:
            value = re.sub(r"\s+", " ", value)
        if self.config.replace_yo:
            value = value.replace("ё", "е").replace("Ё", "Е")
        if self.config.lowercase:
            value = value.lower()
        if self.config.trim_punctuation:
            value = value.strip(TRIM_PUNCTUATION)
        return value

    def prefix_key(self, text: str, words: int) -> str:
        """Return the normalized first N words of text."""
        tokens = re.findall(r"\S+", self.normalize(text))
        return " ".join(tokens[:words])


def char_ngrams(text: str, ngram: int) -> set[str]:
    """Return character n-grams for similarity checks."""
    compact = re.sub(r"\s+", " ", text.strip())
    if not compact:
        return set()
    if len(compact) <= ngram:
        return {compact}
    return {compact[index : index + ngram] for index in range(0, len(compact) - ngram + 1)}


def jaccard(left: set[str], right: set[str]) -> float:
    """Compute Jaccard similarity for two sets."""
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)
