# NyayaSetu Hybrid Retrieval Architecture

NyayaSetu now uses a hybrid legal retrieval strategy that combines semantic retrieval with structure-aware navigation.

## Why Hybrid Retrieval

Standard vector search is strong for:

- plain-language legal questions
- paraphrased offence descriptions
- related fact patterns where exact section names are not mentioned

But legal work also depends on document structure. Users often ask:

- "How many sections are in BNS?"
- "What does Section 173 BNSS say?"
- "Which chapter covers general exceptions?"

For those queries, similarity alone is not enough. The system also needs to understand the hierarchy of the act and navigate it directly.

That is why NyayaSetu now runs two retrieval paths in parallel:

1. `RAG / semantic retrieval`
   - embeddings over legal chunks
   - FAISS nearest-neighbor lookup
   - best for concept and fact-pattern matching
2. `PageIndex / structural retrieval`
   - act -> chapter -> section -> clause hierarchy
   - exact reference matching and structure traversal
   - best for section lookups, act totals, and explainable legal grounding

## Query Handling Flow

1. The backend analyzes the query for legal intent, statute references, and act aliases.
2. Semantic retrieval expands the query into variants and searches the FAISS index.
3. PageIndex retrieval searches structured nodes using:
   - act aliases
   - chapter hints
   - exact section references
   - linked citations
4. The retriever fuses both result sets and re-ranks them using:
   - semantic relevance
   - structural confidence
   - exact-reference bonuses
   - metadata alignment
5. The legal engine passes only grounded sources to answer generation.
6. Final answers include:
   - simple-language explanation
   - supporting citations
   - reference paths such as `Act -> Chapter -> Section`
   - retrieval confidence signals

## Implementation

Main components:

- `backend/app/services/retriever.py`
  - hybrid query decomposition
  - semantic + PageIndex retrieval
  - fusion and re-ranking
- `backend/app/services/page_index.py`
  - hierarchy extraction
  - exact citation lookup
  - structure overview answers
- `backend/app/services/legal_engine.py`
  - grounded source formatting
  - PageIndex-driven structural answers
  - source confidence and retrieval mode exposure
- `rag/indexing/build_page_index.py`
  - standalone PageIndex build step

Supporting configuration:

- `PAGE_INDEX_PATH`
- `PAGE_INDEX_TOP_K`
- `PAGE_INDEX_SCOPE_THRESHOLD`
- `HYBRID_SEMANTIC_WEIGHT`
- `HYBRID_PAGE_INDEX_WEIGHT`
- `HYBRID_CROSS_SIGNAL_BONUS`
- `HYBRID_EXACT_REFERENCE_BONUS`

## Why PageIndex Matters in Legal Reasoning

PageIndex is useful because legal documents are not flat text corpora. They are drafted as structured instruments where meaning depends on:

- chapter placement
- section numbering
- clause nesting
- linked cross-references

Using structure-aware retrieval improves:

- exact section matching
- explainability
- count and coverage questions
- grounded navigation across related provisions
- hallucination resistance on statute-structure queries

## Scalability Notes

The architecture scales by separating concerns:

- FAISS handles broad semantic recall efficiently.
- PageIndex stays lightweight because it stores structured metadata, not dense vectors.
- Both indices can be rebuilt independently from the corpus pipeline.
- Hybrid fusion keeps the response path fast while improving trustworthiness for statute navigation.

Recommended production workflow:

1. rebuild corpus chunks
2. rebuild FAISS index
3. rebuild PageIndex
4. run benchmark prompts across semantic-only vs hybrid retrieval
5. deploy only after grounded-answer checks pass
