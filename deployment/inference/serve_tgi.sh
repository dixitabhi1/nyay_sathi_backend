#!/usr/bin/env bash
set -euo pipefail

MODEL_PATH="${1:-/models/mistral-7b-instruct}"

text-generation-launcher \
  --model-id "$MODEL_PATH" \
  --hostname 0.0.0.0 \
  --port 8000 \
  --max-input-length 4096 \
  --max-total-tokens 8192

