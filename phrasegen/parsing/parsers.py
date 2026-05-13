"""Parsers that convert raw model responses into candidate texts."""

from __future__ import annotations

import json
import re
from typing import Protocol


class ResponseParser(Protocol):
    """Protocol implemented by all response parsers."""

    name: str

    def parse(self, raw_text: str) -> list[str]:
        """Parse raw model output into text candidates."""
        ...


class JsonArrayParser:
    """Parse a model response as a JSON array of strings."""

    name = "json_array"

    def parse(self, raw_text: str) -> list[str]:
        """Parse JSON array output and keep only string items."""
        payload = self._load_json_array(raw_text)
        return [item.strip() for item in payload if isinstance(item, str) and item.strip()]

    def _load_json_array(self, raw_text: str) -> list[object]:
        """Load a JSON array, tolerating text around the outer array."""
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            parsed = self._load_embedded_array(raw_text)
        if not isinstance(parsed, list):
            raise ValueError("Model response is not a JSON array")
        return parsed

    def _load_embedded_array(self, raw_text: str) -> list[object]:
        """Extract and parse the broadest embedded JSON array."""
        start = raw_text.find("[")
        end = raw_text.rfind("]")
        if start < 0 or end <= start:
            raise ValueError("Model response does not contain a JSON array")
        return json.loads(raw_text[start : end + 1])


class AnswerTagsParser:
    """Parse candidates wrapped in <answer>...</answer> tags."""

    name = "answer_tags"
    pattern = re.compile(r"<answer>\s*(.*?)\s*</answer>", re.IGNORECASE | re.DOTALL)

    def parse(self, raw_text: str) -> list[str]:
        """Parse answer-tag output."""
        results: list[str] = []
        for match in self.pattern.findall(raw_text):
            text = re.sub(r"\s+", " ", match).strip().strip("\"'")
            if text:
                results.append(text)
        return results


class LinesParser:
    """Parse non-empty response lines as candidates."""

    name = "lines"

    def parse(self, raw_text: str) -> list[str]:
        """Parse line-based output."""
        results: list[str] = []
        for line in raw_text.splitlines():
            text = line.strip().lstrip("-*0123456789. )\t").strip()
            if text:
                results.append(text)
        return results


class ParserFactory:
    """Factory for supported response parsers."""

    def create(self, parser_type: str) -> ResponseParser:
        """Create a parser by type name."""
        if parser_type == "json_array":
            return JsonArrayParser()
        if parser_type == "answer_tags":
            return AnswerTagsParser()
        if parser_type == "lines":
            return LinesParser()
        raise ValueError(f"Unsupported parser type: {parser_type}")
