"""Registry that builds configured text checks."""

from __future__ import annotations

from phrasegen.checks.base import CheckBuilder, CheckResult, TextCheck
from phrasegen.checks.builtin import (
    CharCountBetweenCheck,
    NoDigitsCheck,
    NoLatinCheck,
    NotInstructionEchoCheck,
    RejectContainsAnyCheck,
    RejectRegexAnyCheck,
    RequireContainsAllCheck,
    RequireContainsAnyCheck,
    RequireDigitsCheck,
    RequireRegexAnyCheck,
    RussianTextCheck,
    WordCountBetweenCheck,
)
from phrasegen.config.entities import CheckConfig


class CheckRegistry:
    """Factory registry for all supported built-in checks."""

    def __init__(self) -> None:
        """Initialize the registry with built-in checks."""
        self._builders: dict[str, CheckBuilder] = {
            "word_count_between": self._build_word_count_between,
            "char_count_between": self._build_char_count_between,
            "require_contains_any": self._build_require_contains_any,
            "require_contains_all": self._build_require_contains_all,
            "reject_contains_any": self._build_reject_contains_any,
            "require_regex_any": self._build_require_regex_any,
            "reject_regex_any": self._build_reject_regex_any,
            "russian_text": self._build_russian_text,
            "no_digits": self._build_no_digits,
            "require_digits": self._build_require_digits,
            "no_latin": self._build_no_latin,
            "not_instruction_echo": self._build_not_instruction_echo,
        }

    def build_many(self, configs: list[CheckConfig]) -> list[TextCheck]:
        """Build a list of checks from config declarations."""
        return [self.build(config) for config in configs]

    def build(self, config: CheckConfig) -> TextCheck:
        """Build one configured check."""
        builder = self._builders.get(config.type)
        if builder is None:
            raise ValueError(f"Unsupported check type: {config.type}")
        return builder(config)

    def supported_types(self) -> list[str]:
        """Return supported check type names."""
        return sorted(self._builders)

    def _build_word_count_between(self, config: CheckConfig) -> TextCheck:
        """Build a word-count range check."""
        return WordCountBetweenCheck(
            min_words=int(config.params["min"]),
            max_words=int(config.params["max"]),
        )

    def _build_char_count_between(self, config: CheckConfig) -> TextCheck:
        """Build a character-count range check."""
        return CharCountBetweenCheck(
            min_chars=int(config.params["min"]),
            max_chars=int(config.params["max"]),
        )

    def _build_require_contains_any(self, config: CheckConfig) -> TextCheck:
        """Build a contains-any requirement check."""
        return RequireContainsAnyCheck(
            values=[str(item) for item in config.params["values"]],
            case_sensitive=bool(config.params.get("case_sensitive", True)),
        )

    def _build_require_contains_all(self, config: CheckConfig) -> TextCheck:
        """Build a contains-all requirement check."""
        return RequireContainsAllCheck(
            values=[str(item) for item in config.params["values"]],
            case_sensitive=bool(config.params.get("case_sensitive", True)),
        )

    def _build_reject_contains_any(self, config: CheckConfig) -> TextCheck:
        """Build a contains-any rejection check."""
        return RejectContainsAnyCheck(
            values=[str(item) for item in config.params["values"]],
            case_sensitive=bool(config.params.get("case_sensitive", True)),
        )

    def _build_require_regex_any(self, config: CheckConfig) -> TextCheck:
        """Build a regex-any requirement check."""
        return RequireRegexAnyCheck(patterns=[str(item) for item in config.params["patterns"]])

    def _build_reject_regex_any(self, config: CheckConfig) -> TextCheck:
        """Build a regex-any rejection check."""
        return RejectRegexAnyCheck(patterns=[str(item) for item in config.params["patterns"]])

    def _build_russian_text(self, config: CheckConfig) -> TextCheck:
        """Build a Russian text context check."""
        return RussianTextCheck(
            min_cyrillic_chars=int(config.params.get("min_cyrillic_chars", 1)),
            max_latin_chars=int(config.params.get("max_latin_chars", 0)),
            allow_latin_inside=[str(item) for item in config.params.get("allow_latin_inside", [])],
        )

    def _build_no_digits(self, config: CheckConfig) -> TextCheck:
        """Build a no-digits check."""
        return NoDigitsCheck()

    def _build_require_digits(self, config: CheckConfig) -> TextCheck:
        """Build a require-digits check."""
        return RequireDigitsCheck()

    def _build_no_latin(self, config: CheckConfig) -> TextCheck:
        """Build a no-Latin check."""
        return NoLatinCheck(allow_inside=[str(item) for item in config.params.get("allow_inside", [])])

    def _build_not_instruction_echo(self, config: CheckConfig) -> TextCheck:
        """Build an instruction-echo rejection check."""
        return NotInstructionEchoCheck(extra_patterns=[str(item) for item in config.params.get("extra_patterns", [])])


class CheckRunner:
    """Runs a sequence of checks against text candidates."""

    def __init__(self, checks: list[TextCheck]) -> None:
        """Store checks in execution order."""
        self.checks = checks

    def validate(self, text: str) -> CheckResult:
        """Return the first failed check result or success."""
        for check in self.checks:
            result = check.validate(text)
            if not result.accepted:
                return CheckResult.reject(f"{check.name}:{result.reason}")
        return CheckResult.ok()

    def describe(self) -> list[str]:
        """Return prompt-ready descriptions of all checks."""
        return [check.describe() for check in self.checks]
