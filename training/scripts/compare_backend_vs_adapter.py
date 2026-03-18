from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

import torch
import yaml
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_prompts(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
        raise ValueError("Prompt file must be a JSON array of strings.")
    return payload


def prepare_eval_database(eval_db_path: Path) -> None:
    if eval_db_path.exists():
        return
    source_db = REPO_ROOT / "storage" / "db" / "nyayasetu.sqlite3"
    eval_db_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_db, eval_db_path)


def format_sources_for_adapter(sources: list) -> str:
    if not sources:
        return "[No grounded legal sources were retrieved by the backend.]"
    blocks = []
    for source in sources[:4]:
        blocks.append(
            "\n".join(
                [
                    f"Title: {source.title}",
                    f"Citation: {source.citation}",
                    f"Excerpt: {source.excerpt}",
                ]
            )
        )
    return "\n\n".join(blocks)


def build_adapter_prompt(question: str, source_context: str) -> str:
    return (
        "<s>[INST] You are NyayaSetu, a legal AI assistant for Indian law.\n"
        "Answer in plain language, stay grounded in the supplied legal context, and include practical next steps when useful.\n"
        f"Instruction: {question}\n"
        f"Context: {source_context} [/INST]\n"
    )


def generate_adapter_answer(model, tokenizer, question: str, source_context: str, max_new_tokens: int) -> str:
    prompt = build_adapter_prompt(question, source_context)
    inputs = tokenizer(prompt, return_tensors="pt")
    model_device = getattr(model, "device", torch.device("cuda" if torch.cuda.is_available() else "cpu"))
    inputs = {key: value.to(model_device) for key, value in inputs.items()}
    with torch.inference_mode():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    generated_ids = output_ids[0][inputs["input_ids"].shape[1] :]
    answer = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
    return answer or "[No answer generated.]"


def extract_answer_features(answer: str, citations: list[str]) -> dict:
    normalized = answer.lower()
    return {
        "characters": len(answer),
        "bullet_points": len(re.findall(r"(?m)^- ", answer)),
        "mentions_next_steps": "next step" in normalized or "practical next steps" in normalized,
        "citation_mentions": sum(1 for citation in citations if citation and citation in answer),
    }


def render_markdown(results: list[dict]) -> str:
    sections = ["# Backend vs Adapter Evaluation", ""]
    for index, row in enumerate(results, start=1):
        sections.extend(
            [
                f"## Prompt {index}",
                "",
                f"**Question**: {row['question']}",
                "",
                f"**Source Citations**: {', '.join(row['source_citations']) or 'None'}",
                "",
                "**Backend Answer**",
                "",
                row["backend_answer"],
                "",
                f"Backend features: {json.dumps(row['backend_features'], ensure_ascii=True)}",
                "",
                "**Adapter Answer**",
                "",
                row["adapter_answer"],
                "",
                f"Adapter features: {json.dumps(row['adapter_features'], ensure_ascii=True)}",
                "",
                f"**Observation**: {row['observation']}",
                "",
            ]
        )
    return "\n".join(sections).strip() + "\n"


