"""Phone extraction case entities and deterministic case generation."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from generations.phone_extraction.ru_numbers import compact_words, digit_words, fixed_width_words, repeat_words


@dataclass(frozen=True)
class PhoneBlocks:
    """Fixed-width blocks of a Russian phone number."""

    prefix: str
    operator: str
    middle: str
    first_tail: str
    second_tail: str

    @property
    def digits(self) -> str:
        """Return the canonical 11-digit phone number."""
        return f"{self.prefix}{self.operator}{self.middle}{self.first_tail}{self.second_tail}"

    def as_list(self) -> list[str]:
        """Return blocks as a list in dictation order."""
        return [self.prefix, self.operator, self.middle, self.first_tail, self.second_tail]


@dataclass(frozen=True)
class PhoneVariant:
    """One generated source dictation variant for a phone number."""

    case_id: str
    phone_digits: str
    target_digits: str
    expected_result: str | None
    kind: str
    variant_index: int
    blocks: list[str]
    spoken: str
    notes: list[str]

    def to_json(self) -> dict[str, Any]:
        """Return a JSON-safe representation of the variant."""
        return {
            "case_id": self.case_id,
            "phone_digits": self.phone_digits,
            "target_digits": self.target_digits,
            "expected_result": self.expected_result,
            "kind": self.kind,
            "variant_index": self.variant_index,
            "blocks": self.blocks,
            "spoken": self.spoken,
            "notes": self.notes,
        }


class PhoneCaseGenerator:
    """Generates canonical phones and source dictation variants."""

    def __init__(self, seed: int, operator_min: int = 800, operator_max: int = 999) -> None:
        """Initialize deterministic random state."""
        self._validate_operator_range(operator_min, operator_max)
        self.rng = random.Random(seed)
        self.operator_min = operator_min
        self.operator_max = operator_max
        self.seen_numbers: set[str] = set()

    def generate(self, count: int) -> list[PhoneVariant]:
        """Generate all variants for a number of unique phones."""
        variants: list[PhoneVariant] = []
        for index in range(1, count + 1):
            blocks = self._unique_blocks()
            variants.extend(self._variants_for_blocks(index, blocks))
        return variants

    def _unique_blocks(self) -> PhoneBlocks:
        """Generate one unique phone number as fixed-width blocks."""
        while True:
            blocks = PhoneBlocks(
                prefix="8",
                operator=f"{self.rng.randint(self.operator_min, self.operator_max):03d}",
                middle=f"{self.rng.randint(0, 999):03d}",
                first_tail=f"{self.rng.randint(0, 99):02d}",
                second_tail=f"{self.rng.randint(0, 99):02d}",
            )
            if blocks.digits not in self.seen_numbers:
                self.seen_numbers.add(blocks.digits)
                return blocks

    def _validate_operator_range(self, operator_min: int, operator_max: int) -> None:
        """Validate the configured fixed-width operator block range."""
        if operator_min < 0 or operator_min > 999:
            raise ValueError(f"operator_min out of range 0..999: {operator_min}")
        if operator_max < 0 or operator_max > 999:
            raise ValueError(f"operator_max out of range 0..999: {operator_max}")
        if operator_min > operator_max:
            raise ValueError("operator_min must be <= operator_max")

    def _variants_for_blocks(self, index: int, blocks: PhoneBlocks) -> list[PhoneVariant]:
        """Generate ideal, noisy, and incomplete variants for one phone."""
        variants = [self._variant(index, blocks, "complete_ideal", 0, blocks.digits, blocks.digits, self._ideal_spoken(blocks), ["ideal"])]
        noisy = self._noisy_spoken_variants(blocks)
        for noisy_index, spoken in enumerate(noisy, 1):
            variants.append(self._variant(index, blocks, "complete_noisy", noisy_index, blocks.digits, blocks.digits, spoken, [f"noise_{noisy_index}"]))
        incomplete = self._incomplete_spoken_variants(blocks)
        for incomplete_index, payload in enumerate(incomplete, 1):
            target_digits, spoken, notes = payload
            variants.append(self._variant(index, blocks, "incomplete", incomplete_index, target_digits, None, spoken, notes))
        return variants

    def _variant(
        self,
        index: int,
        blocks: PhoneBlocks,
        kind: str,
        variant_index: int,
        target_digits: str,
        expected_result: str | None,
        spoken: str,
        notes: list[str],
    ) -> PhoneVariant:
        """Build one phone variant entity."""
        case_id = f"phone_{index:06d}__{kind}_{variant_index}"
        return PhoneVariant(
            case_id=case_id,
            phone_digits=blocks.digits,
            target_digits=target_digits,
            expected_result=expected_result,
            kind=kind,
            variant_index=variant_index,
            blocks=blocks.as_list(),
            spoken=spoken,
            notes=notes,
        )

    def _ideal_spoken(self, blocks: PhoneBlocks) -> str:
        """Render the ideal full dictation with fixed-width blocks."""
        return " ".join(
            [
                "восемь",
                fixed_width_words(blocks.operator, self.rng),
                fixed_width_words(blocks.middle, self.rng),
                fixed_width_words(blocks.first_tail, self.rng),
                fixed_width_words(blocks.second_tail, self.rng),
            ]
        )

    def _noisy_spoken_variants(self, blocks: PhoneBlocks) -> list[str]:
        """Render five complete noisy dictation variants without digit loss."""
        return [
            self._mixed_words_and_digits(blocks),
            self._glued_words(blocks),
            self._filler_split(blocks),
            self._asr_typo_words(blocks),
            self._repeat_or_digitwise(blocks),
        ]

    def _mixed_words_and_digits(self, blocks: PhoneBlocks) -> str:
        """Render a complete variant that mixes words and digit strings."""
        return " ".join(
            [
                self.rng.choice(["8", "+7", "семь"]),
                fixed_width_words(blocks.operator, self.rng),
                self.rng.choice([blocks.middle, fixed_width_words(blocks.middle, self.rng)]),
                self.rng.choice([blocks.first_tail, fixed_width_words(blocks.first_tail, self.rng)]),
                self.rng.choice([blocks.second_tail, fixed_width_words(blocks.second_tail, self.rng)]),
            ]
        )

    def _glued_words(self, blocks: PhoneBlocks) -> str:
        """Render a complete variant with ASR-like word glue."""
        return " ".join(
            [
                "восемь",
                compact_words(blocks.operator),
                self.rng.choice([compact_words(blocks.middle), fixed_width_words(blocks.middle, self.rng)]),
                compact_words(blocks.first_tail),
                self.rng.choice([compact_words(blocks.second_tail), fixed_width_words(blocks.second_tail, self.rng)]),
            ]
        )

    def _filler_split(self, blocks: PhoneBlocks) -> str:
        """Render a complete variant with service words and pauses."""
        fillers = ["так", "секунду", "записывайте", "дальше", "угу"]
        return (
            f"записывайте {fixed_width_words(blocks.prefix, self.rng)}, "
            f"{fixed_width_words(blocks.operator, self.rng)}, {self.rng.choice(fillers)}, "
            f"{fixed_width_words(blocks.middle, self.rng)}, {self.rng.choice(fillers)}, "
            f"{fixed_width_words(blocks.first_tail, self.rng)} {fixed_width_words(blocks.second_tail, self.rng)}, все"
        )

    def _asr_typo_words(self, blocks: PhoneBlocks) -> str:
        """Render a complete variant with common ASR-like misspellings."""
        text = self._ideal_spoken(blocks)
        replacements = {
            "девятьсот": "девятсот",
            "семьдесят": "семсят",
            "пятьдесят": "писят",
            "девяносто": "девясат",
            "двадцать": "двацать",
            "одиннадцать": "одинадацать",
            "восемнадцать": "восемьнадцать",
            "шестнадцать": "шеснадцать",
        }
        for source, target in replacements.items():
            text = text.replace(source, target)
        return text

    def _repeat_or_digitwise(self, blocks: PhoneBlocks) -> str:
        """Render a complete variant with repeat forms where possible."""
        parts = [self.rng.choice(["восемь", "8"])]
        for block in [blocks.operator, blocks.middle, blocks.first_tail, blocks.second_tail]:
            repeated = repeat_words(block)
            if repeated and self.rng.random() < 0.8:
                parts.append(repeated)
            elif "0" in block and self.rng.random() < 0.7:
                parts.append(digit_words(block))
            else:
                parts.append(fixed_width_words(block, self.rng))
        return " ".join(parts)

    def _incomplete_spoken_variants(self, blocks: PhoneBlocks) -> list[tuple[str, str, list[str]]]:
        """Render five incomplete variants that intentionally cannot yield success."""
        operator = fixed_width_words(blocks.operator, self.rng)
        middle = fixed_width_words(blocks.middle, self.rng)
        first_tail = fixed_width_words(blocks.first_tail, self.rng)
        second_tail = fixed_width_words(blocks.second_tail, self.rng)
        return [
            (blocks.digits[1:], f"{operator} {middle} {first_tail} {second_tail}", ["missing_prefix"]),
            (blocks.prefix, "восемь", ["only_prefix"]),
            (blocks.prefix + blocks.operator, f"восемь {operator}", ["missing_middle_and_tail"]),
            (blocks.prefix + blocks.operator + blocks.middle, f"восемь {operator} {middle}", ["missing_both_tail_blocks"]),
            (blocks.prefix + blocks.operator + blocks.middle + blocks.first_tail, f"восемь {operator} {middle} {first_tail}", ["missing_last_tail_block"]),
        ]
