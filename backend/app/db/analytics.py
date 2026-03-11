from __future__ import annotations

from contextlib import contextmanager

import duckdb

from app.core.config import get_settings


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


@contextmanager
def duckdb_connection(read_only: bool = False):
    settings = get_settings()
    connection = duckdb.connect(str(settings.analytics_db_path), read_only=read_only)
    try:
        yield connection
    finally:
        connection.close()


def init_analytics_db() -> None:
    with duckdb_connection() as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
