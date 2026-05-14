"""Build deterministic phone extraction cases before LLM generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from generations.phone_extraction.cases import PhoneCaseGenerator


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for case generation."""
    parser = argparse.ArgumentParser(description="Build phone extraction cases.")
    parser.add_argument("--count", type=int, required=True, help="Number of unique phone numbers.")
    parser.add_argument("--output", type=Path, required=True, help="Output JSONL path for generated variants.")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic seed.")
    parser.add_argument("--operator-min", type=int, default=800, help="Minimum fixed-width operator block.")
    parser.add_argument("--operator-max", type=int, default=999, help="Maximum fixed-width operator block.")
    return parser


def write_cases(count: int, output: Path, seed: int, operator_min: int = 800, operator_max: int = 999) -> None:
    """Generate phone variants and write them as UTF-8 JSONL."""
    variants = PhoneCaseGenerator(seed=seed, operator_min=operator_min, operator_max=operator_max).generate(count)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as file_obj:
        for variant in variants:
            file_obj.write(json.dumps(variant.to_json(), ensure_ascii=False) + "\n")


def main() -> None:
    """Generate cases from CLI arguments."""
    args = build_parser().parse_args()
    write_cases(
        count=args.count,
        output=args.output,
        seed=args.seed,
        operator_min=args.operator_min,
        operator_max=args.operator_max,
    )
    print(f"[OK] Wrote {args.count * 11} variants to {args.output}")


if __name__ == "__main__":
    main()
