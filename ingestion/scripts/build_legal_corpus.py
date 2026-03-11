from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import duckdb

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.scripts.legal_corpus_utils import (
    build_document_record,
    build_judgment_chunks,
    build_statute_chunks,
    dumps_jsonl,
    normalize_text,
    read_text_from_file,
)


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS ingestion_runs (
        run_id VARCHAR PRIMARY KEY,
        manifest_path VARCHAR,
        started_at TIMESTAMP,
        completed_at TIMESTAMP,
        document_count BIGINT,
        chunk_count BIGINT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS corpus_documents (
        document_id VARCHAR PRIMARY KEY,
        source_id VARCHAR,
        title VARCHAR,
        citation VARCHAR,
        source_type VARCHAR,
        document_type VARCHAR,
        jurisdiction VARCHAR,
        language VARCHAR,
        source_url VARCHAR,
        local_path VARCHAR,
        summary VARCHAR,
        text_length BIGINT,
        content_hash VARCHAR
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS corpus_chunks (
        chunk_id VARCHAR PRIMARY KEY,
        document_id VARCHAR,
        vector_position BIGINT,
        title VARCHAR,
        citation VARCHAR,
        source_type VARCHAR,
        language VARCHAR,
        chunk_strategy VARCHAR,
        chunk_size BIGINT,
        summary VARCHAR,
        linked_citations VARCHAR,
        text VARCHAR
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS section_mappings (
        source_citation VARCHAR,
        target_citation VARCHAR,
        relationship VARCHAR,
        notes VARCHAR,
        confidence DOUBLE
    )
    """,
]


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_mappings(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [row for row in reader if any(row.values())]


def init_analytics_db(connection: duckdb.DuckDBPyConnection) -> None:
    for statement in SCHEMA_STATEMENTS:
        connection.execute(statement)


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean official legal downloads and build the NyayaSetu corpus.")
    parser.add_argument("--download-manifest", default="ingestion/manifest/download_manifest.jsonl")
    parser.add_argument("--output-corpus", default="data/corpus/official_legal_corpus.jsonl")
    parser.add_argument("--analytics-db", default="data/analytics/legal_corpus.duckdb")
    parser.add_argument("--mapping-csv", default="ingestion/configs/ipc_bns_mappings.csv")
    args = parser.parse_args()

    manifest_rows = load_jsonl(Path(args.download_manifest))
    documents: list[dict] = []
    chunks: list[dict] = []
    for row in manifest_rows:
        local_path = row.get("local_path")
        if not local_path:
            continue
        raw_text = normalize_text(read_text_from_file(Path(local_path)))
        if len(raw_text) < 200:
            continue
        document = build_document_record(row, raw_text)
        documents.append(document)
        if row["source_type"] in {"statute", "gazette"}:
            chunks.extend(build_statute_chunks(document))
        else:
            chunks.extend(build_judgment_chunks(document))

    dumps_jsonl(chunks, Path(args.output_corpus))

    connection = duckdb.connect(args.analytics_db)
    try:
        init_analytics_db(connection)
        connection.execute("DELETE FROM corpus_documents")
        connection.execute("DELETE FROM corpus_chunks")
        connection.execute("DELETE FROM section_mappings")

        document_rows = [
            (
                document["document_id"],
                document["source_id"],
                document["title"],
                document["citation"],
                document["source_type"],
                document["document_type"],
                document["jurisdiction"],
                document["language"],
                document["source_url"],
                document["local_path"],
                document["summary"],
                document["text_length"],
                document["content_hash"],
            )
            for document in documents
        ]
        if document_rows:
            connection.executemany(
                """
                INSERT INTO corpus_documents (
                    document_id, source_id, title, citation, source_type, document_type,
                    jurisdiction, language, source_url, local_path, summary, text_length, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                document_rows,
            )

        chunk_rows = [
            (
                chunk["chunk_id"],
                chunk["document_id"],
                None,
                chunk["title"],
                chunk["citation"],
                chunk["source_type"],
                chunk["language"],
                chunk["chunk_strategy"],
                chunk["chunk_size"],
                chunk["summary"],
                json.dumps(chunk["linked_citations"], ensure_ascii=True),
                chunk["text"],
            )
            for chunk in chunks
        ]
        if chunk_rows:
            connection.executemany(
                """
                INSERT INTO corpus_chunks (
                    chunk_id, document_id, vector_position, title, citation, source_type,
                    language, chunk_strategy, chunk_size, summary, linked_citations, text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                chunk_rows,
            )

        mapping_rows = load_mappings(Path(args.mapping_csv))
        if mapping_rows:
            connection.executemany(
                """
                INSERT INTO section_mappings (
                    source_citation, target_citation, relationship, notes, confidence
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        row["source_citation"],
                        row["target_citation"],
                        row.get("relationship", ""),
                        row.get("notes", ""),
                        float(row.get("confidence") or 0.0),
                    )
                    for row in mapping_rows
                ],
            )

        connection.execute(
            """
            INSERT INTO ingestion_runs (run_id, manifest_path, started_at, completed_at, document_count, chunk_count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                str(uuid4()),
                args.download_manifest,
                datetime.now(timezone.utc),
                datetime.now(timezone.utc),
                len(documents),
                len(chunks),
            ],
        )
    finally:
        connection.close()

    print(f"Built corpus with {len(documents)} documents and {len(chunks)} chunks at {args.output_corpus}.")


if __name__ == "__main__":
    main()
