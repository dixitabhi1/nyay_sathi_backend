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

Exact payload:

```json
{
  "incident_description": "A caller impersonated a bank officer and money was withdrawn after OTP sharing.",
  "location": "Lucknow",
  "incident_date": "2026-03-11",
  "people_involved": ["Complainant", "Unknown caller"],
  "evidence": ["Call recording", "Bank SMS", "Transaction statement"],
  "language": "en"
}
```

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

Exact payload:

```json
{
  "query": "criminal intimidation for online threats",
  "top_k": 5
}
```

Render:

- semantic search summary
- list of retrieved statutes / judgments
- citation cards
- excerpt preview

### 4. Legal Document Drafting

Endpoint:

- `POST {{HF_SPACE_API_BASE_URL}}/analysis/draft`

Exact payload:

```json
{
  "draft_type": "legal notice",
  "facts": "Someone is using my research without permission.",
  "parties": ["Author", "Unauthorized user"],
  "relief_sought": "Cease use, remove copied material, and provide written undertaking.",
  "jurisdiction": "Lucknow"
}
```

Important:

- Do not send `document_type`
- Do not send `details`
- Backend requires `draft_type` and `facts`

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

Important:

- Send multipart form data
- At least one of `contract_file` or `contract_text` must be present

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

Important:

- Send multipart form data
- At least one of `evidence_file` or `evidence_text` must be present

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
- Saved FIRs

Endpoints:

- `GET {{HF_SPACE_API_BASE_URL}}/fir?limit=25`
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

Manual FIR exact payload for preview and create:

```json
{
  "complainant_name": "Abhishek Dixit",
  "parent_name": "",
  "address": "Lucknow, Uttar Pradesh",
  "contact_number": "9876543210",
  "police_station": "Hazratganj Police Station",
  "incident_date": "2026-03-11",
  "incident_time": "19:00",
  "incident_location": "Hazratganj, Lucknow",
  "incident_description": "Unknown attackers assaulted multiple people in Hazratganj.",
  "accused_details": ["Unknown attackers"],
  "witness_details": [],
  "evidence_information": []
}
```

Important:

- Do not send only `complainant_name`, `incident_description`, `incident_date`, and `incident_location`
- Backend also requires `address` and `police_station`
- For manual FIR, `accused_details`, `witness_details`, and `evidence_information` must be arrays, not comma-separated raw strings unless the frontend converts them

Voice FIR form-data fields:

- `audio_file` or `transcript_text`
- `police_station`
- `complainant_name`

Upload FIR form-data fields:

- `complaint_file`
- `police_station`

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
- saved FIR list with reopen support

Background persistence requirements for FIR:

- Do not lose in-progress FIR work when the user presses back, refreshes, or navigates away.
- Persist FIR form state for all three workflows in browser local storage:
  - manual FIR fields
  - complaint upload metadata
  - voice transcript text and police station / complainant name
- Persist the latest preview response and currently open `fir_id`
- On page reload or back navigation, restore the last in-progress FIR session automatically
- Show a banner like:
  - `Restored your last FIR draft session`

Saved FIR history requirements:

- Add a `Saved FIRs` panel or tab in the FIR module
- Use `GET {{HF_SPACE_API_BASE_URL}}/fir?limit=25`
- Render each saved FIR with:
  - complainant name
  - police station
  - incident date
  - incident location
  - case strength score
  - current version
  - last edited time
  - short draft excerpt
- Add actions:
  - `Open`
  - `Continue Editing`

Saved FIR detail flow:

- On open, call `GET {{HF_SPACE_API_BASE_URL}}/fir/{fir_id}`
- Load the editable draft editor with the returned `draft_text`
- Load versions with `GET {{HF_SPACE_API_BASE_URL}}/fir/{fir_id}/versions`
- Save edits with `PUT {{HF_SPACE_API_BASE_URL}}/fir/{fir_id}/draft`

Editing requirements:

- Allow users to reopen any previously generated FIR
- Allow editing of the FIR draft text
- Keep auto-save behavior if possible using `PUT /fir/{fir_id}/draft`
- Show version history in the UI
- After save, refresh the saved FIR list and version history

### 8. Case Strength Prediction

Endpoint:

- `POST {{HF_SPACE_API_BASE_URL}}/analysis/strength`

Exact payload:

```json
{
  "evidence_items": 3,
  "witness_count": 1,
  "documentary_support": true,
  "police_complaint_filed": false,
  "incident_recency_days": 5,
  "jurisdiction_match": true
}
```

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
- For every `422` response, parse the backend `detail` array and show a user-friendly validation error instead of dumping the raw JSON string.
- Match backend field names exactly; do not rename payload keys on the frontend.

## Final Output Requirement

Generate:

- complete frontend pages
- reusable components
- API client layer
- environment variable support
- polished responsive styling
- production-ready UI for the NyayaSetu backend described above
