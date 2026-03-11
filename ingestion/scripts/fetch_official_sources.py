from __future__ import annotations

import argparse
import json
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


USER_AGENT = "NyayaSetuBot/0.1 (+self-hosted legal corpus ingestion)"


def load_sources(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def safe_filename(url: str, content_type: str | None) -> str:
    candidate = Path(urlparse(url).path).name or "download"
    extension = Path(candidate).suffix
    if not extension and content_type:
        extension = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".bin"
        candidate = f"{candidate}{extension}"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", candidate)


def extract_links(html: str, base_url: str, source: dict) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    allowed_domains = source.get("allowed_domains", [])
    link_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in source.get("link_regex", [])]
    keywords = [keyword.lower() for keyword in source.get("keywords", [])]

    assets: list[dict] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = urljoin(base_url, anchor["href"])
        netloc = urlparse(href).netloc
        if allowed_domains and not any(netloc == domain or netloc.endswith(f".{domain}") for domain in allowed_domains):
            continue
        anchor_text = " ".join(anchor.stripped_strings)
        haystack = f"{anchor_text} {href}".lower()
        if link_patterns and not any(pattern.search(href) or pattern.search(anchor_text) for pattern in link_patterns):
            continue
        if href in seen:
            continue
        seen.add(href)
        assets.append(
            {
                "url": href,
                "discovered_title": anchor_text,
                "keyword_score": sum(1 for keyword in keywords if keyword in haystack),
            }
        )
    return sorted(assets, key=lambda item: item["keyword_score"], reverse=True)


def discover_assets(source: dict, client: httpx.Client) -> list[dict]:
    fetcher = source["fetcher"]
    if fetcher == "direct_url":
        return [{"url": source["url"], "discovered_title": source.get("title", source["source_id"])}]
    if fetcher == "html_pdf_links":
        response = client.get(source["index_url"], follow_redirects=True)
        response.raise_for_status()
        return extract_links(response.text, source["index_url"], source)
    raise ValueError(f"Unsupported fetcher: {fetcher}")


def download_asset(source: dict, asset: dict, raw_dir: Path, client: httpx.Client) -> dict:
    source_dir = raw_dir / source["source_id"]
    ensure_directory(source_dir)

    response = client.get(asset["url"], follow_redirects=True)
    response.raise_for_status()
    content_type = response.headers.get("content-type")
    filename = safe_filename(asset["url"], content_type)
    local_path = source_dir / filename
    local_path.write_bytes(response.content)

    return {
        "source_id": source["source_id"],
        "title": source.get("title"),
        "source_type": source["source_type"],
        "document_type": source.get("document_type", source["source_type"]),
        "jurisdiction": source.get("jurisdiction", "India"),
        "court": source.get("court"),
        "language": source.get("language"),
        "citation": source.get("citation"),
        "source_url": source.get("index_url") or source.get("url"),
        "download_url": asset["url"],
        "discovered_title": asset.get("discovered_title"),
        "local_path": str(local_path),
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    ensure_directory(path.parent)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=True) for row in rows), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download official government and court sources for NyayaSetu.")
    parser.add_argument("--manifest", default="ingestion/configs/official_sources.json")
    parser.add_argument("--raw-dir", default="ingestion/raw")
    parser.add_argument("--output-manifest", default="ingestion/manifest/download_manifest.jsonl")
    parser.add_argument("--limit-per-source", type=int, default=0)
    args = parser.parse_args()

    sources = load_sources(Path(args.manifest))
    records: list[dict] = []
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(headers=headers, timeout=90.0) as client:
        for source in sources:
            assets = discover_assets(source, client)
            source_limit = args.limit_per_source or int(source.get("limit", 0) or 0)
            selected_assets = assets[:source_limit] if source_limit else assets
            for asset in selected_assets:
                try:
                    records.append(download_asset(source, asset, Path(args.raw_dir), client))
                except Exception as exc:
                    records.append(
                        {
                            "source_id": source["source_id"],
                            "download_url": asset["url"],
                            "status": "error",
                            "error": str(exc),
                            "downloaded_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )

    write_jsonl(Path(args.output_manifest), records)
    successful = sum(1 for record in records if record.get("local_path"))
    print(f"Recorded {len(records)} manifest rows with {successful} successful downloads.")


if __name__ == "__main__":
    main()
