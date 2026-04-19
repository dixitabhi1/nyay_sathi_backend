from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import faiss
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.services.corpus_records import load_legal_corpus_records
from ingestion.scripts.legal_corpus_utils import stable_id


def build_embedding_text(record: dict) -> str:
    parts = [
        record.get("source_id", ""),
        record.get("document_type", ""),
        record.get("chunk_strategy", ""),
        record.get("title", ""),
        record.get("citation", ""),
        record.get("summary", ""),
        record.get("text", ""),
        " ".join(record.get("linked_citations", [])) if isinstance(record.get("linked_citations"), list) else "",
        record.get("question", ""),
        record.get("context", ""),
        record.get("answer", ""),
    ]
    return "\n".join(part.strip() for part in parts if isinstance(part, str) and part.strip())

def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=True, indent=2), encoding="utf-8")


def update_vector_positions(analytics_db: Path, metadata: list[dict]) -> None:
    try:
        import duckdb
    except ImportError:
        print("duckdb is not installed; skipping vector_position updates.")
        return

    if not analytics_db.exists():
        print(f"Analytics DB not found at {analytics_db}; skipping vector_position updates.")
        return

    try:
        connection = duckdb.connect(str(analytics_db))
    except duckdb.IOException as exc:
        print(f"Could not open analytics DB for vector_position updates: {exc}")
        return

    try:
        connection.execute("UPDATE corpus_chunks SET vector_position = NULL")
        rows = [(index, item.get("chunk_id")) for index, item in enumerate(metadata) if item.get("chunk_id")]
        if rows:
            connection.executemany(
                "UPDATE corpus_chunks SET vector_position = ? WHERE chunk_id = ?",
                rows,
            )
    finally:
        connection.close()


def main() -> None:
    settings = get_settings()
    default_checkpoint_dir = settings.vector_index_path.parent / "checkpoints" / "legal"

    parser = argparse.ArgumentParser(description="Build a FAISS index from the NyayaSetu legal corpus.")
    parser.add_argument("--corpus-path", default=str(settings.legal_corpus_path))
    parser.add_argument("--index-path", default=str(settings.vector_index_path))
    parser.add_argument("--metadata-path", default=str(settings.vector_metadata_path))
    parser.add_argument("--analytics-db", default=str(settings.analytics_db_path))
    parser.add_argument("--model-name", default=settings.embedding_model_name)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--checkpoint-dir", default=str(default_checkpoint_dir))
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    corpus_path = Path(args.corpus_path)
    index_path = Path(args.index_path)
    metadata_path = Path(args.metadata_path)
    analytics_db = Path(args.analytics_db)
    checkpoint_dir = Path(args.checkpoint_dir)
    state_path = checkpoint_dir / "state.json"

    if args.reset and checkpoint_dir.exists():
        shutil.rmtree(checkpoint_dir)

    records = load_legal_corpus_records(settings, corpus_path)
    if not records:
        raise SystemExit(f"No corpus rows found at {corpus_path}")

    texts = [build_embedding_text(record) for record in records]
    total_batches = math.ceil(len(texts) / args.batch_size)
    corpus_fingerprint = stable_id(str(corpus_path.resolve()), str(len(records)), args.model_name)

    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("corpus_fingerprint") != corpus_fingerprint or state.get("batch_size") != args.batch_size:
            shutil.rmtree(checkpoint_dir, ignore_errors=True)

    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    from sentence_transformers import SentenceTransformer

    print(f"Loading embedding model: {args.model_name}")
    model = SentenceTransformer(args.model_name, device="cpu")

    state = {
        "corpus_fingerprint": corpus_fingerprint,
        "model_name": args.model_name,
        "batch_size": args.batch_size,
        "total_records": len(records),
        "total_batches": total_batches,
        "completed_batches": [],
    }
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))

    for batch_index in range(total_batches):
        batch_start = batch_index * args.batch_size
        batch_end = min(len(texts), batch_start + args.batch_size)
        batch_file = checkpoint_dir / f"batch_{batch_index:05d}.npy"
        if batch_file.exists():
            if batch_index not in state["completed_batches"]:
                state["completed_batches"].append(batch_index)
                state["completed_batches"].sort()
                save_state(state_path, state)
            print(f"Reusing batch {batch_index + 1}/{total_batches} ({batch_start}:{batch_end})")
            continue

        batch_embeddings = model.encode(
            texts[batch_start:batch_end],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        np.save(batch_file, np.asarray(batch_embeddings, dtype="float32"))
        state["completed_batches"].append(batch_index)
        state["completed_batches"].sort()
        save_state(state_path, state)
        print(f"Embedded batch {batch_index + 1}/{total_batches} ({batch_start}:{batch_end})")

    embedding_batches: list[np.ndarray] = []
    for batch_index in range(total_batches):
        batch_file = checkpoint_dir / f"batch_{batch_index:05d}.npy"
        embedding_batches.append(np.load(batch_file))

    embeddings = np.vstack(embedding_batches).astype("float32")
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    index_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(index_path))
    metadata_path.write_text(json.dumps(records, ensure_ascii=True, indent=2), encoding="utf-8")
    update_vector_positions(analytics_db, records)

    state["built_index_path"] = str(index_path)
    state["built_metadata_path"] = str(metadata_path)
    state["embedding_dimension"] = int(embeddings.shape[1])
    save_state(state_path, state)

    print(
        f"Built FAISS index with {len(records)} records and dimension {embeddings.shape[1]} "
        f"at {index_path}."
    )


if __name__ == "__main__":
    main()
