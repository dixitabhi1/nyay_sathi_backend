from __future__ import annotations

import argparse
import io
import json
import re
import sys
import tarfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable
from urllib.parse import quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.scripts.legal_corpus_utils import (  # noqa: E402
    dumps_jsonl,
    extract_citations,
    normalize_text,
    stable_id,
    summarize_text,
)


SC_BUCKET = "https://indian-supreme-court-judgments.s3.amazonaws.com"
HC_BUCKET = "https://indian-high-court-judgments.s3.ap-south-1.amazonaws.com"
DEFAULT_SUPREME_COURT_YEARS = [2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018]
DEFAULT_HIGH_COURT_YEARS = [2025, 2024]
CASE_FIELD_KEYS = (
    "case_title",
    "court",
    "parties",
    "decision_date",
    "case_number",
    "verdict",
    "bench",
    "cnr",
    "dataset",
    "dataset_registry",
    "source_pdf",
)


@dataclass(frozen=True)
class CourtRecord:
    source_id: str
    title: str
    citation: str
    court: str
    source_url: str
    text: str
    parties: str = ""
    decision_date: str = ""
    case_number: str = ""
    verdict: str = ""
    bench: str = ""
    cnr: str = ""
    dataset: str = ""
    dataset_registry: str = ""
    source_pdf: str = ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Import real Indian Supreme Court and High Court case-law metadata/headnotes "
            "from public Dattam/OpenJustice AWS datasets into NyayaSetu corpus JSONL."
        )
    )
    parser.add_argument("--output", default="data/corpus/legal_case_law_corpus.jsonl")
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--supreme-court-limit", type=int, default=5500)
    parser.add_argument("--high-court-limit", type=int, default=4500)
    parser.add_argument("--supreme-court-years", nargs="*", type=int, default=DEFAULT_SUPREME_COURT_YEARS)
    parser.add_argument("--high-court-years", nargs="*", type=int, default=DEFAULT_HIGH_COURT_YEARS)
    parser.add_argument("--max-text-chars", type=int, default=4500)
    parser.add_argument("--skip-high-courts", action="store_true")
    parser.add_argument("--skip-supreme-court", action="store_true")
    args = parser.parse_args()

    rows: list[dict] = []
    remaining = args.limit

    if not args.skip_supreme_court and remaining > 0:
        sc_limit = min(args.supreme_court_limit, remaining)
        sc_records = list(iter_supreme_court_records(args.supreme_court_years, sc_limit, args.max_text_chars))
        rows.extend(to_corpus_rows(sc_records))
        remaining = args.limit - len(rows)
        print(f"Imported {len(sc_records)} Supreme Court records.")

    if not args.skip_high_courts and remaining > 0:
        hc_limit = min(args.high_court_limit, remaining)
        hc_records = list(iter_high_court_records(args.high_court_years, hc_limit, args.max_text_chars))
        rows.extend(to_corpus_rows(hc_records))
        print(f"Imported {len(hc_records)} High Court records.")

    rows = dedupe_rows(rows)[: args.limit]
    if not rows:
        raise SystemExit("No case-law rows were imported. Check network access and dataset availability.")

    dumps_jsonl(rows, Path(args.output))
    print(f"Wrote {len(rows)} verified case-law rows to {args.output}.")


def iter_supreme_court_records(years: Iterable[int], limit: int, max_text_chars: int) -> Iterable[CourtRecord]:
    imported = 0
    for year in years:
        if imported >= limit:
            break
        metadata_url = f"{SC_BUCKET}/metadata/tar/year={year}/metadata.tar"
        try:
            raw_tar = fetch_bytes(metadata_url)
        except Exception as exc:
            print(f"Skipping Supreme Court year {year}: {exc}")
            continue

        with tarfile.open(fileobj=io.BytesIO(raw_tar), mode="r:") as archive:
            for member in archive:
                if imported >= limit:
                    break
                if not member.isfile() or not member.name.endswith(".json"):
                    continue
                file_obj = archive.extractfile(member)
                if not file_obj:
                    continue
                try:
                    payload = json.loads(file_obj.read().decode("utf-8", errors="ignore"))
                except json.JSONDecodeError:
                    continue
                record = parse_supreme_court_metadata(payload, member.name, year, max_text_chars)
                if record:
                    imported += 1
                    yield record


