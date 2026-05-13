"""Command line interface for the generator."""

from __future__ import annotations

import argparse
from pathlib import Path

from phrasegen.config.loader import load_project_config
from phrasegen.engine.runner import GenerationRunner


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(description="Universal text dataset generator.")
    parser.add_argument("--config", type=Path, required=True, help="Path to a UTF-8 YAML config.")
    return parser


def main() -> None:
    """Run the generator from CLI arguments."""
    args = build_parser().parse_args()
    config = load_project_config(args.config)
    runner = GenerationRunner(config)
    runner.run()
    print(f"[OK] Report: {config.output.report_path}")
    print(f"[OK] Dataset: {config.output.dataset_path}")
