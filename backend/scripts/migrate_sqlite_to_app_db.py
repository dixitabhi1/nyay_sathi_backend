from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import MetaData, create_engine, select

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.db.session import Base, engine as target_engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy NyayaSetu application tables from local SQLite into the configured app DB.")
    parser.add_argument("--source-sqlite", default="storage/db/db.db")
    parser.add_argument("--truncate-target", action="store_true")
    args = parser.parse_args()

    source_path = Path(args.source_sqlite)
    if not source_path.is_absolute():
        source_path = PROJECT_ROOT / source_path
    if not source_path.exists():
        raise SystemExit(f"Source SQLite DB not found at {source_path}")

    settings = get_settings()
    Base.metadata.create_all(bind=target_engine)

    source_engine = create_engine(f"sqlite+pysqlite:///{source_path.resolve().as_posix()}", future=True)
    source_metadata = MetaData()
    source_metadata.reflect(bind=source_engine)

    copied_tables: list[tuple[str, int]] = []
    ordered_tables = list(Base.metadata.sorted_tables)

    with source_engine.connect() as source_conn, target_engine.begin() as target_conn:
        for table in ordered_tables:
            if table.name not in source_metadata.tables:
                continue

            source_table = source_metadata.tables[table.name]
            rows = [dict(row._mapping) for row in source_conn.execute(select(source_table))]
            if not rows:
                copied_tables.append((table.name, 0))
                continue

            if args.truncate_target:
                target_conn.execute(table.delete())

            target_conn.execute(table.insert(), rows)
            copied_tables.append((table.name, len(rows)))

    print(f"Target database: {settings.resolved_database_url}")
    for table_name, row_count in copied_tables:
        print(f"{table_name}: {row_count} rows copied")


if __name__ == "__main__":
    main()
