"""Post-validation callbacks for the targeted phrases generation pack."""

from __future__ import annotations

import re


QUESTION_MARKERS = ("Окей?", "Хорошо?", "Договорились?", "Алло?", "Понятно?")

WRITTEN_STYLE_PATTERNS = (
    r"^\s*[-*0-9]+[.)\s]",
    r"\bjson\b",
    r"\bmarkdown\b",
    r"\bprompt\b",
    r"\brule\b",
    r"\bexample\b",
    r"\bсгенерируй\b",
    r"\bверни\b",
    r"\bфраза\s+с\b",
    r"\bобязательн\w*\s+(?:слов|термин|фрагмент)",
)


def validate_sahara_phrase(text: str) -> tuple[bool, str]:
    """Validate a phrase that must contain the exact phrase пустыня Сахара."""
    return _validate_required_fragment(text, "пустыня Сахара")


def validate_refuseniks_phrase(text: str) -> tuple[bool, str]:
    """Validate a phrase that must contain the exact word отказников."""
    accepted, reason = _validate_required_fragment(text, "отказников")
    if not accepted:
        return accepted, reason
    if not re.search(r"(?<![A-Za-zА-Яа-яЁё])отказников(?![A-Za-zА-Яа-яЁё])", text):
        return False, "required_word_not_standalone"
    return True, ""


def validate_question_check_phrase(text: str) -> tuple[bool, str]:
    """Validate a phrase ending with exactly one allowed question marker."""
    accepted, reason = _validate_common_shape(text)
    if not accepted:
        return accepted, reason
    marker_count = sum(text.count(marker) for marker in QUESTION_MARKERS)
    if marker_count != 1:
        return False, "question_marker_count"
    if not any(text.endswith(marker) for marker in QUESTION_MARKERS):
        return False, "question_marker_not_final"
    if text.count("?") != 1:
        return False, "question_mark_count"
    return True, ""


def validate_one_c_phrase(text: str) -> tuple[bool, str]:
    """Validate a phrase that must contain the exact term 1С."""
    accepted, reason = _validate_required_fragment(text, "1С")
    if not accepted:
        return accepted, reason
    if "1C" in text or "1с" in text:
        return False, "wrong_one_c_spelling"
    return True, ""


def _validate_required_fragment(text: str, required: str) -> tuple[bool, str]:
    """Run shared checks for phrases with one required exact fragment."""
    accepted, reason = _validate_common_shape(text)
    if not accepted:
        return accepted, reason
    if text.count(required) != 1:
        return False, "required_fragment_count"
    return True, ""


def _validate_common_shape(text: str) -> tuple[bool, str]:
    """Reject output that looks like formatting, prompt echo, or malformed TTS text."""
    if _collapse_spaces(text) != text.strip():
        return False, "bad_spacing"
    if "\n" in text or "\r" in text:
        return False, "multiline"
    if _has_forbidden_punctuation(text):
        return False, "written_or_dialog_punctuation"
    lowered = text.lower()
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in WRITTEN_STYLE_PATTERNS):
        return False, "written_style"
    if _looks_like_fragment(text):
        return False, "sentence_fragment"
    return True, ""


def _collapse_spaces(text: str) -> str:
    """Collapse repeated whitespace without changing other characters."""
    return re.sub(r"\s+", " ", text.strip())


def _has_forbidden_punctuation(text: str) -> bool:
    """Reject punctuation that usually marks written formatting, not a TTS phrase."""
    if any(char in text for char in "\"'`«»[]{}<>|"):
        return True
    if ":" in text or ";" in text:
        return True
    return False


def _looks_like_fragment(text: str) -> bool:
    """Reject very short snippets and unfinished comma fragments."""
    stripped = text.strip()
    if not stripped:
        return True
    if stripped.endswith(","):
        return True
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", stripped)
    return len(words) < 5
