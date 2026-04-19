from __future__ import annotations

import argparse
import csv
import json
import random
import re
from pathlib import Path


CITATION_PATTERNS = (
    re.compile(r"\b(?:IPC|BNS|BNSS|BSA)\s+Section\s+[0-9A-Za-z()/-]+\b", re.IGNORECASE),
    re.compile(r"\bSection\s+[0-9A-Za-z()/-]+\s+of\s+the\s+[A-Za-z ]+\b", re.IGNORECASE),
    re.compile(r"\bAct No\.\s+\d+\s+of\s+\d{4}\s+\|\s+Section\s+[0-9A-Za-z()/-]+(?:\([0-9A-Za-z/-]+\))?", re.IGNORECASE),
)
NOISY_CORPUS_MARKERS = (
    "FORM NO.",
    "SEAL OF THE COURT",
    "BOND AND BAIL-BOND",
    "SURETY",
    "................................",
    "OMITTED BY",
    "SUBS. BY ACT",
    "STRIKE OUT",
)
ACT_TITLE_MARKERS = ("sanhita", "adhiniyam", "penal code", "code of criminal procedure", "act, 20", "act, 18")


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def merge_jsonl(paths: list[Path]) -> list[dict]:
    merged: list[dict] = []
    seen_keys: set[str] = set()
    for path in paths:
        for row in load_jsonl(path):
            key = normalize_text(row.get("chunk_id") or row.get("citation") or row.get("question") or json.dumps(row, ensure_ascii=True))
            if key.lower() in seen_keys:
                continue
            seen_keys.add(key.lower())
            merged.append(row)
    return merged


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=True) for row in rows), encoding="utf-8")


