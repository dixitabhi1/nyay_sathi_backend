from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup
from pypdf import PdfReader


SECTION_REGEX = re.compile(r"(?im)^(section\s+\d+[a-zA-Z-]*\.?.*|chapter\s+[ivxlcdm]+.*|\d+\.\s+.+)$")
SHORT_TITLE_START_REGEX = re.compile(r"(?im)^\s*1\.\s+short title[^\n]*$")
SECTION_HEADING_REGEX = re.compile(r"(?im)^\s*(?P<number>\d+[A-Za-z-]*)\.\s*[—–-]?\s*(?P<title>[^\n]+?)\s*$")
SECTION_NUMBER_REGEX = re.compile(r"(?i)(?:section\s+)?(\d+[A-Za-z-]*)")
SUBSECTION_SPLIT_REGEX = re.compile(r"(?=(?:^|\n)\((\d+[A-Za-z]?)\)\s+)")
CITATION_PATTERNS = [
    re.compile(r"\b(?:Section|Sections)\s+\d+[A-Za-z-]*(?:\s*(?:to|-)\s*\d+[A-Za-z-]*)?", re.IGNORECASE),
    re.compile(r"\b\d{4}\s+INSC\s+\d+\b", re.IGNORECASE),
    re.compile(r"\b(?:AIR|SCC|CriLJ)\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\bArticle\s+\d+[A-Za-z-]*\b", re.IGNORECASE),
]


def stable_id(*parts: str) -> str:
    return hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()


def read_text_from_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix in {".html", ".htm"}:
        soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "lxml")
        return soup.get_text("\n", strip=True)
    return path.read_text(encoding="utf-8", errors="ignore")


def normalize_text(text: str) -> str:
    cleaned = text.replace("\xa0", " ").replace("\u200b", "")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"(?m)^\s*\d+\s*$", "", cleaned)
    return cleaned.strip()


def trim_statute_front_matter(text: str) -> str:
    if "ARRANGEMENT OF SECTIONS" in text.upper():
        short_title_matches = list(SHORT_TITLE_START_REGEX.finditer(text))
        if len(short_title_matches) >= 2:
            return text[short_title_matches[1].start():]
        if short_title_matches:
            return text[short_title_matches[0].start():]

    marker_candidates = [
        "BE it enacted by Parliament",
        "BE it enacted",
    ]
    for marker in marker_candidates:
        position = text.find(marker)
        if position > 0:
            return text[position:]
    return text


def detect_language(text: str) -> str:
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"
    return "en"


def extract_citations(text: str) -> list[str]:
    seen: list[str] = []
    for pattern in CITATION_PATTERNS:
        for match in pattern.findall(text):
            citation = re.sub(r"\s+", " ", match.strip())
            if citation not in seen:
                seen.append(citation)
    return seen


def summarize_text(text: str, source_type: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [sentence.strip() for sentence in sentences if len(sentence.strip()) > 30]
    if not sentences:
        return text[:400]
    if source_type == "judgment":
        preferred = [
            sentence
            for sentence in sentences
            if any(keyword in sentence.lower() for keyword in ("held", "issue", "question", "therefore", "ordered"))
        ]
        picked = preferred[:2] or sentences[:2]
        return " ".join(picked)[:500]
    return " ".join(sentences[:2])[:400]


def chunk_text(text: str, chunk_chars: int, overlap: int) -> list[str]:
    if len(text) <= chunk_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_chars)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


def split_statute_sections(text: str) -> list[tuple[str, str]]:
    heading_matches = list(SECTION_HEADING_REGEX.finditer(text))
    if heading_matches:
        sections: list[tuple[str, str]] = []
        for index, match in enumerate(heading_matches):
            start = match.start()
            end = heading_matches[index + 1].start() if index + 1 < len(heading_matches) else len(text)
            block = text[start:end].strip()
            if not block:
                continue
            sections.append((match.group(0).strip(), block))
        if sections:
            return sections

    lines = [line.strip() for line in text.splitlines()]
    blocks: list[tuple[str, list[str]]] = []
    current_heading = "Preamble"
    current_lines: list[str] = []
    for line in lines:
        if not line:
            continue
        if SECTION_REGEX.match(line):
            if current_lines:
                blocks.append((current_heading, current_lines))
            current_heading = line
            current_lines = []
            continue
        current_lines.append(line)
    if current_lines:
        blocks.append((current_heading, current_lines))
    return [(heading, "\n".join(block_lines).strip()) for heading, block_lines in blocks if block_lines]


