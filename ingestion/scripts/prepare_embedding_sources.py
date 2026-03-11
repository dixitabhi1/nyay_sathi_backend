from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.scripts.legal_corpus_utils import (
    build_document_record,
    build_judgment_chunks,
    build_statute_chunks,
    chunk_text,
    detect_language,
    dumps_jsonl,
    normalize_text,
    read_text_from_file,
    stable_id,
    summarize_text,
)

SUPPORTED_FILE_SUFFIXES = {".pdf", ".txt", ".md", ".html", ".htm"}
SUPPORTED_DATASET_SUFFIXES = {".jsonl", ".csv"}


def iter_input_paths(inputs: list[str]) -> list[Path]:
    discovered: list[Path] = []
    for raw_path in inputs:
        path = Path(raw_path)
        if path.is_dir():
            discovered.extend(candidate for candidate in path.rglob("*") if candidate.is_file())
            continue
        if path.is_file():
            discovered.append(path)
    return discovered


def infer_source_type(path: Path, text: str) -> str:
    name = path.stem.lower()
    if any(token in name for token in ("judgment", "judgement", "order", "appeal", "petition")):
        return "judgment"
    if any(token in name for token in ("ipc", "bns", "bnss", "bsa", "act", "code", "statute", "section")):
        return "statute"
    if "court" in text[:500].lower():
        return "judgment"
    return "reference"


def generic_chunks(document: dict) -> list[dict]:
    chunks: list[dict] = []
    for index, piece in enumerate(chunk_text(document["text"], chunk_chars=1400, overlap=180), start=1):
        chunk_id = stable_id(document["document_id"], str(index))
        chunks.append(
            {
                "chunk_id": chunk_id,
                "document_id": document["document_id"],
                "title": document["title"],
                "citation": document["citation"],
                "source_type": document["source_type"],
                "document_type": document["document_type"],
                "language": document["language"],
                "source_url": document["source_url"],
                "text": piece,
                "summary": summarize_text(piece, "statute"),
                "linked_citations": [],
                "chunk_strategy": "generic_passage",
                "chunk_size": len(piece),
            }
        )
    return chunks


def build_chunks_for_document(document: dict) -> list[dict]:
    if document["source_type"] in {"statute", "gazette"}:
        return build_statute_chunks(document)
    if document["source_type"] == "judgment":
        return build_judgment_chunks(document)
    return generic_chunks(document)


def build_document_from_file(path: Path) -> list[dict]:
    raw_text = normalize_text(read_text_from_file(path))
    if len(raw_text) < 80:
        return []
    source_type = infer_source_type(path, raw_text)
    record = build_document_record(
        {
            "source_id": f"local-file::{path.stem}",
            "local_path": str(path),
            "title": path.stem.replace("_", " ").replace("-", " ").title(),
            "citation": path.stem,
            "source_type": source_type,
            "document_type": source_type,
            "language": detect_language(raw_text),
            "jurisdiction": "India",
            "source_url": "",
        },
        raw_text,
    )
    return build_chunks_for_document(record)


def row_to_text(row: dict) -> str:
    ordered_keys = ("title", "citation", "summary", "question", "context", "answer", "text", "content", "body")
    parts = [str(row[key]).strip() for key in ordered_keys if row.get(key)]
    return "\n".join(part for part in parts if part)


def build_chunks_from_dataset(path: Path) -> list[dict]:
    rows: list[dict] = []
    if path.suffix.lower() == ".jsonl":
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    elif path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

    chunks: list[dict] = []
    for index, row in enumerate(rows, start=1):
        text = normalize_text(row_to_text(row))
        if len(text) < 40:
            continue
        source_type = row.get("source_type") or infer_source_type(path, text)
        record = build_document_record(
            {
                "source_id": f"dataset::{path.stem}",
                "local_path": f"{path}#row-{index}",
                "title": row.get("title") or row.get("question") or f"{path.stem} row {index}",
                "citation": row.get("citation") or f"{path.stem} row {index}",
                "source_type": source_type,
                "document_type": row.get("document_type", "dataset_row"),
                "language": row.get("language") or detect_language(text),
                "jurisdiction": row.get("jurisdiction", "India"),
                "source_url": row.get("source_url", ""),
            },
            text,
        )
        chunks.extend(build_chunks_for_document(record))
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare local PDFs and legal datasets for embedding and FAISS indexing.")
    parser.add_argument(
        "--inputs",
        nargs="+",
        required=True,
        help="Files or directories containing PDFs, text files, JSONL, or CSV legal datasets.",
    )
    parser.add_argument("--output-corpus", default="data/corpus/local_embedding_corpus.jsonl")
    args = parser.parse_args()

    paths = iter_input_paths(args.inputs)
    corpus_chunks: list[dict] = []
    for path in paths:
        suffix = path.suffix.lower()
        if suffix in SUPPORTED_FILE_SUFFIXES:
            corpus_chunks.extend(build_document_from_file(path))
        elif suffix in SUPPORTED_DATASET_SUFFIXES:
            corpus_chunks.extend(build_chunks_from_dataset(path))

    dumps_jsonl(corpus_chunks, Path(args.output_corpus))
    print(
        f"Prepared {len(corpus_chunks)} chunk records at {args.output_corpus}. "
        "Run rag/indexing/build_faiss_index.py against that corpus to generate embeddings and the FAISS index."
    )


if __name__ == "__main__":
    main()
