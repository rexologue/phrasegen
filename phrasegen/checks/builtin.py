"""Built-in check implementations."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from phrasegen.checks.base import CheckResult
from phrasegen.utils.text import contains_digit, count_cyrillic, count_latin, count_words, strip_fragments


@dataclass
class WordCountBetweenCheck:
    """Check that the candidate word count is inside an inclusive range."""

    min_words: int
    max_words: int
    name: str = "word_count_between"

    def validate(self, text: str) -> CheckResult:
        """Validate the candidate word count."""
        word_count = count_words(text)
        if word_count < self.min_words:
            return CheckResult.reject("too_few_words")
        if word_count > self.max_words:
            return CheckResult.reject("too_many_words")
        return CheckResult.ok()

    def describe(self) -> str:
        """Describe the word count requirement."""
        return f"word count must be between {self.min_words} and {self.max_words}"


@dataclass
class CharCountBetweenCheck:
    """Check that the candidate character count is inside an inclusive range."""

    min_chars: int
    max_chars: int
    name: str = "char_count_between"

    def validate(self, text: str) -> CheckResult:
        """Validate the candidate character count."""
        char_count = len(text)
        if char_count < self.min_chars:
            return CheckResult.reject("too_few_chars")
        if char_count > self.max_chars:
            return CheckResult.reject("too_many_chars")
        return CheckResult.ok()

    def describe(self) -> str:
        """Describe the character count requirement."""
        return f"character count must be between {self.min_chars} and {self.max_chars}"


@dataclass
class RequireContainsAnyCheck:
    """Check that text contains at least one configured fragment."""

    values: list[str]
    case_sensitive: bool = True
    name: str = "require_contains_any"

    def validate(self, text: str) -> CheckResult:
        """Validate that at least one fragment is present."""
        haystack = text if self.case_sensitive else text.lower()
        needles = self.values if self.case_sensitive else [value.lower() for value in self.values]
        if any(value in haystack for value in needles):
            return CheckResult.ok()
        return CheckResult.reject("missing_required_fragment")

    def describe(self) -> str:
        """Describe the required fragment set."""
        return f"must contain at least one of: {', '.join(self.values)}"


@dataclass
class RequireContainsAllCheck:
    """Check that text contains every configured fragment."""

    values: list[str]
    case_sensitive: bool = True
    name: str = "require_contains_all"

    def validate(self, text: str) -> CheckResult:
        """Validate that every fragment is present."""
        haystack = text if self.case_sensitive else text.lower()
        needles = self.values if self.case_sensitive else [value.lower() for value in self.values]
        if all(value in haystack for value in needles):
            return CheckResult.ok()
        return CheckResult.reject("missing_required_fragment")

    def describe(self) -> str:
        """Describe the required fragment list."""
        return f"must contain all of: {', '.join(self.values)}"


@dataclass
class RejectContainsAnyCheck:
    """Check that text contains none of the configured fragments."""

    values: list[str]
    case_sensitive: bool = True
    name: str = "reject_contains_any"

    def validate(self, text: str) -> CheckResult:
        """Validate that forbidden fragments are absent."""
        haystack = text if self.case_sensitive else text.lower()
        needles = self.values if self.case_sensitive else [value.lower() for value in self.values]
        if any(value in haystack for value in needles):
            return CheckResult.reject("forbidden_fragment")
        return CheckResult.ok()

    def describe(self) -> str:
        """Describe the forbidden fragment set."""
        return f"must not contain any of: {', '.join(self.values)}"


@dataclass
class RequireRegexAnyCheck:
    """Check that text matches at least one configured regex pattern."""

    patterns: list[str]
    name: str = "require_regex_any"
    compiled: list[re.Pattern[str]] = field(init=False)

    def __post_init__(self) -> None:
        """Compile regex patterns once during check initialization."""
        self.compiled = [re.compile(pattern) for pattern in self.patterns]

    def validate(self, text: str) -> CheckResult:
        """Validate that at least one regex pattern matches."""
        if any(pattern.search(text) for pattern in self.compiled):
            return CheckResult.ok()
        return CheckResult.reject("regex_required_pattern_missing")

    def describe(self) -> str:
        """Describe the required regex set."""
        return f"must match at least one regex: {', '.join(self.patterns)}"


@dataclass
class RejectRegexAnyCheck:
    """Check that text matches none of the configured regex patterns."""

    patterns: list[str]
    name: str = "reject_regex_any"
    compiled: list[re.Pattern[str]] = field(init=False)

    def __post_init__(self) -> None:
        """Compile regex patterns once during check initialization."""
        self.compiled = [re.compile(pattern) for pattern in self.patterns]

    def validate(self, text: str) -> CheckResult:
        """Validate that no forbidden regex pattern matches."""
        if any(pattern.search(text) for pattern in self.compiled):
            return CheckResult.reject("forbidden_regex")
        return CheckResult.ok()

    def describe(self) -> str:
        """Describe the forbidden regex set."""
        return f"must not match any regex: {', '.join(self.patterns)}"


@dataclass
class RussianTextCheck:
    """Check that text has enough Cyrillic context and limited foreign text."""

    min_cyrillic_chars: int = 1
    max_latin_chars: int = 0
    allow_latin_inside: list[str] = field(default_factory=list)
    name: str = "russian_text"

    def validate(self, text: str) -> CheckResult:
        """Validate Russian-context constraints."""
        stripped = strip_fragments(text, self.allow_latin_inside, case_sensitive=True)
        if count_cyrillic(stripped) < self.min_cyrillic_chars:
            return CheckResult.reject("not_enough_cyrillic")
        if count_latin(stripped) > self.max_latin_chars:
            return CheckResult.reject("too_much_latin")
        return CheckResult.ok()

    def describe(self) -> str:
        """Describe the Russian text requirement."""
        return (
            "must be Russian-context text with at least "
            f"{self.min_cyrillic_chars} Cyrillic chars and at most {self.max_latin_chars} Latin chars"
        )


@dataclass
class NoDigitsCheck:
    """Check that text contains no decimal digits."""

    name: str = "no_digits"

    def validate(self, text: str) -> CheckResult:
        """Validate that digits are absent."""
        if contains_digit(text):
            return CheckResult.reject("digits_present")
        return CheckResult.ok()

    def describe(self) -> str:
        """Describe the no-digits requirement."""
        return "must not contain decimal digits"


@dataclass
class RequireDigitsCheck:
    """Check that text contains at least one decimal digit."""

    name: str = "require_digits"

    def validate(self, text: str) -> CheckResult:
        """Validate that at least one digit is present."""
        if contains_digit(text):
            return CheckResult.ok()
        return CheckResult.reject("digits_missing")

    def describe(self) -> str:
        """Describe the digit requirement."""
        return "must contain at least one decimal digit"


@dataclass
class NoLatinCheck:
    """Check that text contains no Latin characters outside allowed fragments."""

    allow_inside: list[str] = field(default_factory=list)
    name: str = "no_latin"

    def validate(self, text: str) -> CheckResult:
        """Validate that Latin characters are absent outside allowed fragments."""
        stripped = strip_fragments(text, self.allow_inside, case_sensitive=True)
        if count_latin(stripped) > 0:
            return CheckResult.reject("latin_present")
        return CheckResult.ok()

    def describe(self) -> str:
        """Describe the no-Latin requirement."""
        if self.allow_inside:
            return f"must not contain Latin characters outside: {', '.join(self.allow_inside)}"
        return "must not contain Latin characters"


@dataclass
class NotInstructionEchoCheck:
    """Check that text does not look like a prompt, instruction, or format echo."""

    extra_patterns: list[str] = field(default_factory=list)
    name: str = "not_instruction_echo"
    compiled: list[re.Pattern[str]] = field(init=False)

    def __post_init__(self) -> None:
        """Compile the default and configured echo-detection patterns."""
        patterns = [
            r"\bjson\b",
            r"\bmarkdown\b",
            r"\boutput\b",
            r"\bformat\b",
            r"\breturn\b",
            r"\bprompt\b",
            r"\binstruction\b",
            r"\brule\b",
            r"\bexample\b",
            r"\bgenerate\b",
            r"\bсгенерируй\b",
            r"\bверни\b",
            r"\bформат\b",
            r"\bинструкц",
        ]
        self.compiled = [re.compile(pattern, re.IGNORECASE) for pattern in patterns + self.extra_patterns]

    def validate(self, text: str) -> CheckResult:
        """Validate that text does not look like instruction leakage."""
        if text.startswith(("-", "*")):
            return CheckResult.reject("list_item_echo")
        if "\n" in text:
            return CheckResult.reject("multiline_echo")
        if any(pattern.search(text) for pattern in self.compiled):
            return CheckResult.reject("instruction_echo")
        return CheckResult.ok()

    def describe(self) -> str:
        """Describe the instruction-echo filter."""
        return "must not echo prompts, formatting instructions, markdown, or metadata"