def load_mappings(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [row for row in reader if any(row.values())]


def normalize_text(text: str, max_chars: int | None = None) -> str:
    cleaned = (text or "")
    replacements = {
        "\u2014": " - ",
        "\u2013": " - ",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00a0": " ",
    }
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    cleaned = cleaned.replace("\r", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if max_chars is not None:
        return cleaned[:max_chars]
    return cleaned


def ensure_period(text: str) -> str:
    cleaned = normalize_text(text)
    if not cleaned:
        return cleaned
    if cleaned[-1] in ".!?":
        return cleaned
    return f"{cleaned}."


def unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = normalize_text(value)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
    return ordered


def split_sentences(text: str) -> list[str]:
    cleaned = normalize_text(text)
    if not cleaned:
        return []
    cleaned = cleaned.replace("Act No.", "Act No<dot>")
    cleaned = cleaned.replace("No.", "No<dot>")
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    restored = [part.replace("Act No<dot>", "Act No.").replace("No<dot>", "No.") for part in parts]
    return [part.strip() for part in restored if part.strip()]


def first_sentence(text: str, max_chars: int = 260) -> str:
    sentences = split_sentences(text)
    if sentences:
        return normalize_text(sentences[0], max_chars)
    return normalize_text(text, max_chars)


def best_context_sentence(text: str, max_chars: int = 260) -> str:
    sentences = split_sentences(text)
    for sentence in sentences:
        normalized = normalize_text(sentence, max_chars)
        if len(normalized) < 40:
            continue
        if normalized.lower().startswith("act no.") and normalized.count(" ") < 7:
            continue
        return normalized
    return first_sentence(text, max_chars)


def lower_first(text: str) -> str:
    cleaned = normalize_text(text)
    if not cleaned:
        return cleaned
    return cleaned[0].lower() + cleaned[1:]


def looks_like_section_text(text: str) -> bool:
    cleaned = normalize_text(text)
    if not cleaned:
        return False
    if re.match(r"^[a-z]", cleaned):
        return False
    if not re.match(r"^\(?\d+[A-Za-z()/-]*\)?[.:]?\s*", cleaned):
        return False
    if " - " not in cleaned and "." not in cleaned[:140]:
        return False
    return True


def extract_citations(text: str) -> list[str]:
    matches: list[str] = []
    for pattern in CITATION_PATTERNS:
        matches.extend(pattern.findall(text or ""))
    return unique_preserving_order(matches)


def derive_steps(hint_text: str) -> list[str]:
    normalized = normalize_text(hint_text).lower()
    if any(keyword in normalized for keyword in ("landlord", "tenant", "security deposit", "rent agreement", "deposit receipt", "lease")):
        return [
            "Collect the agreement, payment proof, deposit receipt, and handover or move-out records in one place.",
            "Send a clear written demand for the deposit and keep proof of delivery or acknowledgement.",
            "Get legal advice on the best civil or criminal route if the other side still refuses to return the money.",
        ]
    if any(keyword in normalized for keyword in ("fraud", "otp", "payment", "bank", "cheating", "seller", "transaction")):
        return [
            "Preserve transaction IDs, bank alerts, payment screenshots, and chat records.",
            "Write down the exact timeline, account numbers, phone numbers, and platform details.",
            "Report quickly to the bank, platform, and police because delay can hurt recovery options.",
        ]
    if any(keyword in normalized for keyword in ("arrest", "bail", "detention", "interrogation")):
        return [
            "Ask for the grounds of arrest and keep a copy of any arrest or bail paperwork.",
            "Inform a family member or trusted person and contact a lawyer quickly.",
            "Record the time, place, officer details, and any medical issues without delay.",
        ]
    if any(keyword in normalized for keyword in ("fir", "cognizable", "police refuse", "station house officer", "magistrate", "refusal details", "register the information")):
        return [
            "Write down the facts in date-wise order and keep copies of every complaint you submit.",
            "Preserve the refusal details, station name, officer details, and any receiving copy or email proof.",
            "Escalate quickly to senior police officers or a Magistrate if the matter is urgent.",
        ]
    if any(keyword in normalized for keyword in ("whatsapp", "electronic", "evidence", "record", "document")):
        return [
            "Keep the original device, export the chats or files, and preserve timestamps.",
            "Do not edit or crop the material in a way that hides context or metadata.",
            "Ask for legal review if admissibility or certification of the record will matter.",
        ]
    return [
        "Write down the facts in simple date-wise order before taking the next legal step.",
        "Preserve the original documents, screenshots, messages, and witness details.",
        "Get lawyer review quickly if the issue could lead to police action or court process.",
    ]


def format_grounding(citations: list[str]) -> str | None:
    ordered = unique_preserving_order(citations)
    if not ordered:
        return None
    return ", ".join(ordered[:3])


def format_section_list(citations: list[str]) -> str | None:
    ordered = unique_preserving_order(citations)
    if not ordered:
        return None
    return "\n- " + "\n- ".join(ordered[:3])


def format_answer(
    legal_position: str,
    why_it_matters: str | None = None,
    steps: list[str] | None = None,
    grounding: list[str] | None = None,
) -> str:
    sections = [f"Short answer: {ensure_period(legal_position)}"]
    if why_it_matters:
        sections.append(f"Why it matters: {ensure_period(why_it_matters)}")
    section_list = format_section_list(grounding or [])
    if section_list:
        sections.append(f"Most relevant sections:{section_list}")
    if steps:
        sections.append("Practical next steps:\n- " + "\n- ".join(steps[:3]))
    grounding_text = format_grounding(grounding or [])
    if grounding_text:
        sections.append(f"Grounded citations: {grounding_text}.")
    return "\n\n".join(sections)


def is_high_quality_corpus_row(row: dict) -> bool:
    text = normalize_text(row.get("text", ""))
    citation = normalize_text(row.get("citation", ""))
    if len(text) < 80:
        return False
    if not citation:
        return False
    upper_text = text.upper()
    if any(marker in upper_text for marker in NOISY_CORPUS_MARKERS):
        return False
    if re.search(r"\.{8,}", text):
        return False
    if text.count("_") > 12:
        return False
    lowered = text.lower()
    if any(marker in lowered for marker in ("struck down", "shreya singhal", "repealed", "omitted by act")):
        return False
    if not looks_like_section_text(text):
        return False
    return True


def derive_section_label(row: dict) -> str:
    title = normalize_text(row.get("title", ""), 120)
    if title and not any(marker in title.lower() for marker in ACT_TITLE_MARKERS):
        return title

    text = normalize_text(row.get("text") or row.get("summary", ""), 240)
    text = re.sub(r"^\(?\d+[A-Za-z()/-]*\)?[.:]?\s*", "", text)
    if " - " in text:
        heading = text.split(" - ", 1)[0]
        if 4 <= len(heading) <= 110:
            return heading
    heading = text.split(".", 1)[0]
    heading = normalize_text(heading, 110)
    if 4 <= len(heading) <= 110:
        return heading
    return normalize_text(row.get("citation", "this provision"), 110)


def extract_rule_text(text: str) -> str:
    cleaned = normalize_text(text, 900)
    cleaned = re.sub(r"^\(?\d+[A-Za-z()/-]*\)?[.:]?\s*", "", cleaned)
    if " - " in cleaned:
        _, cleaned = cleaned.split(" - ", 1)
    cleaned = re.sub(r"^\([a-z0-9]+\)\s*", "", cleaned, flags=re.IGNORECASE)
    sentence = first_sentence(cleaned, 280)
    return sentence or normalize_text(cleaned, 280)


def build_corpus_explanation(row: dict) -> str:
    label = derive_section_label(row)
    rule = extract_rule_text(row.get("summary") or row.get("text", ""))
    if label.lower() in rule.lower():
        legal_position = rule
    else:
        legal_position = f"{label} means {lower_first(rule)}"
    why_it_matters = f"Use {row['citation']} when the facts match this rule and avoid stretching it beyond the actual ingredients of the section."
    return format_answer(
        legal_position=legal_position,
        why_it_matters=why_it_matters,
        steps=derive_steps(" ".join([label, row.get("citation", ""), row.get("text", "")])),
        grounding=[row["citation"], *row.get("linked_citations", [])],
    )


def build_corpus_takeaway(row: dict) -> str:
    label = derive_section_label(row)
    rule = extract_rule_text(row.get("summary") or row.get("text", ""))
    legal_position = f"{label} may matter where the facts suggest {lower_first(rule)}"
    why_it_matters = f"Use {row['citation']} only when the facts actually line up with the ingredients of the provision."
    return format_answer(
        legal_position=legal_position,
        why_it_matters=why_it_matters,
        steps=derive_steps(" ".join([label, row.get("citation", ""), row.get("text", "")])),
        grounding=[row["citation"], *row.get("linked_citations", [])],
    )


def build_qa_examples(qa_rows: list[dict]) -> list[dict]:
    examples: list[dict] = []
    for row in qa_rows:
        instruction = normalize_text(row["question"], 320)
        context = normalize_text(row.get("context", ""), 2200)
        legal_position = normalize_text(row["answer"], 520)
        citations = extract_citations(context)
        why_it_matters = best_context_sentence(context, 260) if context else None
        steps = derive_steps(" ".join([instruction, context, legal_position]))
        output = format_answer(
            legal_position=legal_position,
            why_it_matters=why_it_matters,
            steps=steps,
            grounding=citations,
        )
        prompt_variants = [
            (instruction, "legal_qa"),
            (f"Explain this in simple language for a citizen: {instruction}", "citizen_plain_language_qa"),
            (f"A user asks: {instruction} Give a grounded answer with practical next steps.", "grounded_legal_guidance"),
            (
                f"Give a short answer, list the most relevant sections, and add practical next steps: {instruction}",
                "grounded_citation_following",
            ),
            (
                f"Answer this using the exact section names from the context and keep it easy to understand: {instruction}",
                "citation_grounded_plain_language",
            ),
        ]
        for variant_instruction, task in prompt_variants:
            examples.append(
                {
                    "instruction": variant_instruction,
                    "input": context,
                    "output": output,
                    "task": task,
                }
            )
    return examples


def build_corpus_examples(corpus_rows: list[dict]) -> list[dict]:
    examples: list[dict] = []
    for row in corpus_rows:
        if not is_high_quality_corpus_row(row):
            continue
        source_text = normalize_text(row.get("text", ""), 2200)
        examples.append(
            {
                "instruction": f"Explain {row['citation']} in plain language.",
                "input": source_text,
                "output": build_corpus_explanation(row),
                "task": f"{row.get('source_type', 'legal')}_explanation",
            }
        )
    return examples


def build_mapping_examples(mapping_rows: list[dict]) -> list[dict]:
    examples: list[dict] = []
    for row in mapping_rows:
        source_citation = normalize_text(row.get("source_citation", ""), 180)
        target_citation = normalize_text(row.get("target_citation", ""), 180)
        notes = normalize_text(row.get("notes", ""), 700)
        relationship = normalize_text(row.get("relationship", "mapped"), 80)
        if not source_citation or not target_citation:
            continue
        output = format_answer(
            legal_position=f"{source_citation} maps most closely to {target_citation}",
            why_it_matters=f"Treat the relationship as {relationship} and verify ingredients, punishment, and exceptions before relying on it.",
            steps=[
                "Read both provisions side by side before suggesting that they are equivalent.",
                "Check whether the conduct, intent, and punishment still line up after the new law.",
                "Flag any uncertainty instead of claiming a one-to-one match without verification.",
            ],
            grounding=[source_citation, target_citation],
        )
        examples.append(
            {
                "instruction": f"If a user cites {source_citation}, which modern provision should NyayaSetu review next?",
                "input": notes,
                "output": output,
                "task": "section_mapping",
            }
        )
    return examples


def dedupe_examples(rows: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict] = []
    for row in rows:
        key = (
            normalize_text(row["instruction"]).lower(),
            normalize_text(row.get("input", "")).lower(),
            normalize_text(row["output"]).lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def split_rows(rows: list[dict], eval_ratio: float, seed: int) -> tuple[list[dict], list[dict]]:
    random.Random(seed).shuffle(rows)
    split_index = max(1, int(len(rows) * (1 - eval_ratio)))
    return rows[:split_index], rows[split_index:]


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare NyayaSetu instruction tuning datasets.")
    parser.add_argument("--qa-path", default="training/data/raw/legal_qa.jsonl")
    parser.add_argument("--statute-expansion-path", default="training/data/raw/legal_statute_expansion_cases.jsonl")
    parser.add_argument("--hard-cases-path", default="training/data/raw/legal_style_hard_cases.jsonl")
    parser.add_argument("--legacy-bridge-path", default="training/data/raw/legal_legacy_bridge_cases.jsonl")
    parser.add_argument("--corpus-path", default="data/corpus/official_legal_corpus.jsonl")
    parser.add_argument("--supplemental-corpus-path", default="data/corpus/legal_supplemental_corpus.jsonl")
    parser.add_argument("--fallback-corpus-path", default="data/sample/legal_corpus/legal_corpus.jsonl")
    parser.add_argument("--mapping-csv", default="ingestion/configs/ipc_bns_mappings.csv")
    parser.add_argument("--output-dir", default="training/data/processed")
    parser.add_argument("--max-corpus-examples", type=int, default=120)
    parser.add_argument("--eval-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    qa_rows = load_jsonl(Path(args.qa_path))
    statute_expansion_rows = load_jsonl(Path(args.statute_expansion_path))
    hard_case_rows = load_jsonl(Path(args.hard_cases_path))
    legacy_bridge_rows = load_jsonl(Path(args.legacy_bridge_path))
    corpus_path = Path(args.corpus_path)
    if not corpus_path.exists():
        corpus_path = Path(args.fallback_corpus_path)
    corpus_rows = merge_jsonl([corpus_path, Path(args.supplemental_corpus_path)])
    mapping_rows = load_mappings(Path(args.mapping_csv))

    examples = []
    examples.extend(build_qa_examples(qa_rows))
    examples.extend(build_qa_examples(statute_expansion_rows))
    examples.extend(build_qa_examples(hard_case_rows))
    examples.extend(build_qa_examples(legacy_bridge_rows))
    corpus_examples = build_corpus_examples(corpus_rows)
    random.Random(args.seed).shuffle(corpus_examples)
    if args.max_corpus_examples >= 0:
        corpus_examples = corpus_examples[: args.max_corpus_examples]
    examples.extend(corpus_examples)
    examples.extend(build_mapping_examples(mapping_rows))
    examples = dedupe_examples(examples)

    train_rows, eval_rows = split_rows(examples, args.eval_ratio, args.seed)

    output_dir = Path(args.output_dir)
    write_jsonl(output_dir / "train.jsonl", train_rows)
    write_jsonl(output_dir / "eval.jsonl", eval_rows)
    print(f"Prepared {len(train_rows)} train and {len(eval_rows)} eval examples in {output_dir}.")


if __name__ == "__main__":
    main()
