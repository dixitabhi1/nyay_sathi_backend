from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=True) for row in rows), encoding="utf-8")


def normalize_text(text: str) -> str:
    return " ".join((text or "").replace("\r", " ").split()).strip()


def build_examples(rows: list[dict]) -> list[dict]:
    examples: list[dict] = []
    for row in rows:
        mode = normalize_text(row.get("mode", "citizen_application"))
        language = normalize_text(row.get("language", "en"))
        facts = normalize_text(row.get("facts", ""))
        comparative_sections = normalize_text(row.get("comparative_sections", ""))
        output = row.get("output", "").strip()
        if not facts or not output:
            continue
        context = (
            f"Complaint facts: {facts}\n\n"
            f"Comparative sections to stay grounded in: {comparative_sections}\n\n"
            "Return a clean, human-readable FIR workflow document and do not invent facts."
        )
        prompt_variants = [
            (f"Generate a {mode} document for NyayaSetu in {language}.", f"fir_{mode}"),
            (
                f"Rewrite the same {mode} output in a polished, submission-ready way for NyayaSetu.",
                f"fir_{mode}_rewrite",
            ),
            (
                f"An OCR pipeline extracted this complaint. Draft a {mode} document for NyayaSetu in {language}.",
                f"fir_{mode}_ocr",
            ),
            (
                f"A voice transcript has been converted to text. Draft a {mode} document for NyayaSetu in {language}.",
                f"fir_{mode}_voice",
            ),
            (
                f"Prepare a {mode} document with clear headings, comparative sections, and verification notes for NyayaSetu in {language}.",
                f"fir_{mode}_structured",
            ),
        ]
        for instruction, task in prompt_variants:
            examples.append(
                {
                    "instruction": instruction,
                    "input": context,
                    "output": output,
                    "task": task,
                }
            )
    return examples


def split_rows(rows: list[dict], eval_ratio: float, seed: int) -> tuple[list[dict], list[dict]]:
    random.Random(seed).shuffle(rows)
    split_index = max(1, int(len(rows) * (1 - eval_ratio)))
    return rows[:split_index], rows[split_index:]


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare NyayaSetu FIR generation datasets.")
    parser.add_argument("--raw-path", default="training/data/raw/fir_generation_examples.jsonl")
    parser.add_argument("--output-dir", default="training/data/processed/fir")
    parser.add_argument("--eval-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    raw_rows = load_jsonl(Path(args.raw_path))
    examples = build_examples(raw_rows)
    train_rows, eval_rows = split_rows(examples, args.eval_ratio, args.seed)

    output_dir = Path(args.output_dir)
    write_jsonl(output_dir / "train.jsonl", train_rows)
    write_jsonl(output_dir / "eval.jsonl", eval_rows)
    print(f"Prepared {len(train_rows)} FIR train and {len(eval_rows)} FIR eval examples in {output_dir}.")


if __name__ == "__main__":
    main()
