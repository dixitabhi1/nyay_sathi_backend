from __future__ import annotations

import argparse
from pathlib import Path

import torch
import yaml
from datasets import load_dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments
from trl import SFTTrainer


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def format_example(example: dict) -> str:
    return (
        "<s>[INST] You are NyayaSetu, a legal AI assistant for Indian law.\n"
        "Answer in plain language, stay grounded in the supplied legal context, and include practical next steps when useful.\n"
        f"Instruction: {example['instruction']}\n"
        f"Context: {example['input']} [/INST]\n"
        f"{example['output']}</s>"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune a legal LLM with QLoRA.")
    parser.add_argument("--config", default="training/configs/finetune_qlora.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    dataset = load_dataset(
        "json",
        data_files={
            "train": config["dataset"]["train_file"],
            "eval": config["dataset"]["eval_file"],
        },
    )
    tokenizer = AutoTokenizer.from_pretrained(config["model_name"], use_fast=True)
    tokenizer.pad_token = tokenizer.eos_token

    quantization_config = BitsAndBytesConfig(
        load_in_4bit=config["quantization"]["load_in_4bit"],
        bnb_4bit_use_double_quant=config["quantization"]["bnb_4bit_use_double_quant"],
        bnb_4bit_quant_type=config["quantization"]["bnb_4bit_quant_type"],
        bnb_4bit_compute_dtype=getattr(torch, config["quantization"]["bnb_4bit_compute_dtype"]),
    )
    model = AutoModelForCausalLM.from_pretrained(
        config["model_name"],
        quantization_config=quantization_config,
        device_map="auto",
    )
    peft_config = LoraConfig(
        r=config["lora"]["r"],
        lora_alpha=config["lora"]["alpha"],
        lora_dropout=config["lora"]["dropout"],
        bias="none",
        target_modules=config["lora"]["target_modules"],
        task_type="CAUSAL_LM",
    )
    training_args = TrainingArguments(
        output_dir=config["output_dir"],
        learning_rate=float(config["learning_rate"]),
        num_train_epochs=int(config["epochs"]),
        per_device_train_batch_size=int(config["per_device_train_batch_size"]),
        per_device_eval_batch_size=int(config["per_device_eval_batch_size"]),
        gradient_accumulation_steps=int(config["gradient_accumulation_steps"]),
        logging_steps=int(config["logging_steps"]),
        save_steps=int(config["save_steps"]),
        eval_steps=int(config["eval_steps"]),
        warmup_ratio=float(config.get("warmup_ratio", 0.03)),
        weight_decay=float(config.get("weight_decay", 0.0)),
        max_grad_norm=float(config.get("max_grad_norm", 1.0)),
        evaluation_strategy="steps",
        save_strategy="steps",
        bf16=True,
        gradient_checkpointing=bool(config.get("gradient_checkpointing", False)),
        optim="paged_adamw_8bit",
        report_to="none",
    )
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset["train"],
        eval_dataset=dataset["eval"],
        peft_config=peft_config,
        formatting_func=format_example,
        args=training_args,
        max_seq_length=int(config["sequence_length"]),
    )
    trainer.train()
    trainer.model.save_pretrained(Path(config["output_dir"]) / "adapter")
    tokenizer.save_pretrained(Path(config["output_dir"]) / "adapter")


if __name__ == "__main__":
    main()
