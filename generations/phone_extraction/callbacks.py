"""Callbacks for the phone extraction generation pack."""

from __future__ import annotations

import os
import re
import threading
from pathlib import Path
from typing import Any

from generations.phone_extraction.case_store import PhoneCaseStore, append_jsonl, count_jsonl_rows, now_payload


CASES_ENV = "PHONE_EXTRACTION_CASES_PATH"
USED_ENV = "PHONE_EXTRACTION_USED_PATH"
ACCEPTED_ENV = "PHONE_EXTRACTION_ACCEPTED_PATH"

_LOCK = threading.Lock()
_STORE_CACHE: dict[Path, PhoneCaseStore] = {}


def inject_phone_case(prompt: str) -> tuple[str, str]:
    """Append the next phone case to the prompt and return its case id as anchor."""
    cases_path = _env_path(CASES_ENV)
    used_path = _env_path(USED_ENV)
    with _LOCK:
        store = _store(cases_path)
        use_index = count_jsonl_rows(used_path)
        case = store.by_index(use_index)
        append_jsonl(
            used_path,
            {
                **now_payload(),
                "use_index": use_index,
                "case_id": case["case_id"],
                "kind": case["kind"],
                "target_digits": case["target_digits"],
                "expected_result": case["expected_result"],
            },
        )
    return f"{prompt}\n\n{_case_prompt_block(case)}", str(case["case_id"])


def validate_phone_case_output(text: str, anchor: str) -> tuple[bool, str]:
    """Validate an LLM-wrapped transcript against the anchored phone case."""
    cases_path = _env_path(CASES_ENV)
    accepted_path = _env_path(ACCEPTED_ENV)
    case = _store(cases_path).get(anchor)
    spoken = str(case["spoken"])
    if not _contains_source_spoken(text, spoken):
        return False, "source_spoken_missing_or_changed"
    if str(case["phone_digits"]) in text:
        return False, "canonical_digits_leaked"
    append_jsonl(
        accepted_path,
        {
            **now_payload(),
            "case_id": case["case_id"],
            "phone_digits": case["phone_digits"],
            "target_digits": case["target_digits"],
            "expected_result": case["expected_result"],
            "kind": case["kind"],
            "spoken": spoken,
            "llm_text": text,
        },
    )
    return True, ""


def _case_prompt_block(case: dict[str, Any]) -> str:
    """Render a strict prompt extension for one phone case."""
    expected = case["expected_result"] if case["expected_result"] is not None else "null"
    return f"""PHONE_EXTRACTION_CASE
case_id: {case["case_id"]}
case_kind: {case["kind"]}
expected_extraction_result: {expected}
target_digits_or_partial_digits: {case["target_digits"]}

Source dictation to preserve exactly:
<<<{case["spoken"]}>>>

Wrap this source dictation into one realistic PHONE_CAPTURE transcript window.
Rules:
- Return exactly one string in the configured JSON array.
- The source dictation between <<< >>> must appear in the output unchanged.
- You may add client filler words, assistant acknowledgements, line breaks, and speaker labels around it.
- Do not add the canonical 11-digit answer anywhere.
- Do not add another competing phone number.
- For incomplete cases, keep them incomplete and do not invent missing digits.
"""


def _contains_source_spoken(text: str, spoken: str) -> bool:
    """Check exact or whitespace-normalized presence of source dictation."""
    if spoken in text:
        return True
    return _collapse_spaces(spoken) in _collapse_spaces(text)


def _collapse_spaces(text: str) -> str:
    """Normalize case, punctuation, and whitespace for source-presence checks."""
    lowered = text.lower().replace("ё", "е")
    without_punctuation = re.sub(r"[.,;:!?\"'`«»()\[\]{}<>/\\|]+", " ", lowered)
    return re.sub(r"\s+", " ", without_punctuation).strip()


def _store(path: Path) -> PhoneCaseStore:
    """Return a cached case store for a path."""
    resolved = path.resolve()
    store = _STORE_CACHE.get(resolved)
    if store is None:
        store = PhoneCaseStore(resolved)
        _STORE_CACHE[resolved] = store
    return store


def _env_path(name: str) -> Path:
    """Read a required filesystem path from the environment."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable is not set: {name}")
    return Path(value).expanduser().resolve()
