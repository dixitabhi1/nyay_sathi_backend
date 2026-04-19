from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen

from app.core.config import DEFAULT_REMOTE_CASE_LAW_CORPUS_URL, Settings


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
    case_law_path = settings.legal_corpus_path.parent / "legal_case_law_corpus.jsonl"
    remote_case_law_path = _ensure_remote_case_law_corpus(settings, case_law_path)
    supplemental = [
        settings.legal_corpus_path.parent / "legal_supplemental_corpus.jsonl",
        case_law_path,
    ]
    if remote_case_law_path != case_law_path:
        supplemental.append(remote_case_law_path)
    return [path for path in supplemental if path.exists()]


def _ensure_remote_case_law_corpus(settings: Settings, local_case_law_path: Path) -> Path:
    if local_case_law_path.exists():
        return local_case_law_path

    remote_url = settings.remote_case_law_corpus_url.strip()
    if not remote_url and settings.is_huggingface_space:
        remote_url = DEFAULT_REMOTE_CASE_LAW_CORPUS_URL
    if not remote_url:
        return local_case_law_path

    cache_root = (
        settings.persistent_storage_root / "data" / "corpus"
        if settings.persistent_storage_root
        else local_case_law_path.parent
    )
    cache_path = cache_root / "legal_case_law_corpus.jsonl"
    if cache_path.exists():
        return cache_path

    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        request = Request(remote_url, headers={"User-Agent": "NyayaSetu corpus bootstrap/1.0"})
        with urlopen(request, timeout=90) as response:
            cache_path.write_bytes(response.read())
    except Exception:
        return local_case_law_path
    return cache_path
