#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

python generate.py --config generations/targeted_phrases/config.yaml
