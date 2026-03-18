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

## Refresh the datasets first

```powershell
.venv\Scripts\python training\scripts\prepare_dataset.py
.venv\Scripts\python training\scripts\prepare_fir_dataset.py
```

## Grounded legal pass

```powershell
.venv\Scripts\python training\scripts\train_qlora.py `
  --config training\configs\finetune_qlora_rtx3050_grounded_v2.yaml
```

This run uses a more balanced legal dataset, a grounded answer format, and explicit legacy-law bridge examples for IPC and CrPC style questions.

## Focused legal follow-up

After the grounded pass, run a focused follow-up on the user-facing legal QA tasks:

```powershell
.venv\Scripts\python training\scripts\train_qlora.py `
  --config training\configs\finetune_qlora_rtx3050_focus_v1.yaml `
  --adapter-path training\output\qwen2.5-1.5b-legal-grounded-v2\adapter
```

This second stage is useful when you want the model to focus more on plain-language answers, legacy-law translation, and practical next steps instead of generic section paraphrases.

## Benchmark against the backend

Always compare the adapter against the live retrieval-first backend before treating it as production-ready:

```powershell
.venv\Scripts\python training\scripts\compare_backend_vs_adapter.py `
  --adapter-path training\output\qwen2.5-1.5b-legal-grounded-v2-focus\adapter `
  --train-config training\configs\finetune_qlora_rtx3050_focus_v1.yaml `
  --output-prefix training\output\backend_vs_adapter_grounded_v2_focus `
  --offline
```

Each run writes `run_metadata.yaml` into the output folder so you can see exactly which checkpoint, dataset, and slice were used.

Use `--resume-from-checkpoint` only if a run crashes midway and you want to restart that same run from its latest checkpoint. Use `--adapter-path` when you want to continue learning from a previous adapter in a new output directory.

## FIR-specific model

Use the dedicated FIR dataset and config when you want a separate model for citizen applications, police FIR drafting, and lawyer review.

```powershell
.venv\Scripts\python training\scripts\train_qlora.py `
  --config training\configs\finetune_fir_qlora_rtx3050_v2.yaml
```

If you want a longer second-stage FIR tune on the same examples, continue from the saved adapter:

```powershell
.venv\Scripts\python training\scripts\train_qlora.py `
  --config training\configs\finetune_fir_qlora_rtx3050_v2.yaml `
  --adapter-path training\output\qwen2.5-1.5b-fir-studio-v2\adapter `
  --output-dir training\output\qwen2.5-1.5b-fir-studio-v2-round2 `
  --max-steps 12
```
