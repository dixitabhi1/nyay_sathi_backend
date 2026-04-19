from __future__ import annotations

import json
from pathlib import Path

from app.core.config import Settings


def load_jsonl_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_legal_corpus_records(settings: Settings, corpus_path: Path | None = None) -> list[dict]:
    primary_path = corpus_path or Path(settings.legal_corpus_path)
    if not primary_path.exists():
        primary_path = Path(settings.bootstrap_corpus_path)

    records = load_jsonl_records(primary_path)
    seen_chunk_ids = {str(item.get("chunk_id") or "") for item in records if item.get("chunk_id")}

    for supplemental_path in _supplemental_paths(settings):
        for item in load_jsonl_records(supplemental_path):
            chunk_id = str(item.get("chunk_id") or "")
            if chunk_id and chunk_id in seen_chunk_ids:
                continue
            if chunk_id:
                seen_chunk_ids.add(chunk_id)
            records.append(item)

    return records


def _supplemental_paths(settings: Settings) -> list[Path]:
    supplemental = [
        settings.legal_corpus_path.parent / "legal_supplemental_corpus.jsonl",
        settings.legal_corpus_path.parent / "legal_case_law_corpus.jsonl",
    ]
    return [path for path in supplemental if path.exists()]
