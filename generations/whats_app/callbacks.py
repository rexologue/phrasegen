"""Post-validation callbacks for the WhatsApp TTS generation pack."""

from __future__ import annotations

import re


PROTECTED_TERMS = ("АИ МОП", "AmoCRM", "Bitrix", "API", "WhatsApp", "Telegram", "Max")

BUSINESS_CONTEXT_WORDS = (
    "аккаунт",
    "аналитик",
    "бот",
    "воронк",
    "встреч",
    "диалог",
    "договор",
    "задач",
    "заявк",
    "звон",
    "интеграц",
    "канал",
    "клиент",
    "команд",
    "контакт",
    "лид",
    "менеджер",
    "мессендж",
    "напомин",
    "обращени",
    "оператор",
    "оплат",
    "отчет",
    "поддержк",
    "продаж",
    "проект",
    "рассыл",
    "сделк",
    "сервис",
    "сообщени",
    "соглас",
    "статус",
    "уведомлен",
    "чат",
    "crm",
    "црм",
)

WRITTEN_STYLE_PATTERNS = (
    r"^\s*[-*0-9]+[.)\s]",
    r"\bjson\b",
    r"\bmarkdown\b",
    r"\bprompt\b",
    r"\brule\b",
    r"\bexample\b",
    r"\bсгенерируй\b",
    r"\bверни\b",
    r"\bданн(?:ая|ый|ое|ые)\b",
    r"\bвышеуказан",
    r"\bнижеследующ",
    r"\bнастоящ(?:им|ая|ий|ее)\b",
    r"\bследует отметить\b",
    r"\bв рамках настоящего\b",
)

RANDOM_TOPIC_WORDS = (
    "одуванчик",
    "ромашк",
    "пирож",
    "котик",
    "погода",
    "лес",
    "море",
    "кухн",
    "огород",
)


def validate_ai_mop_phrase(text: str) -> tuple[bool, str]:
    """Validate a phrase that must contain АИ МОП."""
    return _validate_term_phrase(text, "АИ МОП")


def validate_amocrm_phrase(text: str) -> tuple[bool, str]:
    """Validate a phrase that must contain AmoCRM."""
    return _validate_term_phrase(text, "AmoCRM")


def validate_bitrix_phrase(text: str) -> tuple[bool, str]:
    """Validate a phrase that must contain Bitrix."""
    return _validate_term_phrase(text, "Bitrix")


def validate_api_phrase(text: str) -> tuple[bool, str]:
    """Validate a phrase that must contain API."""
    return _validate_term_phrase(text, "API")


def validate_whatsapp_phrase(text: str) -> tuple[bool, str]:
    """Validate a phrase that must contain WhatsApp."""
    return _validate_term_phrase(text, "WhatsApp")


def validate_telegram_phrase(text: str) -> tuple[bool, str]:
    """Validate a phrase that must contain Telegram."""
    return _validate_term_phrase(text, "Telegram")


def validate_max_phrase(text: str) -> tuple[bool, str]:
    """Validate a phrase that must contain Max as a communication channel."""
    accepted, reason = _validate_term_phrase(text, "Max")
    if not accepted:
        return accepted, reason
    lowered = text.lower()
    max_context_patterns = (
        r"\bв\s+Max\b",
        r"\bчерез\s+Max\b",
        r"\bиз\s+Max\b",
        r"\bдля\s+Max\b",
        r"\bканал\w*\s+Max\b",
        r"\bчат\w*\s+Max\b",
        r"\bсообщени\w*\s+.*\bMax\b",
        r"\bMax\b.*\bсообщени",
        r"\bMax\b.*\bканал",
        r"\bMax\b.*\bчат",
    )
    if not any(re.search(pattern, text, re.IGNORECASE) for pattern in max_context_patterns):
        return False, "max_context_missing"
    if re.search(r"\bмаксим\w*\b", lowered):
        return False, "max_as_person_name"
    return True, ""


def _validate_term_phrase(text: str, required_term: str) -> tuple[bool, str]:
    """Run shared TTS phrase checks for one protected term."""
    normalized = _collapse_spaces(text)
    if normalized != text.strip():
        return False, "bad_spacing"
    if "\n" in text or "\r" in text:
        return False, "multiline"
    if _has_forbidden_punctuation(text):
        return False, "written_or_dialog_punctuation"
    if text.count(required_term) != 1:
        return False, "required_term_count"
    for term in PROTECTED_TERMS:
        if term != required_term and term in text:
            return False, "other_protected_term_present"
    if not _has_business_context(text, required_term):
        return False, "business_context_missing"
    lowered = text.lower()
    if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in WRITTEN_STYLE_PATTERNS):
        return False, "written_style"
    if any(word in lowered for word in RANDOM_TOPIC_WORDS):
        return False, "random_topic"
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


def _has_business_context(text: str, required_term: str) -> bool:
    """Return whether a phrase has enough work-domain context."""
    lowered = text.lower().replace(required_term.lower(), " ")
    return any(word in lowered for word in BUSINESS_CONTEXT_WORDS)


def _looks_like_fragment(text: str) -> bool:
    """Reject obvious non-sentence snippets."""
    stripped = text.strip()
    if not stripped:
        return True
    if stripped.endswith(","):
        return True
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", stripped)
    if len(words) < 6:
        return True
    return False
