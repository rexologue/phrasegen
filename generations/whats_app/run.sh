#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

python generate.py --config generations/whats_app/config.yaml
