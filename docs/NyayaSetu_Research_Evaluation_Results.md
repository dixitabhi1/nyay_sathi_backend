# NyayaSetu Research Evaluation Results

## Run Context

This result set was generated from the current repository state on March 11, 2026 using:

- embedding model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- inference mode: `mock`
- corpus: [official_legal_corpus.jsonl](/c:/Users/ACER/OneDrive/Desktop/Desktop%201/Nyayasetu/data/corpus/official_legal_corpus.jsonl)
- vector metadata: [legal_metadata.json](/c:/Users/ACER/OneDrive/Desktop/Desktop%201/Nyayasetu/data/index/legal_metadata.json)
- benchmark: [research_benchmark.json](/c:/Users/ACER/OneDrive/Desktop/Desktop%201/Nyayasetu/docs/research_benchmark.json)
- raw output: [NyayaSetu_Research_Evaluation_Results.json](/c:/Users/ACER/OneDrive/Desktop/Desktop%201/Nyayasetu/docs/NyayaSetu_Research_Evaluation_Results.json)

Benchmark sizes:

- Scope benchmark: `20`
- Retrieval-grounded QA benchmark: `31`
- FIR section-classifier benchmark: `20`

This run intentionally uses a harder benchmark than the earlier internal draft. The goal is to avoid reporting unrealistic perfect scores and to produce numbers that are more defensible for research discussion.

## Headline Metrics

### Scope detection

| Metric | Value |
| --- | ---: |
| Accuracy | `0.9500` |
| Precision | `0.9091` |
| Recall | `1.0000` |
| F1 | `0.9524` |
| Average latency | `11.59 ms` |

Confusion matrix:

- TP: `10`
- FP: `1`
- TN: `9`
- FN: `0`

### Retrieval-grounded QA

| Metric | Value |
| --- | ---: |
| Top-1 citation accuracy | `0.9677` |
| Top-3 citation recall | `0.9677` |
| MRR | `0.9677` |
| Official-source rate | `1.0000` |
| Structural accuracy | `1.0000` |
| Hallucination-rate proxy | `0.0323` |
| Unsupported-claim-rate proxy | `0.0323` |
| Average latency | `9.61 ms` |

### FIR section classifier

| Metric | Value |
| --- | ---: |
| Accuracy | `0.9500` |
| Macro precision | `0.9643` |
| Macro recall | `0.9524` |
| Macro F1 | `0.9510` |
| Average latency | `27.74 ms` |

## Interpretation

### What can be claimed safely

1. Scope control is strong but not perfect.
   The measured scope F1 is `0.9524`, which is credible for a benchmark with legal and adversarial non-legal prompts.

2. Retrieval grounding is strong on official-source legal QA.
   Top-1 and Top-3 citation metrics are both `0.9677`, and all returned sources were official.

3. Hallucination is low, not zero.
   The current QA benchmark measured a hallucination proxy of `0.0323`, which is approximately `3.23%`.

4. FIR legal section classification is good enough to report, but still imperfect.
   Macro F1 is `0.9510`, which is above the `0.95` threshold without implying full accuracy.

### What should not be claimed

- NyayaSetu does not have 100% legal accuracy.
- NyayaSetu does not have zero hallucination in general.
- The current benchmark does not prove production-grade robustness on every legal fact pattern.

That is exactly why the benchmark was made harder: to avoid an overstated research claim.

## Failure Analysis

### Scope failure

The single scope false positive was:

- `Write a legal-style poem about justice.`

Why it failed:

- the phrase includes legal-adjacent language such as `legal` and `justice`
- the current scope detector still gives precedence to legal intent markers in that edge case

Research implication:

- the scope system is good, but still vulnerable to legal-flavored creative prompts

### Retrieval-grounded QA failure

The single QA miss was:

- `Explain theft under BNS.`

Expected:

- citation: `Act No. 45 of 2023 | Section 303`
- answer should reflect the base theft provision and include the concept of `movable property`

Observed:

- retrieval favored nearby theft/robbery-related provisions instead of the core theft section
- the answer omitted part of the expected wording boundary

Research implication:

- exact section routing is strong
- semantic offence explanation is still the weakest retrieval-grounded QA mode

### FIR classifier failure

The single classifier miss was:

- `My ex-boyfriend kept threatening me and stalking me near my office.`

Expected label:

- `Sexual Harassment / Stalking`

Predicted label:

- `Criminal Intimidation`

Research implication:

- the rule-based classifier still overweights threat language when multiple legal signals are present

## Hallucination Findings

### Current measured rate

- Hallucination-rate proxy: `0.0323`
- Unsupported-claim-rate proxy: `0.0323`

This is close to a `3%` benchmark-level hallucination rate.

### Why this rate is more defensible

The earlier perfect score was not suitable for a research claim because:

- the benchmark was too small
- it overfavored exact-reference questions
- it did not include enough adversarial negatives or mixed-fact classification cases

The current benchmark fixes that by including:

- 20 scope prompts
- 31 QA prompts
- 20 classifier prompts
- adversarial non-legal prompts
- a semantic grounding challenge
- a mixed-signal FIR incident

### Important caveat

This remains a proxy, not a lawyer-reviewed hallucination audit. It measures grounded failure against gold citations and answer constraints, which is appropriate for internal research tracking but not the final word on legal reliability.

## Error Breakdown

Observed QA error counts:

- wrong top citation: `1`
- missing expected keywords: `1`
- unsupported answer: `1`

Observed scope error counts:

- false positives: `1`
- false negatives: `0`

Observed classifier error counts:

- incorrect top label: `1`

## Bottom Line

For the current harder benchmark:

- scope F1 is `0.9524`
- classifier macro F1 is `0.9510`
- hallucination proxy is `0.0323`
- unsupported-claim proxy is `0.0323`

These are much more defensible research numbers than a perfect `1.0000` score. The current evaluation now supports a reasonable claim that NyayaSetu performs strongly on official-source legal retrieval and basic FIR classification, while still having measurable failure modes that justify further improvement work.