def extract_section_number(heading: str) -> str | None:
    match = SECTION_NUMBER_REGEX.search(heading)
    if not match:
        return None
    return match.group(1)


def split_statute_subsections(section_text: str) -> list[tuple[str, str]]:
    matches = list(SUBSECTION_SPLIT_REGEX.finditer(section_text))
    if len(matches) <= 1:
        return []

    subsections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        label = match.group(1)
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section_text)
        body = section_text[start:end].strip()
        if body:
            subsections.append((label, body))
    return subsections


def build_statute_chunks(document: dict) -> list[dict]:
    sections = split_statute_sections(document["text"])
    chunks: list[dict] = []
    if not sections:
        sections = [(document["citation"] or document["title"], document["text"])]
    for section_index, (heading, section_text) in enumerate(sections, start=1):
        section_number = extract_section_number(heading)
        subsection_blocks = split_statute_subsections(section_text)
        if subsection_blocks and section_number:
            granular_units = [
                (f"Section {section_number}({subsection_label})", subsection_text, "statute_subsection")
                for subsection_label, subsection_text in subsection_blocks
            ]
        else:
            citation_suffix = f"Section {section_number}" if section_number else (
                heading if heading.lower().startswith("section") else f"Section Block {section_index}"
            )
            granular_units = [(citation_suffix, section_text, "statute_section")]

        for granular_heading, granular_text, strategy in granular_units:
            for local_index, chunk in enumerate(chunk_text(granular_text, chunk_chars=1200, overlap=160), start=1):
                chunk_id = stable_id(document["document_id"], str(section_index), granular_heading, strategy, str(local_index))
                chunk_summary = summarize_text(chunk, "statute")
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "document_id": document["document_id"],
                        "source_id": document["source_id"],
                        "title": document["title"],
                        "citation": f"{document['citation']} | {granular_heading}" if document.get("citation") else granular_heading,
                        "source_type": document["source_type"],
                        "document_type": document["document_type"],
                        "jurisdiction": document["jurisdiction"],
                        "language": document["language"],
                        "source_url": document["source_url"],
                        "text": chunk,
                        "summary": chunk_summary,
                        "linked_citations": extract_citations(chunk),
                        "chunk_strategy": strategy,
                        "chunk_size": len(chunk),
                    }
                )
    return chunks


def build_judgment_chunks(document: dict) -> list[dict]:
    paragraphs = [paragraph.strip() for paragraph in document["text"].split("\n\n") if len(paragraph.strip()) > 40]
    windows = chunk_text("\n\n".join(paragraphs), chunk_chars=1500, overlap=220)
    chunks: list[dict] = []
    for index, chunk in enumerate(windows, start=1):
        chunk_id = stable_id(document["document_id"], str(index))
        chunks.append(
            {
                "chunk_id": chunk_id,
                "document_id": document["document_id"],
                "source_id": document["source_id"],
                "title": document["title"],
                "citation": document["citation"] or document["title"],
                "source_type": document["source_type"],
                "document_type": document["document_type"],
                "jurisdiction": document["jurisdiction"],
                "language": document["language"],
                "source_url": document["source_url"],
                "text": chunk,
                "summary": summarize_text(chunk, "judgment"),
                "linked_citations": extract_citations(chunk),
                "chunk_strategy": "judgment_passage",
                "chunk_size": len(chunk),
            }
        )
    return chunks


def build_document_record(download_row: dict, raw_text: str) -> dict:
    document_type = download_row.get("document_type", download_row["source_type"])
    if document_type == "act":
        raw_text = trim_statute_front_matter(raw_text)

    language = download_row.get("language") or detect_language(raw_text)
    source_url = download_row.get("download_url") or download_row.get("source_url") or ""
    document_id = stable_id(download_row["source_id"], source_url or download_row["local_path"])
    title = download_row.get("discovered_title") or download_row.get("title") or Path(download_row["local_path"]).stem
    citation = download_row.get("citation") or title
    return {
        "document_id": document_id,
        "source_id": download_row["source_id"],
        "title": title,
        "citation": citation,
        "source_type": download_row["source_type"],
        "document_type": document_type,
        "jurisdiction": download_row.get("jurisdiction", "India"),
        "language": language,
        "source_url": source_url,
        "local_path": download_row["local_path"],
        "summary": summarize_text(raw_text, download_row["source_type"]),
        "text_length": len(raw_text),
        "text": raw_text,
        "content_hash": stable_id(raw_text[:2000], str(len(raw_text))),
    }


def dumps_jsonl(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=True) for row in rows), encoding="utf-8")
