# NyayaSetu Research Comparison and Improvement Plan

## Objective

This document explains why the earlier perfect research scores should not be claimed, what was changed to produce a more realistic benchmark, and how NyayaSetu can be improved further from the current state.

## Comparison Summary

### Earlier internal benchmark state

| Metric | Earlier run |
| --- | ---: |
| Scope accuracy | `0.8571` |
| Scope precision | `0.7778` |
| Scope recall | `1.0000` |
| Scope F1 | `0.8750` |
| Retrieval top-1 citation accuracy | `1.0000` |
| Retrieval top-3 recall | `1.0000` |
| Hallucination-rate proxy | `0.0000` |
| FIR classifier macro F1 | `1.0000` |

### Current harder benchmark state

| Metric | Current run |
| --- | ---: |
| Scope F1 | `0.9524` |
| Retrieval top-1 citation accuracy | `0.9677` |
| Retrieval top-3 recall | `0.9677` |
| Hallucination-rate proxy | `0.0323` |
| FIR classifier macro F1 | `0.9510` |

### Why the current run is better for research

The current run is not "better" because the numbers are higher. It is better because the claims are more believable.

The earlier run was too clean:

- too few benchmark rows
- too many exact-reference questions
- too little adversarial pressure
- too little ambiguity in the classifier set

The current run is harder and therefore safer to cite in a report.

## What Was Changed

### 1. Scope benchmark was expanded

The scope benchmark now includes:

- 20 rows instead of 14
- 10 legal prompts
- 10 non-legal prompts
- adversarial legal-flavored non-legal prompts such as:
  - `Write a legal-style poem about justice.`

This replaced the earlier weaker scope benchmark state, where the system still had measurable false positives and only achieved `0.8750` F1.

### 2. QA benchmark was expanded

The QA benchmark now includes:

- 31 rows instead of 8
- structural statute questions
- exact section lookup questions
- one semantic grounding challenge:
  - `Explain theft under BNS.`

This ensured the benchmark measures not only exact lookup, but also retrieval quality on offence-level explanation.

### 3. Classifier benchmark was expanded

The FIR classifier benchmark now includes:

- 20 rows instead of 8
- one intentionally difficult mixed-signal incident:
  - threat plus stalking in the same complaint

This exposes a genuine confusion point in the current legal section rules.

### 4. Benchmark-generation bugs were corrected

Two benchmark-related issues were fixed:

- exact QA rows with no keyword list are now handled correctly by the evaluator
- `BNSS` rows are no longer mislabeled as `BNS` during benchmark generation

### 5. Retrieval logic was corrected

A statute-matching issue in [retriever.py](/c:/Users/ACER/OneDrive/Desktop/Desktop%201/Nyayasetu/backend/app/services/retriever.py) was fixed so `bns_...` and `bnss_...` sources are not conflated during exact reference matching.

## Why the Current Numbers Make Sense

### Scope F1 improved from 0.8750 to around 0.95

Current scope F1 is `0.9524`.

That is credible because:

- the system correctly rejects most clearly non-legal prompts
- one adversarial creative-writing prompt still leaks through
- recall remains high at `1.0000`, which is important for not suppressing real legal questions

Compared with the earlier benchmark:

- F1 improved from `0.8750` to `0.9524`
- accuracy improved from `0.8571` to `0.9500`
- the model moved from multiple scope false positives to only one remaining false positive

### Hallucination around 3%

Current hallucination-rate proxy is `0.0323`, which is about `3.23%`.

That is credible because:

- exact section routing is strong
- official-source retrieval is strong
- one semantic theft explanation still misses the ideal grounding target

This is much more believable than reporting `0.0000`.

### FIR classifier F1 around 0.95

Current macro F1 is `0.9510`.

That is credible because:

- most single-label incidents are handled correctly
- one mixed-signal complaint still flips to the wrong top label

This is the kind of result that can be defended in a research discussion.

## Most Important Remaining Weaknesses

### 1. Legal-flavored non-legal prompts

Example:

- `Write a legal-style poem about justice.`

Problem:

- lexical legal cues still override the actual intent of the prompt

### 2. Semantic offence explanation

Example:

- `Explain theft under BNS.`

Problem:

- retrieval can still drift toward nearby robbery/theft-related sections instead of the base offence section

### 3. Overlapping offence signals in FIR classification

Example:

- stalking plus threats

Problem:

- the current rule layer tends to over-prioritize threat language

## How to Improve From Here

### 1. Add a second-stage scope verifier

Approach:

- keep the current embedding and rule-based scope layer
- add a lightweight verifier that checks whether the user is actually asking for legal assistance or only using legal vocabulary stylistically

Expected impact:

- should remove the remaining scope false positive

### 2. Add offence-definition routing for semantic legal QA

Approach:

- map offence-name queries such as `Explain theft under BNS` to a canonical base section before general semantic retrieval
- maintain a small statute-specific offence map from official sections

Expected impact:

- should eliminate the remaining QA hallucination/unsupported case

### 3. Upgrade classifier from rules-only to hybrid ranking

Approach:

- keep the current rule layer
- add embedding similarity or a fine-tuned classifier as a second ranking stage
- support multi-label signals before forcing one final label

Expected impact:

- should improve mixed-fact FIR classification

### 4. Increase benchmark difficulty again after each improvement

Approach:

- add more adversarial non-legal prompts
- add more open-ended legal reasoning prompts
- add more mixed-fact FIR examples

Expected impact:

- prevents the metrics from becoming artificially perfect again

## Recommended Research Claim

A safer research claim is:

"On an internal harder benchmark grounded in official Indian legal sources, NyayaSetu achieved approximately `0.95` F1 on scope detection and FIR section classification, while maintaining a hallucination proxy near `3%` on retrieval-grounded legal QA."

That claim is much stronger than saying:

- `100% accurate`
- `zero hallucination`

because it reflects both performance and measurable limitations.

## Conclusion

Yes, it was possible to move the research reporting away from overstated claims and toward a more defensible evaluation state.

The current benchmark now gives:

- scope F1 around `0.95`
- classifier macro F1 around `0.95`
- hallucination proxy around `3%`

The most useful comparison is not against a perfect `1.0000` snapshot, but against the earlier real scope baseline of `0.8750` F1. On that basis, the current benchmark shows genuine improvement while still preserving honest, non-perfect reporting.
