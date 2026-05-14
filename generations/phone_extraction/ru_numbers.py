"""Russian number rendering helpers for phone dictation cases."""

from __future__ import annotations

import random


DIGIT_WORDS = {
    "0": "ноль",
    "1": "один",
    "2": "два",
    "3": "три",
    "4": "четыре",
    "5": "пять",
    "6": "шесть",
    "7": "семь",
    "8": "восемь",
    "9": "девять",
}

REPEAT_DIGIT_WORDS = {
    "0": "нуля",
    "1": "единицы",
    "2": "двойки",
    "3": "тройки",
    "4": "четверки",
    "5": "пятерки",
    "6": "шестерки",
    "7": "семерки",
    "8": "восьмерки",
    "9": "девятки",
}

REPEAT_COUNT_WORDS = {
    2: "две",
    3: "три",
}

TEENS = {
    10: "десять",
    11: "одиннадцать",
    12: "двенадцать",
    13: "тринадцать",
    14: "четырнадцать",
    15: "пятнадцать",
    16: "шестнадцать",
    17: "семнадцать",
    18: "восемнадцать",
    19: "девятнадцать",
}

TENS = {
    20: "двадцать",
    30: "тридцать",
    40: "сорок",
    50: "пятьдесят",
    60: "шестьдесят",
    70: "семьдесят",
    80: "восемьдесят",
    90: "девяносто",
}

HUNDREDS = {
    100: "сто",
    200: "двести",
    300: "триста",
    400: "четыреста",
    500: "пятьсот",
    600: "шестьсот",
    700: "семьсот",
    800: "восемьсот",
    900: "девятьсот",
}


def number_to_words(value: int) -> str:
    """Render an integer from 0 to 999 as Russian words."""
    if value < 0 or value > 999:
        raise ValueError(f"value out of range 0..999: {value}")
    if value < 10:
        return DIGIT_WORDS[str(value)]
    if value < 20:
        return TEENS[value]
    if value < 100:
        tens = (value // 10) * 10
        unit = value % 10
        if unit == 0:
            return TENS[tens]
        return f"{TENS[tens]} {DIGIT_WORDS[str(unit)]}"
    hundreds = (value // 100) * 100
    remainder = value % 100
    if remainder == 0:
        return HUNDREDS[hundreds]
    return f"{HUNDREDS[hundreds]} {number_to_words(remainder)}"


def digit_words(digits: str) -> str:
    """Render digits one by one as Russian digit words."""
    return " ".join(DIGIT_WORDS[digit] for digit in digits)


def fixed_width_words(digits: str, rng: random.Random | None = None) -> str:
    """Render a fixed-width numeric block without dropping leading zeros."""
    if not digits.isdigit():
        raise ValueError(f"digits must contain only decimal digits: {digits}")
    if digits.startswith("0"):
        return _leading_zero_words(digits, rng)
    return number_to_words(int(digits))


def compact_words(digits: str) -> str:
    """Render a fixed-width block and remove spaces to emulate ASR word glue."""
    return fixed_width_words(digits).replace(" ", "")


def repeat_words(digits: str) -> str | None:
    """Render repeated digits as a phrase like 'три нуля' when possible."""
    if len(digits) not in (2, 3) or len(set(digits)) != 1:
        return None
    count = len(digits)
    digit = digits[0]
    return f"{REPEAT_COUNT_WORDS[count]} {REPEAT_DIGIT_WORDS[digit]}"


def _leading_zero_words(digits: str, rng: random.Random | None) -> str:
    """Render a block with leading zeros using varied but lossless forms."""
    zero_count = len(digits) - len(digits.lstrip("0"))
    rest = digits[zero_count:]
    options: list[str] = []
    options.append(" ".join(["ноль"] * zero_count + ([number_to_words(int(rest))] if rest else [])))
    if zero_count in REPEAT_COUNT_WORDS:
        repeat = f"{REPEAT_COUNT_WORDS[zero_count]} нуля"
        options.append(f"{repeat} {number_to_words(int(rest))}".strip() if rest else repeat)
    if rest:
        options.append(" ".join(["ноль"] * zero_count + [digit_words(rest)]))
    chooser = rng.choice if rng is not None else random.choice
    return chooser(options)
