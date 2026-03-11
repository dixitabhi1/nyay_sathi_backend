# NyayaSetu Research Evaluation Approach

## Purpose

This document describes a research-oriented evaluation approach for NyayaSetu. The goal is not to expose these metrics inside the application UI. The goal is to trace system quality internally and measure retrieval quality, scope control, citation grounding, classifier quality, and hallucination risk proxies.

The current evaluation run is benchmarked against the repository state as of March 11, 2026, using:

- official legal corpus in [official_legal_corpus.jsonl](/c:/Users/ACER/OneDrive/Desktop/Desktop%201/Nyayasetu/data/corpus/official_legal_corpus.jsonl)
- FAISS metadata in [legal_metadata.json](/c:/Users/ACER/OneDrive/Desktop/Desktop%201/Nyayasetu/data/index/legal_metadata.json)
- benchmark definitions in [research_benchmark.json](/c:/Users/ACER/OneDrive/Desktop/Desktop%201/Nyayasetu/docs/research_benchmark.json)
- evaluation runner in [run_research_eval.py](/c:/Users/ACER/OneDrive/Desktop/Desktop%201/Nyayasetu/docs/run_research_eval.py)

## Evaluation Scope

The current benchmark covers three internal subsystems:

1. Scope detection
2. Retrieval-grounded legal QA
3. FIR legal section classification

It does not yet measure:

- OCR extraction quality
- voice transcription accuracy
- contract clause extraction F1
- evidence entity extraction F1
- long-form draft quality judged by lawyers

Those should be added later with dedicated gold datasets.

## Benchmark Design

### 1. Scope benchmark

The scope benchmark tests whether NyayaSetu correctly rejects irrelevant prompts while keeping legal prompts in scope.

Current benchmark size:

- 20 prompts total
- 10 legal prompts
- 10 non-legal prompts

Examples of legal prompts:

- `What does Section 87 of BNS cover?`
- `How many sections are there in BNSS?`
- `How do I draft an FIR for phone theft?`

Examples of non-legal prompts:

- `what is my name?`
- `what is the weather in Lucknow?`
- `write a poem about justice`

### 2. Retrieval-grounded QA benchmark

The QA benchmark evaluates exact statute retrieval and grounded answer generation for questions where there is a clear official answer.

Current benchmark size:

- 31 questions total
- 3 statute-structure questions
- 27 exact-section questions
- 1 semantic grounding challenge

Examples:

- `How many sections are there in BNS?`
- `What does Section 303 of BNS cover?`
- `What is BNSS section 79 about?`
- `What does BSA section 145 say?`

Each QA benchmark row includes:

- expected source citation
- expected keywords in the answer
- expected count for structural questions where applicable

### 3. FIR section-classifier benchmark

The classifier benchmark evaluates whether the FIR rule-based section predictor maps a complaint to the correct legal category.

Current benchmark size:

- 20 incident descriptions

Labels used in the benchmark:

- `Theft`
- `Criminal Intimidation`
- `Cheating`
- `Voluntarily Causing Hurt / Assault`
- `Sexual Harassment / Stalking`
- `Criminal Trespass`
- `Mischief / Property Damage`

## Metrics

### Scope detection metrics

Scope is evaluated as binary classification.

Reported metrics:

- Accuracy
- Precision
- Recall
- F1 score
- Confusion matrix: TP, FP, TN, FN
- Average latency

These tell us whether the system rejects non-legal prompts without suppressing legitimate legal prompts.

### Retrieval-grounded QA metrics

For each query, NyayaSetu returns sources and an answer. The benchmark scores:

- Top-1 citation accuracy
- Top-3 citation recall
- MRR
- Official-source rate
- Structural accuracy
- Hallucination-rate proxy
- Unsupported-claim-rate proxy
- Average latency

Definitions:

- `Top-1 citation accuracy`: the first returned citation is the gold citation
- `Top-3 citation recall`: the gold citation appears within the first 3 returned citations
- `MRR`: reciprocal rank of the gold citation
- `Official-source rate`: all returned sources are official authorities
- `Structural accuracy`: statute-count questions return the correct count and correct official source

### FIR section-classifier metrics

The classifier is scored as single-label classification using the top suggestion.

Reported metrics:

