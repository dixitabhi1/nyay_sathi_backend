from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_embedding_text(row: dict) -> str:
    parts = [
        row.get("title", ""),
        row.get("citation", ""),
        row.get("summary", ""),
        row.get("text", ""),
        row.get("question", ""),
        row.get("context", ""),
        row.get("answer", ""),
    ]
    return "\n".join(part.strip() for part in parts if isinstance(part, str) and part.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a FAISS index for the NyayaSetu legal corpus.")
    parser.add_argument("--corpus-path", default="data/corpus/official_legal_corpus.jsonl")
    parser.add_argument("--fallback-corpus-path", default="data/sample/legal_corpus/legal_corpus.jsonl")
    parser.add_argument("--model-name", default="BAAI/bge-m3")
    parser.add_argument("--index-path", default="data/index/legal.index")
    parser.add_argument("--metadata-path", default="data/index/legal_metadata.json")
    parser.add_argument("--analytics-db", default="data/analytics/legal_corpus.duckdb")
    args = parser.parse_args()

    corpus_path = Path(args.corpus_path)
    if not corpus_path.exists():
        corpus_path = Path(args.fallback_corpus_path)
    corpus_rows = load_jsonl(corpus_path)
    model = SentenceTransformer(args.model_name)
    embeddings = model.encode(
        [build_embedding_text(row) for row in corpus_rows],
        normalize_embeddings=True,
    )
    embeddings = np.asarray(embeddings, dtype="float32")

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    index_path = Path(args.index_path)
    metadata_path = Path(args.metadata_path)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    for position, row in enumerate(corpus_rows):
        row["vector_position"] = position
    faiss.write_index(index, str(index_path))
    metadata_path.write_text(json.dumps(corpus_rows, ensure_ascii=True, indent=2), encoding="utf-8")
    if Path(args.analytics_db).exists():
        connection = duckdb.connect(args.analytics_db)
        try:
            if corpus_rows and connection.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'corpus_chunks'"
            ).fetchone()[0]:
                updates = [(row["vector_position"], row["chunk_id"]) for row in corpus_rows if row.get("chunk_id")]
                if updates:
                    connection.executemany(
                        "UPDATE corpus_chunks SET vector_position = ? WHERE chunk_id = ?",
                        updates,
                    )
        finally:
            connection.close()
    print(f"Indexed {len(corpus_rows)} legal documents into {index_path}.")


if __name__ == "__main__":
    main()