def iter_high_court_records(years: Iterable[int], limit: int, max_text_chars: int) -> Iterable[CourtRecord]:
    imported = 0
    for year in years:
        if imported >= limit:
            break
        metadata_archives = sorted(
            (
                item
                for item in list_s3_objects(HC_BUCKET, f"metadata/tar/year={year}/")
                if item["key"].endswith("metadata.tar.gz")
            ),
            key=lambda item: item["size"],
        )
        for metadata_object in metadata_archives:
            if imported >= limit:
                break
            metadata_key = metadata_object["key"]
            if not metadata_key.endswith("metadata.tar.gz"):
                continue
            match = re.search(r"year=(?P<year>\d+)/court=(?P<court>[^/]+)/bench=(?P<bench>[^/]+)/", metadata_key)
            if not match:
                continue
            court_code = match.group("court")
            bench_code = match.group("bench")
            metadata_url = f"{HC_BUCKET}/{quote(metadata_key, safe='/=')}"
            try:
                raw_tar = fetch_bytes(metadata_url)
            except Exception as exc:
                print(f"Skipping High Court metadata archive {metadata_key}: {exc}")
                continue
            with tarfile.open(fileobj=io.BytesIO(raw_tar), mode="r:gz") as archive:
                for member in archive:
                    if imported >= limit:
                        break
                    if not member.isfile() or not member.name.endswith(".json"):
                        continue
                    file_obj = archive.extractfile(member)
                    if not file_obj:
                        continue
                    try:
                        payload = json.loads(file_obj.read().decode("utf-8", errors="ignore"))
                    except json.JSONDecodeError:
                        continue
                    record = parse_high_court_metadata(
                        payload=payload,
                        member_name=member.name,
                        year=year,
                        court_code=court_code,
                        bench_code=bench_code,
                        max_text_chars=max_text_chars,
                    )
                    if record:
                        imported += 1
                        yield record


def parse_supreme_court_metadata(
    payload: dict,
    member_name: str,
    year: int,
    max_text_chars: int,
) -> CourtRecord | None:
    raw_html = str(payload.get("raw_html") or "")
    if not raw_html.strip():
        return None
    soup = BeautifulSoup(raw_html, "lxml")
    title = clean_title(extract_button_label(soup) or extract_strong_case_title(soup) or Path(member_name).stem)
    text = clean_html_text(soup)
    if len(text) < 120:
        return None
    nc_display = str(payload.get("nc_display") or "")
    citation = (
        first_match(r"\b\d{4}\s+INSC\s+\d+\b", raw_html)
        or nc_display
        or first_match(r"\[\d{4}\]\s+\d+\s+S\.C\.R\.\s+\d+", text)
        or Path(member_name).stem
    )
    decision_date = labelled_value(text, "Decision Date")
    case_number = labelled_value(text, "Case No")
    verdict = labelled_value(text, "Disposal Nature")
    bench = labelled_value(text, "Bench")
    base_name = Path(member_name).stem
    pdf_name = f"{base_name}_EN.pdf"
    source_url = f"{SC_BUCKET}/data/tar/year={year}/english/english.tar#{pdf_name}"
    parties = split_parties(title)
    body = build_case_text(
        title=title,
        court="Supreme Court of India",
        citation=citation,
        parties=parties,
        decision_date=decision_date,
        case_number=case_number,
        verdict=verdict,
        bench=bench,
        extracted=text,
        max_text_chars=max_text_chars,
    )
    return CourtRecord(
        source_id="indian_supreme_court_judgments_aws",
        title=title,
        citation=citation,
        court="Supreme Court of India",
        source_url=source_url,
        text=body,
        parties=parties,
        decision_date=decision_date,
        case_number=case_number,
        verdict=verdict,
        bench=bench,
        dataset="Dattam Labs Indian Supreme Court Judgments",
        dataset_registry="https://registry.opendata.aws/indian-supreme-court-judgments/",
        source_pdf=pdf_name,
    )


