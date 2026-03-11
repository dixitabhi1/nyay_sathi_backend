# Loveable Frontend Prompt For NyayaSetu

Build a polished, production-ready frontend for **NyayaSetu**, an AI-powered legal intelligence platform for Indian law.

Important product constraints:

- The frontend and backend are deployed separately.
- Frontend will be built in Loveable.
- Backend is a FastAPI API deployed on Hugging Face Spaces.
- Do not invent backend routes.
- All API integrations must use the exact endpoints listed below.
- The UI must be clean, premium, and highly readable.
- Avoid raw JSON output in the interface.
- Show answer cards, citations, previews, editable draft views, status pills, upload states, and warning banners.
- Any irrelevant or out-of-scope question should display the backend-provided warning in a visible notice card.

## Backend Configuration

Use these environment variables in the frontend:

- `VITE_API_BASE_URL={{HF_SPACE_API_BASE_URL}}`
- `VITE_SWAGGER_URL={{HF_SPACE_SWAGGER_URL}}`

Expected backend base URL:

- `{{HF_SPACE_API_BASE_URL}} = https://abhishek785-nyaya-setu.hf.space/api/v1`

Expected Swagger docs URL:

- `{{HF_SPACE_SWAGGER_URL}} = https://abhishek785-nyaya-setu.hf.space/docs`

If the final Space URL differs, replace the domain only and keep the same path structure.

## Core UI Modules

Build these modules in the left navigation:

1. AI Legal Chatbot
2. Case Analysis Engine
3. Legal Research Engine
4. Legal Document Drafting
5. Contract Analysis
6. Evidence Analyzer
7. FIR Generator
8. Case Strength Prediction

## Required Screens And Behaviors

### 1. AI Legal Chatbot

Purpose:

- Ask legal questions in natural language.
- Show grounded answers with citations.
- Show legal reasoning.
- Show disclaimer.
- Show out-of-scope warning if backend returns `in_scope: false`.

Endpoint:

- `POST {{HF_SPACE_API_BASE_URL}}/chat/query`

Payload:

```json
{
  "question": "What should be included in an FIR for phone theft?",
  "language": "en"
}
```

Response fields to render:

- `answer`
- `reasoning`
- `sources[]`
- `in_scope`
- `scope_warning`
- `disclaimer`

### 2. Case Analysis Engine

Endpoint:

- `POST {{HF_SPACE_API_BASE_URL}}/analysis/case`

Render:

- case summary
- applicable laws
- legal reasoning
- possible punishment
- evidence required
- next steps
- retrieved sources

### 3. Legal Research Engine

Endpoint:

- `POST {{HF_SPACE_API_BASE_URL}}/research/search`

Render:

- semantic search summary
- list of retrieved statutes / judgments
- citation cards
- excerpt preview

### 4. Legal Document Drafting

Endpoint:

- `POST {{HF_SPACE_API_BASE_URL}}/analysis/draft`

Render:

- readable draft preview
- downloadable text
- review notes

### 5. Contract Analysis

Endpoint:

- `POST {{HF_SPACE_API_BASE_URL}}/documents/contract/analyze`

Use multipart form data.

Inputs:

- `contract_file`
- `contract_text`

Render:

- contract summary
- extracted clauses
- risk list
- missing clauses

### 6. Evidence Analyzer

Endpoint:

- `POST {{HF_SPACE_API_BASE_URL}}/documents/evidence/analyze`

Use multipart form data.

Inputs:

- `evidence_file`
- `evidence_text`

Render:

- extracted text
- detected entities
- timeline
- investigation observations

### 7. FIR Generator

Use a dedicated workspace with three tabs:

- Manual Entry
- Complaint Upload
- Voice Filing

Endpoints:

- `POST {{HF_SPACE_API_BASE_URL}}/fir/manual/preview`
- `POST {{HF_SPACE_API_BASE_URL}}/fir/manual`
- `POST {{HF_SPACE_API_BASE_URL}}/fir/upload/preview`
- `POST {{HF_SPACE_API_BASE_URL}}/fir/upload`
- `POST {{HF_SPACE_API_BASE_URL}}/fir/voice/preview`
- `POST {{HF_SPACE_API_BASE_URL}}/fir/voice`
- `POST {{HF_SPACE_API_BASE_URL}}/fir/evidence/analyze`
- `POST {{HF_SPACE_API_BASE_URL}}/fir/{fir_id}/evidence`
- `PUT {{HF_SPACE_API_BASE_URL}}/fir/{fir_id}/draft`
- `GET {{HF_SPACE_API_BASE_URL}}/fir/{fir_id}`
- `GET {{HF_SPACE_API_BASE_URL}}/fir/{fir_id}/versions`
- `GET {{HF_SPACE_API_BASE_URL}}/fir/{fir_id}/intelligence`
- `GET {{HF_SPACE_API_BASE_URL}}/fir/analytics/patterns?window_days=7`

Render:

- extracted complainant and incident fields
- BNS section suggestions
- legal reasoning
- jurisdiction suggestion
- completeness score
- case strength score
- editable FIR draft
- version history
- evidence upload and analysis
- crime hotspot cards

### 8. Case Strength Prediction

Endpoint:

- `POST {{HF_SPACE_API_BASE_URL}}/analysis/strength`

Render:

- score
- verdict
- rationale

## UX Requirements

- Use a three-column desktop layout:
  - left navigation
  - center workspace
  - right utility rail
- Make the app responsive on mobile and tablet.
- Use clear cards, readable typography, and high information density without clutter.
- Add loading states, empty states, and error banners.
- Add download buttons for draft-style outputs.
- Never show raw JSON to the user.
- Format sources as citation cards.
- Use a professional legal-tech visual style, not a generic chatbot look.

## Technical Requirements

- Use React.
- Use environment variables for backend URLs.
- Centralize API calls in one service layer.
- Use reusable cards, preview components, and upload components.
- Keep the FIR workspace lazy-loaded if possible.
- Add a top-level settings/help link pointing to `{{HF_SPACE_SWAGGER_URL}}` so developers can inspect the live API docs.

## Final Output Requirement

Generate:

- complete frontend pages
- reusable components
- API client layer
- environment variable support
- polished responsive styling
- production-ready UI for the NyayaSetu backend described above