def compare_answers(backend_answer: str, adapter_answer: str, citations: list[str]) -> str:
    backend_features = extract_answer_features(backend_answer, citations)
    adapter_features = extract_answer_features(adapter_answer, citations)

    notes: list[str] = []
    if adapter_features["citation_mentions"] > backend_features["citation_mentions"]:
        notes.append("adapter cites more of the retrieved authorities directly")
    elif adapter_features["citation_mentions"] < backend_features["citation_mentions"]:
        notes.append("backend keeps the citations more explicit")

    if adapter_features["mentions_next_steps"] and not backend_features["mentions_next_steps"]:
        notes.append("adapter is more action-oriented")
    elif backend_features["mentions_next_steps"] and not adapter_features["mentions_next_steps"]:
        notes.append("backend gives clearer next steps")

    if adapter_features["characters"] < backend_features["characters"]:
        notes.append("adapter is more concise")
    elif adapter_features["characters"] > backend_features["characters"]:
        notes.append("backend is more concise")

    if not notes:
        return "Both answers are structurally similar on this prompt."
    return "; ".join(notes).capitalize() + "."


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare current backend answers against a fine-tuned adapter.")
    parser.add_argument(
        "--adapter-path",
        default="training/output/qwen2.5-1.5b-legal-rtx3050-round3/adapter",
    )
    parser.add_argument(
        "--train-config",
        default="training/configs/finetune_qlora_rtx3050.yaml",
    )
    parser.add_argument(
        "--prompts-file",
        default="training/eval/benchmark_prompts.json",
    )
    parser.add_argument(
        "--output-prefix",
        default="training/output/backend_vs_adapter_round3",
    )
    parser.add_argument(
        "--database-url",
        default="sqlite+pysqlite:///training/output/nyayasetu_eval.sqlite3",
    )
    parser.add_argument("--max-new-tokens", type=int, default=320)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    if args.offline:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"

    eval_db_path = REPO_ROOT / "training" / "output" / "nyayasetu_eval.sqlite3"
    prepare_eval_database(eval_db_path)

    os.environ["DATABASE_URL"] = args.database_url
    sys.path.insert(0, str(BACKEND_ROOT))

    from app.core.dependencies import get_legal_engine
    from app.schemas.chat import ChatRequest

    train_config = load_yaml(REPO_ROOT / args.train_config)
    prompts = load_prompts(REPO_ROOT / args.prompts_file)

    tokenizer = AutoTokenizer.from_pretrained(train_config["model_name"], use_fast=True, local_files_only=args.offline)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quantization_config = BitsAndBytesConfig(
        load_in_4bit=train_config["quantization"]["load_in_4bit"],
        bnb_4bit_use_double_quant=train_config["quantization"]["bnb_4bit_use_double_quant"],
        bnb_4bit_quant_type=train_config["quantization"]["bnb_4bit_quant_type"],
        bnb_4bit_compute_dtype=getattr(torch, train_config["quantization"]["bnb_4bit_compute_dtype"]),
    )
    model = AutoModelForCausalLM.from_pretrained(
        train_config["model_name"],
        quantization_config=quantization_config,
        device_map="auto",
        low_cpu_mem_usage=True,
        local_files_only=args.offline,
    )
    model = PeftModel.from_pretrained(model, REPO_ROOT / args.adapter_path, is_trainable=False)
    model.eval()

    engine = get_legal_engine()
    results: list[dict] = []
    for question in prompts:
        backend_response = engine.answer_question(ChatRequest(question=question))
        source_context = format_sources_for_adapter(backend_response.sources)
        adapter_answer = generate_adapter_answer(
            model=model,
            tokenizer=tokenizer,
            question=question,
            source_context=source_context,
            max_new_tokens=args.max_new_tokens,
        )
        source_citations = [source.citation for source in backend_response.sources]
        backend_features = extract_answer_features(backend_response.answer, source_citations)
        adapter_features = extract_answer_features(adapter_answer, source_citations)
        results.append(
            {
                "question": question,
                "in_scope": backend_response.in_scope,
                "source_citations": source_citations,
                "backend_answer": backend_response.answer,
                "backend_reasoning": backend_response.reasoning,
                "backend_features": backend_features,
                "adapter_answer": adapter_answer,
                "adapter_features": adapter_features,
                "observation": compare_answers(backend_response.answer, adapter_answer, source_citations),
            }
        )

    output_prefix = REPO_ROOT / args.output_prefix
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path = output_prefix.with_suffix(".json")
    md_path = output_prefix.with_suffix(".md")
    json_path.write_text(json.dumps(results, ensure_ascii=True, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(results), encoding="utf-8")

    print(f"Wrote JSON report to {json_path}")
    print(f"Wrote Markdown report to {md_path}")


if __name__ == "__main__":
    main()
