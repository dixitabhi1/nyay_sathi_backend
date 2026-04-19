from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.services.corpus_records import load_legal_corpus_records
from app.services.page_index import PageIndexStore


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Build the NyayaSetu PageIndex from the legal corpus.")
    parser.add_argument("--corpus-path", default=str(settings.legal_corpus_path))
    parser.add_argument("--page-index-path", default=str(settings.page_index_path))
    args = parser.parse_args()

    corpus_path = Path(args.corpus_path)
    if not corpus_path.exists():
        corpus_path = Path(settings.bootstrap_corpus_path)

    records = load_legal_corpus_records(settings, corpus_path)
    if not records:
        raise SystemExit(f"No corpus rows found at {corpus_path}")

    page_index = PageIndexStore(settings)
    page_index.index_path = Path(args.page_index_path)
    page_index.build(records)
    print(f"Built PageIndex with {len(page_index.nodes)} structural records at {page_index.index_path}.")


if __name__ == "__main__":
    main()
