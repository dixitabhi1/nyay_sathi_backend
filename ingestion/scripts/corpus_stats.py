from __future__ import annotations

import argparse
import json

import duckdb


def main() -> None:
    parser = argparse.ArgumentParser(description="Report NyayaSetu corpus coverage against dataset targets.")
    parser.add_argument("--analytics-db", default="data/analytics/legal_corpus.duckdb")
    args = parser.parse_args()

    connection = duckdb.connect(args.analytics_db, read_only=True)
    try:
        total_documents = connection.execute("SELECT COUNT(*) FROM corpus_documents").fetchone()[0]
        statute_chunks = connection.execute(
            "SELECT COUNT(*) FROM corpus_chunks WHERE source_type IN ('statute', 'gazette')"
        ).fetchone()[0]
        judgment_chunks = connection.execute(
            "SELECT COUNT(*) FROM corpus_chunks WHERE source_type = 'judgment'"
        ).fetchone()[0]
        mapping_rows = connection.execute("SELECT COUNT(*) FROM section_mappings").fetchone()[0]
        languages = dict(connection.execute("SELECT language, COUNT(*) FROM corpus_chunks GROUP BY language").fetchall())
    finally:
        connection.close()

    report = {
        "total_documents": total_documents,
        "statute_chunks": statute_chunks,
        "judgment_chunks": judgment_chunks,
        "mapping_rows": mapping_rows,
        "target_statute_chunks": 10000,
        "target_judgment_passages": 50000,
        "languages": languages,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
