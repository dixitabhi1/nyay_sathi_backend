# NyayaSetu Case-Law Corpus

## Purpose

- NyayaSetu now supports verified case-law retrieval through a generated corpus at `data/corpus/legal_case_law_corpus.jsonl`.
- The corpus is merged automatically with the main bare-act corpus by `backend/app/services/corpus_records.py`.
- Case-search responses only cite records retrieved from this corpus; if no matching judgment is retrieved, the backend still returns an empty `results` array instead of inventing a citation.

## Data Sources

- Supreme Court judgments are imported from the public AWS Open Data dataset: `https://registry.opendata.aws/indian-supreme-court-judgments/`.
- High Court judgments are imported from the public AWS Open Data dataset: `https://registry.opendata.aws/indian-high-court-judgments/`.
- Both datasets are managed by Dattam Labs / OpenJustice and list CC-BY-4.0 licensing in the AWS registry.
- Supreme Court records use metadata/headnotes and link back to the public S3 English judgment archive.
- High Court records use metadata/extracted visible text and link to the public S3 PDF object where available.

## Current Local Build

- Current generated corpus rows: `10,473`.
- Supreme Court rows: `7,200`.
- High Court rows: `3,273`.
- Rebuilt FAISS/PageIndex merged records: `12,839`.

## Refresh Commands

```powershell
.\.venv\Scripts\python.exe ingestion\scripts\import_open_case_law.py `
  --limit 10500 `
  --supreme-court-limit 7200 `
  --high-court-limit 3300 `
  --supreme-court-years 2025 2024 2023 2022 2021 2020 2019 2018 2017 2016 `
  --high-court-years 2025 2024 `
  --output data\corpus\legal_case_law_corpus.jsonl
```

```powershell
.\.venv\Scripts\python.exe rag\indexing\build_faiss_index.py `
  --batch-size 256 `
  --checkpoint-dir data\index\checkpoints\legal_case_law_build
```

```powershell
.\.venv\Scripts\python.exe rag\indexing\build_page_index.py
```

## Retrieval Behavior

- Case-law rows are marked as `source_type = judgment` and `document_type = case_law`.
- Each row stores `case_title`, `court`, `parties`, `decision_date`, `case_number`, `verdict`, `bench`, `dataset`, and `source_url`.
- Legal research fetches a wider candidate set for `case_search` so statutes do not crowd out judgment matches.
- Frontend research output now renders verified case cards with court, similarity score, verdict/disposal, reasoning metadata, and source links.
- Hugging Face Spaces cannot accept non-LFS files over 10 MiB, so the Space deployment can cache this corpus from `REMOTE_CASE_LAW_CORPUS_URL`. When that environment variable is not set on a Space, NyayaSetu falls back to the GitHub raw corpus URL for this repository.

## Limitations

- The importer intentionally avoids hallucinated summaries. It uses the public metadata/headnote text already present in the datasets.
- Supreme Court source links point to the dataset archive plus PDF filename fragment because the public dataset stores English PDFs in yearly TAR archives.
- For production-grade full-text judgment reasoning, run a slower PDF-text extraction pipeline over selected archives and append those full-text passages as additional `judgment_passage` rows.