def parse_high_court_metadata(
    payload: dict,
    member_name: str,
    year: int,
    court_code: str,
    bench_code: str,
    max_text_chars: int,
) -> CourtRecord | None:
    raw_html = str(payload.get("raw_html") or "")
    if not raw_html.strip():
        return None
    soup = BeautifulSoup(raw_html, "lxml")
    court = str(payload.get("court_name") or labelled_value(clean_html_text(soup), "Court") or "High Court of India")
    title = clean_title(extract_button_label(soup) or extract_strong_case_title(soup) or Path(member_name).stem)
    text = clean_html_text(soup)
    if len(text) < 100:
        return None
    cnr = labelled_value(text, "CNR")
    decision_date = labelled_value(text, "Decision Date")
    verdict = labelled_value(text, "Disposal Nature")
    case_number = first_match(r"\b[A-Z][A-Za-z()./ -]+No\.?\s*[\w./-]+(?:\s+of\s+\d{4})?", text)
    judge = labelled_value(text, "Judge")
    pdf_link = str(payload.get("pdf_link") or "")
    pdf_name = Path(pdf_link).name or f"{Path(member_name).stem}.pdf"
    source_url = f"{HC_BUCKET}/data/pdf/year={year}/court={court_code}/bench={bench_code}/{quote(pdf_name)}"
    citation = cnr or case_number or Path(member_name).stem
    parties = split_parties(title)
    body = build_case_text(
        title=title,
        court=court,
        citation=citation,
        parties=parties,
        decision_date=decision_date,
        case_number=case_number,
        verdict=verdict,
        bench=judge,
        extracted=text,
        max_text_chars=max_text_chars,
    )
    return CourtRecord(
        source_id="indian_high_court_judgments_aws",
        title=title,
        citation=citation,
        court=court,
        source_url=source_url,
        text=body,
        parties=parties,
        decision_date=decision_date,
        case_number=case_number,
        verdict=verdict,
        bench=judge,
        cnr=cnr,
        dataset="Dattam Labs Indian High Court Judgments",
        dataset_registry="https://registry.opendata.aws/indian-high-court-judgments/",
        source_pdf=pdf_name,
    )


def to_corpus_rows(records: Iterable[CourtRecord]) -> list[dict]:
    rows: list[dict] = []
    accessed_on = date.today().isoformat()
    for record in records:
        document_id = stable_id(record.source_id, record.source_url, record.citation)
        text = normalize_text(record.text)
        summary = summarize_text(text, "judgment")
        row = {
            "chunk_id": stable_id(document_id, "case_law_metadata"),
            "document_id": document_id,
            "source_id": record.source_id,
            "title": record.title,
            "citation": record.citation,
            "source_type": "judgment",
            "document_type": "case_law",
            "jurisdiction": "India",
            "language": "en",
            "source_url": record.source_url,
            "text": text,
            "summary": summary,
            "linked_citations": extract_citations(text),
            "chunk_strategy": "judgment_metadata_headnote",
            "chunk_size": len(text),
            "case_title": record.title,
            "court": record.court,
            "parties": record.parties,
            "decision_date": record.decision_date,
            "case_number": record.case_number,
            "verdict": record.verdict,
            "bench": record.bench,
            "cnr": record.cnr,
            "dataset": record.dataset,
            "dataset_registry": record.dataset_registry,
            "source_pdf": record.source_pdf,
            "accessed_on": accessed_on,
        }
        rows.append(row)
    return rows


