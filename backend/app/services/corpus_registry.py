from __future__ import annotations

from app.db.analytics import duckdb_connection
from app.schemas.admin import CorpusStatusResponse


class CorpusRegistry:
    def get_status(self) -> CorpusStatusResponse:
        with duckdb_connection(read_only=True) as connection:
            total_documents = connection.execute("SELECT COUNT(*) FROM corpus_documents").fetchone()[0]
            total_chunks = connection.execute("SELECT COUNT(*) FROM corpus_chunks").fetchone()[0]
            statute_chunks = connection.execute(
                "SELECT COUNT(*) FROM corpus_chunks WHERE source_type IN ('statute', 'gazette')"
            ).fetchone()[0]
            judgment_chunks = connection.execute(
                "SELECT COUNT(*) FROM corpus_chunks WHERE source_type = 'judgment'"
            ).fetchone()[0]
            mapping_rows = connection.execute("SELECT COUNT(*) FROM section_mappings").fetchone()[0]
            language_rows = connection.execute(
                "SELECT language, COUNT(*) AS count FROM corpus_chunks GROUP BY language"
            ).fetchall()
        languages = {row[0] or "unknown": row[1] for row in language_rows}
        return CorpusStatusResponse(
            total_documents=total_documents,
            total_chunks=total_chunks,
            statute_chunks=statute_chunks,
            judgment_chunks=judgment_chunks,
            mapping_rows=mapping_rows,
            languages=languages,
        )
