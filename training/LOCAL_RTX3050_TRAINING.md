# Local RTX 3050 Training

This path is tuned for a 6GB `NVIDIA GeForce RTX 3050 Laptop GPU` and uses short iterative QLoRA rounds instead of a single long 7B training job.

## Smoke test

```powershell
.venv\Scripts\python training\scripts\train_qlora.py `
  --config training\configs\finetune_qlora_rtx3050.yaml `
  --output-dir training\output\qwen2.5-1.5b-legal-rtx3050-smoke `
  --max-train-examples 32 `
  --max-eval-examples 8 `
  --max-steps 2
```

## Round 1

```powershell
.venv\Scripts\python training\scripts\train_qlora.py `
  --config training\configs\finetune_qlora_rtx3050.yaml `
  --output-dir training\output\qwen2.5-1.5b-legal-rtx3050
```

## Round 2

Point `--adapter-path` at the adapter saved from round 1 and move to the next training slice.

```powershell
.venv\Scripts\python training\scripts\train_qlora.py `
  --config training\configs\finetune_qlora_rtx3050.yaml `
  --output-dir training\output\qwen2.5-1.5b-legal-rtx3050 `
  --adapter-path training\output\qwen2.5-1.5b-legal-rtx3050\adapter `
  --train-offset 160 `
  --eval-offset 32
```

## Later rounds

Keep the same output directory, resume from the newest checkpoint, and move the dataset window forward.

Suggested dataset windows:

- Round 1: `--train-offset 0 --eval-offset 0`
- Round 2: `--train-offset 160 --eval-offset 32`
- Round 3: `--train-offset 320 --eval-offset 64`
- Round 4: `--train-offset 480 --eval-offset 96`

Each run writes `run_metadata.yaml` into the output folder so you can see exactly which slice and checkpoint were used.

Use `--resume-from-checkpoint` only if a round crashes midway and you want to restart that same round from its latest checkpoint.