def dedupe_rows(rows: list[dict]) -> list[dict]:
    seen: set[str] = set()
    deduped: list[dict] = []
    for row in rows:
        key = str(row.get("source_url") or row.get("chunk_id"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def build_case_text(
    *,
    title: str,
    court: str,
    citation: str,
    parties: str,
    decision_date: str,
    case_number: str,
    verdict: str,
    bench: str,
    extracted: str,
    max_text_chars: int,
) -> str:
    header = [
        f"Case Title: {title}",
        f"Court: {court}",
        f"Citation: {citation}",
        f"Parties: {parties}" if parties else "",
        f"Decision Date: {decision_date}" if decision_date else "",
        f"Case Number: {case_number}" if case_number else "",
        f"Verdict / Disposal: {verdict}" if verdict else "",
        f"Bench / Judge: {bench}" if bench else "",
        "Source note: This record is imported from public AWS Open Data court-judgment datasets managed by Dattam Labs/OpenJustice. Use the linked source document for verification.",
        "",
        "Extracted metadata, headnotes, and visible text:",
    ]
    content = "\n".join(part for part in header if part).strip()
    remaining = max(500, max_text_chars - len(content))
    return f"{content}\n{extracted[:remaining]}".strip()


def extract_button_label(soup: BeautifulSoup) -> str:
    buttons = soup.find_all("button", attrs={"aria-label": True})
    button = next(
        (
            candidate
            for candidate in buttons
            if "pdf" in str(candidate.get("aria-label") or "").lower()
            or "open_pdf" in str(candidate.get("onclick") or "").lower()
        ),
        None,
    )
    if button:
        label = str(button.get("aria-label") or "")
        return re.sub(r"\s+pdf\s*$", "", label, flags=re.IGNORECASE).strip()
    button = next(
        (
            candidate
            for candidate in soup.find_all("button")
            if "open_pdf" in str(candidate.get("onclick") or "").lower()
        ),
        None,
    )
    return button.get_text(" ", strip=True) if button else ""


def extract_strong_case_title(soup: BeautifulSoup) -> str:
    for strong in soup.find_all("strong"):
        text = strong.get_text(" ", strip=True)
        if re.search(r"\b(vs\.?|versus|v\.?)\b", text, re.IGNORECASE):
            return text
    return ""


def clean_html_text(soup: BeautifulSoup) -> str:
    for modal in soup.find_all(id=re.compile("DisclaimerModal", re.IGNORECASE)):
        modal.decompose()
    for modal in soup.find_all(class_=lambda value: value and "modal" in str(value).lower()):
        modal.decompose()
    for tag in soup(["script", "style", "select", "input"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"Disclaimer\s+Due care and caution.*?(?=[A-Z][A-Z .&]+(?:versus|Vs))", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*(Split view|HTML view|Flip view|PDF)\s*", " ", text, flags=re.IGNORECASE)
    return normalize_text(text)


def clean_title(title: str) -> str:
    cleaned = re.sub(r"\s+", " ", title).strip(" -")
    cleaned = re.sub(r"\bpdf\b$", "", cleaned, flags=re.IGNORECASE).strip(" -")
    cleaned = cleaned.replace(" .Array[93]. ", " Vs ")
    cleaned = re.sub(r"\s+versus\s+", " versus ", cleaned, flags=re.IGNORECASE)
    return cleaned[:240] or "Untitled judgment"


def split_parties(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip()


def labelled_value(text: str, label: str) -> str:
    pattern = rf"{re.escape(label)}\s*:\s*(?P<value>[^|<\n]+)"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return ""
    value = match.group("value").strip(" :-")
    value = re.split(r"\s+(?:Split view|HTML view|Flip view|PDF)\b", value, flags=re.IGNORECASE)[0]
    value = re.split(
        r"\s+(?:Court|CNR|Decision Date|Disposal Nature|Date of registration)\s*:",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return value.strip(" :-")


def first_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(0).strip() if match else ""


def list_s3_objects(bucket_url: str, prefix: str) -> Iterable[dict[str, int | str]]:
    continuation: str | None = None
    namespace = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
    while True:
        url = f"{bucket_url}/?list-type=2&prefix={quote(prefix, safe='/=')}"
        if continuation:
            url += f"&continuation-token={quote(continuation)}"
        data = fetch_bytes(url)
        root = ET.fromstring(data)
        for item_node in root.findall("s3:Contents", namespace):
            key_node = item_node.find("s3:Key", namespace)
            size_node = item_node.find("s3:Size", namespace)
            if key_node is not None and key_node.text:
                yield {
                    "key": key_node.text,
                    "size": int(size_node.text) if size_node is not None and size_node.text else 0,
                }
        token_node = root.find("s3:NextContinuationToken", namespace)
        if token_node is None or not token_node.text:
            break
        continuation = token_node.text


def fetch_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "NyayaSetu corpus importer/1.0"})
    with urlopen(request, timeout=120) as response:
        return response.read()


if __name__ == "__main__":
    main()
