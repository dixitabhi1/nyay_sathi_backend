from __future__ import annotations

import argparse
import json

import evaluate
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a NyayaSetu legal model on the eval split.")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--eval-file", default="training/data/processed/eval.jsonl")
    parser.add_argument("--max-samples", type=int, default=20)
    args = parser.parse_args()

    dataset = load_dataset("json", data_files={"eval": args.eval_file})["eval"].select(range(args.max_samples))
    tokenizer = AutoTokenizer.from_pretrained(args.model_path)
    model = AutoModelForCausalLM.from_pretrained(args.model_path, device_map="auto")
    generator = pipeline("text-generation", model=model, tokenizer=tokenizer)
    rouge = evaluate.load("rouge")

    predictions: list[str] = []
    references: list[str] = []
    for row in dataset:
        prompt = (
            "You are NyayaSetu, a legal AI assistant for Indian law. "
            "Answer in plain language and stay grounded in the provided context.\n"
            f"Instruction: {row['instruction']}\nContext: {row['input']}\nAnswer:"
        )
        output = generator(prompt, max_new_tokens=256, do_sample=False)[0]["generated_text"]
        raw_prediction = output.split("Answer:", 1)[-1].strip()
        try:
            parsed = json.loads(raw_prediction)
            predictions.append(parsed.get("answer", raw_prediction).strip())
        except json.JSONDecodeError:
            predictions.append(raw_prediction)
        references.append(row["output"])

    scores = rouge.compute(predictions=predictions, references=references)
    print(scores)


if __name__ == "__main__":
    main()
