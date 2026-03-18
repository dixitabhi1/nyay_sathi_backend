from __future__ import annotations

import argparse
from pathlib import Path

import torch
import yaml
from datasets import load_dataset
from peft import LoraConfig, PeftModel, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer


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


def slice_split(dataset, limit: int | None, offset: int = 0, shuffle_seed: int | None = None):
    if offset < 0:
        raise ValueError("Dataset offset must be 0 or greater.")
    if shuffle_seed is not None:
        dataset = dataset.shuffle(seed=shuffle_seed)
    if offset >= len(dataset):
        return dataset.select([])
    end = len(dataset) if limit is None or limit <= 0 else min(offset + limit, len(dataset))
    return dataset.select(list(range(offset, end)))


def write_run_metadata(
    output_dir: Path,
    config: dict,
    args: argparse.Namespace,
    train_examples: int,
    eval_examples: int,
    train_offset: int,
    eval_offset: int,
    shuffle_seed: int | None,
    resume_from_checkpoint: str | None,
    adapter_path: str | None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "model_name": config["model_name"],
        "config_path": args.config,
        "output_dir": str(output_dir),
        "resume_from_checkpoint": resume_from_checkpoint,
        "adapter_path": adapter_path,
        "train_examples": train_examples,
        "eval_examples": eval_examples,
        "train_offset": train_offset,
        "eval_offset": eval_offset,
        "shuffle_seed": shuffle_seed,
        "max_steps": args.max_steps if args.max_steps is not None else config.get("max_steps"),
        "sequence_length": config["sequence_length"],
        "learning_rate": config["learning_rate"],
        "per_device_train_batch_size": config["per_device_train_batch_size"],
        "gradient_accumulation_steps": config["gradient_accumulation_steps"],
        "mixed_precision": config.get("mixed_precision", "auto"),
        "torch_version": str(torch.__version__),
        "cuda_version": str(torch.version.cuda),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }
    with open(output_dir / "run_metadata.yaml", "w", encoding="utf-8") as handle:
        yaml.safe_dump(metadata, handle, sort_keys=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune a legal LLM with QLoRA.")
    parser.add_argument("--config", default="training/configs/finetune_qlora.yaml")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--resume-from-checkpoint", default=None)
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--max-train-examples", type=int, default=None)
    parser.add_argument("--max-eval-examples", type=int, default=None)
    parser.add_argument("--train-offset", type=int, default=None)
    parser.add_argument("--eval-offset", type=int, default=None)
    parser.add_argument("--shuffle-seed", type=int, default=None)
    parser.add_argument("--adapter-path", default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available. Install a CUDA-enabled PyTorch build before launching local QLoRA training.")
    dataset = load_dataset(
        "json",
        data_files={
            "train": config["dataset"]["train_file"],
            "eval": config["dataset"]["eval_file"],
        },
    )
    train_limit = args.max_train_examples if args.max_train_examples is not None else config.get("max_train_examples")
    eval_limit = args.max_eval_examples if args.max_eval_examples is not None else config.get("max_eval_examples")
    train_offset = args.train_offset if args.train_offset is not None else int(config.get("train_offset", 0))
    eval_offset = args.eval_offset if args.eval_offset is not None else int(config.get("eval_offset", 0))
    shuffle_seed = args.shuffle_seed if args.shuffle_seed is not None else config.get("shuffle_seed")

    dataset["train"] = slice_split(dataset["train"], train_limit, offset=train_offset, shuffle_seed=shuffle_seed)
    dataset["eval"] = slice_split(dataset["eval"], eval_limit, offset=eval_offset, shuffle_seed=shuffle_seed)
    if len(dataset["train"]) == 0:
        raise RuntimeError("The selected training slice is empty. Adjust max-train-examples or train-offset.")

    tokenizer = AutoTokenizer.from_pretrained(config["model_name"], use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    mixed_precision = str(config.get("mixed_precision", "auto")).lower()
    use_bf16 = mixed_precision == "bf16" or (
        mixed_precision == "auto" and torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    )
    use_fp16 = mixed_precision == "fp16" or (mixed_precision == "auto" and not use_bf16)

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
        low_cpu_mem_usage=True,
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(
        model,
        use_gradient_checkpointing=bool(config.get("gradient_checkpointing", False)),
    )
    adapter_path = args.adapter_path or config.get("adapter_path")
    peft_config = None
    if adapter_path:
        model = PeftModel.from_pretrained(model, adapter_path, is_trainable=True)
    else:
        peft_config = LoraConfig(
            r=config["lora"]["r"],
            lora_alpha=config["lora"]["alpha"],
            lora_dropout=config["lora"]["dropout"],
            bias="none",
            target_modules=config["lora"]["target_modules"],
            task_type="CAUSAL_LM",
        )
    has_eval = len(dataset["eval"]) > 0
    load_best_model_at_end = bool(config.get("load_best_model_at_end", False) and has_eval)
    resume_from_checkpoint = args.resume_from_checkpoint or config.get("resume_from_checkpoint")
    output_dir = Path(args.output_dir or config["output_dir"])
    write_run_metadata(
        output_dir=output_dir,
        config=config,
        args=args,
        train_examples=len(dataset["train"]),
        eval_examples=len(dataset["eval"]),
        train_offset=train_offset,
        eval_offset=eval_offset,
        shuffle_seed=shuffle_seed,
        resume_from_checkpoint=resume_from_checkpoint,
        adapter_path=adapter_path,
    )
    training_args = SFTConfig(
        output_dir=str(output_dir),
        learning_rate=float(config["learning_rate"]),
        num_train_epochs=int(config["epochs"]),
        per_device_train_batch_size=int(config["per_device_train_batch_size"]),
        per_device_eval_batch_size=int(config["per_device_eval_batch_size"]),
        gradient_accumulation_steps=int(config["gradient_accumulation_steps"]),
        logging_steps=int(config["logging_steps"]),
        save_steps=int(config["save_steps"]),
        eval_steps=int(config["eval_steps"]),
        max_steps=int(args.max_steps if args.max_steps is not None else config.get("max_steps", -1)),
        save_total_limit=int(config.get("save_total_limit", 2)),
        warmup_ratio=float(config.get("warmup_ratio", 0.03)),
        weight_decay=float(config.get("weight_decay", 0.0)),
        max_grad_norm=float(config.get("max_grad_norm", 1.0)),
        lr_scheduler_type=str(config.get("lr_scheduler_type", "cosine")),
        eval_strategy="steps" if has_eval else "no",
        save_strategy="steps",
        bf16=use_bf16,
        fp16=use_fp16,
        gradient_checkpointing=bool(config.get("gradient_checkpointing", False)),
        gradient_checkpointing_kwargs={"use_reentrant": bool(config.get("gradient_checkpointing_use_reentrant", False))},
        optim="paged_adamw_8bit",
        dataloader_pin_memory=False,
        dataloader_num_workers=0,
        remove_unused_columns=False,
        save_safetensors=True,
        load_best_model_at_end=load_best_model_at_end,
        metric_for_best_model="eval_loss" if load_best_model_at_end else None,
        greater_is_better=False if load_best_model_at_end else None,
        logging_first_step=True,
        report_to="none",
        max_seq_length=int(config["sequence_length"]),
    )
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset["train"],
        eval_dataset=dataset["eval"] if has_eval else None,
        processing_class=tokenizer,
        peft_config=peft_config,
        formatting_func=format_example,
        args=training_args,
    )
    trainer.train(resume_from_checkpoint=resume_from_checkpoint)
    trainer.model.save_pretrained(output_dir / "adapter")
    tokenizer.save_pretrained(output_dir / "adapter")


if __name__ == "__main__":
    main()