- Accuracy
- Macro precision
- Macro recall
- Macro F1
- Average latency

Macro F1 is important because the benchmark covers multiple crime categories and should not be dominated by only one label.

## Hallucination Measurement Strategy

NyayaSetu is currently a retrieval-first system. For research purposes, hallucination is not measured as a vague subjective impression. It is measured with a proxy grounded in evidence support.

Current hallucination proxy:

- structural question is hallucinated if the answer gives the wrong statute count or wrong official source
- exact-section question is hallucinated if the top citation is wrong or if required answer keywords are missing
- unsupported-answer flag is raised if the gold citation is missing from the returned top-3 sources

This proxy is intentionally conservative. It does not claim to replace human legal review.

### Why this works

For the current benchmark, each question has:

- a known official source
- a known target section or count
- required answer keywords

This makes it possible to test whether the answer stays inside the retrieved legal evidence boundary.

### What this does not catch

The current proxy will not fully capture:

- subtle overstatement of certainty
- nuanced legal misinterpretation despite correct citation
- misleading paraphrases that still contain the expected keyword
- policy or procedure advice that is incomplete rather than false

Those require lawyer-reviewed annotation.

## Traceability and Error Analysis

Each benchmark row is stored in the result JSON with:

- question or incident description
- expected label or citation
- predicted citations or predicted class
- answer text
- latency
- per-row correctness flags

This enables:

- confusion-matrix review
- false-positive and false-negative audits
- retrieval-rank inspection
- manual legal review of suspect outputs

The raw output file is:

- [NyayaSetu_Research_Evaluation_Results.json](/c:/Users/ACER/OneDrive/Desktop/Desktop%201/Nyayasetu/docs/NyayaSetu_Research_Evaluation_Results.json)

## Recommended Hallucination-Reduction Approach

For NyayaSetu, reducing hallucination should be done in layers.

### 1. Exact-reference routing

If the query contains:

- statute name
- section number
- optional subsection

then the system should route directly to exact statute lookup before semantic search. This is already partially implemented and is critical for section-specific legal queries.

### 2. Evidence-bounded generation

The answer should be generated only from:

- user query
- retrieved legal sources

If the supporting citation is not present, the system should abstain or narrow the answer.

### 3. Threshold-based abstention

If retrieval confidence is weak, the system should respond with:

- insufficient grounding
- request for clarification
- limited answer with warning

### 4. Official-source-only grounding

The strongest legal answers should prioritize:

- India Code
- legislative documents
- other official government material

This reduces citation drift and source contamination.

### 5. Post-generation verifier

A second-pass verifier should check:

- whether every legal claim is supported by a returned citation
- whether section numbers are real
- whether the act name matches the cited provision

### 6. Out-of-scope tightening

The current scope detector can still produce false positives for prompts that contain words semantically close to the legal domain, such as:

- `justice`
- prompts that contain the word `legal` but are still creative-writing requests

This can be reduced by:

- stronger negative anchors
- explicit reject rules for weather, poetry, sports, trivia
- a second-stage scope verifier

## Recommended Next Research Extensions

The next evaluation layers should add:

1. FIR entity extraction benchmark with exact-match and relaxed-match F1
2. OCR benchmark with character error rate and field extraction accuracy
3. Whisper benchmark with word error rate for voice FIR
4. Contract analysis benchmark with clause-level precision and recall
5. Human-annotated legal hallucination severity scoring
6. Comparative experiments across embedding models and retrieval thresholds

## Reproducibility

To rerun the benchmark:

```powershell
.\.venv\Scripts\python.exe docs\build_research_benchmark.py
.\.venv\Scripts\python.exe docs\run_research_eval.py
```

This regenerates:

- [NyayaSetu_Research_Evaluation_Results.json](/c:/Users/ACER/OneDrive/Desktop/Desktop%201/Nyayasetu/docs/NyayaSetu_Research_Evaluation_Results.json)

The two most important benchmark assets are:

- [research_benchmark.json](/c:/Users/ACER/OneDrive/Desktop/Desktop%201/Nyayasetu/docs/research_benchmark.json)
- [run_research_eval.py](/c:/Users/ACER/OneDrive/Desktop/Desktop%201/Nyayasetu/docs/run_research_eval.py)
