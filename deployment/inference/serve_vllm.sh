#!/usr/bin/env bash
set -euo pipefail

MODEL_PATH="${1:-/models/mistral-7b-instruct}"
PORT="${PORT:-8000}"

python -m vllm.entrypoints.openai.api_server \
  --model "$MODEL_PATH" \
  --served-model-name nyayasetu-legal-llm \
  --host 0.0.0.0 \
  --port "$PORT" \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.92

