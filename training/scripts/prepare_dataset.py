from __future__ import annotations

import argparse
import csv
import json
import random
import re
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=True) for row in rows), encoding="utf-8")


def load_mappings(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [row for row in reader if any(row.values())]


def normalize_text(text: str, max_chars: int) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    return cleaned[:max_chars]


def build_instruction_examples(qa_rows: list[dict], corpus_rows: list[dict], mapping_rows: list[dict]) -> list[dict]:
    examples: list[dict] = []
    for row in qa_rows:
        instruction = normalize_text(row["question"], 300)
        context = normalize_text(row.get("context", ""), 2200)
        answer = normalize_text(row["answer"], 1200)
        examples.append(
            {
                "instruction": instruction,
                "input": context,
                "output": answer,
                "task": "legal_qa",
            }
        )
        examples.append(
            {
                "instruction": f"Explain this to an ordinary citizen in plain language: {instruction}",
                "input": context,
                "output": answer,
                "task": "citizen_plain_language_qa",
            }
        )
    for row in corpus_rows:
        source_text = normalize_text(row["text"], 2200)
        summary = normalize_text(row.get("summary") or row["text"][:500], 900)
        examples.append(
            {
                "instruction": f"Explain the legal significance of {row['citation']} in plain language.",
                "input": source_text,
                "output": summary,
                "task": f"{row.get('source_type', 'legal')}_explanation",
            }
        )
        examples.append(
            {
                "instruction": f"What is the practical takeaway from {row['citation']} for a citizen-facing legal assistant?",
                "input": source_text,
                "output": f"{summary} Cite {row['citation']} when grounding the answer.",
                "task": f"{row.get('source_type', 'legal')}_practical_takeaway",
            }
        )
    for row in mapping_rows:
        examples.append(
            {
                "instruction": f"Map {row['source_citation']} to its modern legal equivalent.",
                "input": normalize_text(row.get("notes", ""), 600),
                "output": f"{row['source_citation']} corresponds to {row['target_citation']} ({row.get('relationship', 'mapped')}).",
                "task": "section_mapping",
            }
        )
        examples.append(
            {
                "instruction": f"If a user cites {row['source_citation']}, which modern section should NyayaSetu check next?",
                "input": normalize_text(row.get("notes", ""), 600),
                "output": f"Check {row['target_citation']} and verify the factual overlap before applying the mapping.",
                "task": "section_mapping_follow_up",
            }
        )
    return examples


def split_rows(rows: list[dict], eval_ratio: float, seed: int) -> tuple[list[dict], list[dict]]:
    random.Random(seed).shuffle(rows)
    split_index = max(1, int(len(rows) * (1 - eval_ratio)))
    return rows[:split_index], rows[split_index:]


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare NyayaSetu instruction tuning datasets.")
    parser.add_argument("--qa-path", default="training/data/raw/legal_qa.jsonl")
    parser.add_argument("--corpus-path", default="data/corpus/official_legal_corpus.jsonl")
    parser.add_argument("--fallback-corpus-path", default="data/sample/legal_corpus/legal_corpus.jsonl")
    parser.add_argument("--mapping-csv", default="ingestion/configs/ipc_bns_mappings.csv")
    parser.add_argument("--output-dir", default="training/data/processed")
    parser.add_argument("--eval-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    qa_rows = load_jsonl(Path(args.qa_path))
    corpus_path = Path(args.corpus_path)
    if not corpus_path.exists():
        corpus_path = Path(args.fallback_corpus_path)
    corpus_rows = load_jsonl(corpus_path)
    mapping_rows = load_mappings(Path(args.mapping_csv))
    examples = build_instruction_examples(qa_rows, corpus_rows, mapping_rows)
    train_rows, eval_rows = split_rows(examples, args.eval_ratio, args.seed)

    output_dir = Path(args.output_dir)
    write_jsonl(output_dir / "train.jsonl", train_rows)
    write_jsonl(output_dir / "eval.jsonl", eval_rows)
    print(f"Prepared {len(train_rows)} train and {len(eval_rows)} eval examples in {output_dir}.")


if __name__ == "__main__":
    main()
