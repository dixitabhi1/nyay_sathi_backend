#!/bin/sh
set -eu

PERSIST_ROOT="${PERSISTENT_STORAGE_ROOT:-/data/nyayasetu}"
HF_CACHE_ROOT="${HF_HOME:-/data/.huggingface}"
INDEX_PATH="$PERSIST_ROOT/index/legal.index"
METADATA_PATH="$PERSIST_ROOT/index/legal_metadata.json"
CHECKPOINT_DIR="$PERSIST_ROOT/index/checkpoints/legal_space_runtime"

mkdir -p \
  "$PERSIST_ROOT/db" \
  "$PERSIST_ROOT/analytics" \
  "$PERSIST_ROOT/index" \
  "$PERSIST_ROOT/uploads" \
  "$HF_CACHE_ROOT"

if [ ! -f "$INDEX_PATH" ] || [ ! -f "$METADATA_PATH" ]; then
  if [ -f /app/data/index/legal.index ] && [ -f /app/data/index/legal_metadata.json ]; then
    cp /app/data/index/legal.index "$INDEX_PATH"
    cp /app/data/index/legal_metadata.json "$METADATA_PATH"
  else
    python /app/rag/indexing/build_faiss_index.py --checkpoint-dir "$CHECKPOINT_DIR"
  fi
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-7860}"
