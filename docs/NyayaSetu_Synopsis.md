# NyayaSetu: AI-Powered Legal Intelligence and FIR Workflow Platform

## 1. Introduction

NyayaSetu is an AI-powered legal-tech platform built to improve access to justice in India by connecting citizens, police personnel, and lawyers through a unified digital system. The platform combines legal research, complaint drafting, FIR generation, case analysis, lawyer discovery, legal networking, and workflow dashboards inside a single application. Its core goal is to make legal help faster, more transparent, more understandable, and more operationally useful.

Unlike generic chat assistants, NyayaSetu is designed as a grounded legal system. It uses legal corpora, structured document indexing, retrieval pipelines, role-aware workflows, approval-based access control, and explainable answers tied to specific statutory material. This makes the platform more suitable for legal assistance, FIR preparation, and professional collaboration than a plain large language model interface.

## 2. Problem Statement

Legal access in India is still fragmented for most users:

- Citizens often do not know which law applies to their issue or how to write a proper complaint.
- Police workflows can be slowed by incomplete applications, handwritten submissions, and repetitive FIR drafting effort.
- Lawyers need better digital channels for discovery, trust-building, knowledge sharing, and client communication.
- Traditional legal search tools are difficult for non-experts and often fail to explain laws in plain language.
- Pure LLM systems can produce hallucinations, weak citations, and legally unsafe responses if they are not grounded in reliable sources.

NyayaSetu addresses these gaps by combining hybrid legal retrieval, workflow automation, and role-specific legal assistance.

## 3. Objectives

The major objectives of NyayaSetu are:

- Provide clear and grounded legal guidance in simple, human-understandable language.
- Support hybrid legal retrieval using both semantic similarity and structured document navigation.
- Help citizens draft complaints and applications that can be submitted to police authorities.
- Help police personnel convert citizen inputs into more complete and structured FIR drafts.
- Help lawyers review FIRs, analyze legal issues, and connect with users through a professional platform.
- Create an approval-aware ecosystem where lawyer and police accounts are verified before privileged access is granted.
- Build a scalable legal AI foundation that can evolve with improved retrieval, better datasets, and stronger fine-tuned models.

## 4. Proposed Solution

NyayaSetu is implemented as a modular legal intelligence platform with a separate frontend application and a FastAPI backend. The system combines:

- An AI Legal Assistant for legal questions, case support, and practical next steps.
- A hybrid retrieval engine that uses both vector-based RAG and PageIndex-based structural reasoning.
- A redesigned FIR studio with separate workflows for citizens, police officers, and lawyers.
- A lawyer marketplace and social knowledge network.
- Realtime messaging and notifications for ongoing communication.
- Role-aware authentication, approval workflows, and admin oversight.

This architecture allows NyayaSetu to function not only as a chatbot, but as a digital justice operations platform.

## 5. Key Features and Modules

### 5.1 AI Legal Assistant

Users can describe a legal issue in plain language and receive:

- possible relevant legal provisions
- plain-language explanations
- grounded references to sections or statutes
- recommended next steps
- related workflow suggestions such as complaint drafting or lawyer discovery

### 5.2 Hybrid Retrieval Engine

NyayaSetu uses a dual retrieval strategy:

- RAG pipeline for semantic similarity over chunked legal text
- PageIndex pipeline for reasoning-oriented traversal of legal document structure such as Act -> Chapter -> Section -> Clause

This combination improves explainability and reduces over-reliance on embeddings alone.

### 5.3 FIR Studio

The FIR system is designed as a role-specific workflow:

- Citizen mode drafts a complaint application in a form suitable for submission to a police station or officer.
- Police mode converts the application or provided facts into a more complete FIR draft.
- Lawyer mode analyzes the FIR, highlights issues, and provides legal review support.

The FIR workflow supports manual entry, complaint upload, OCR-assisted extraction, voice input, multilingual drafting, edit logs, comparative section references, and PDF download.

### 5.4 Case Analysis and Evidence Support

Users can submit facts or documents for legal analysis. The system can surface:

- likely sections
- relevant statutory context
- preliminary legal reasoning
- evidence handling guidance
- practical recommendations

### 5.5 Lawyer Discovery and Network

NyayaSetu includes a verified lawyer ecosystem where users can:

- search lawyers by specialization, city, experience, and rating
- view lawyer handles and public profiles
- follow lawyers
- read legal posts and insights
- contact lawyers through direct messaging

### 5.6 Dashboards and Role-Based Operations

The platform contains dedicated surfaces for:

- citizens
- lawyers
- police users
- administrators

Lawyer and police dashboards are visible only after approval. The admin panel allows review of applications, approvals, and operational data needed to manage the ecosystem.

## 6. System Architecture

NyayaSetu follows a layered architecture:

1. Frontend client for user interaction, role-aware navigation, and workflow execution.
2. FastAPI backend for APIs, authentication, routing, and orchestration.
3. Service layer for legal reasoning, retrieval, FIR generation, messaging, admin operations, and lawyer workflows.
4. Hybrid retrieval layer composed of:
   - FAISS-based semantic retrieval over embedded legal chunks
   - PageIndex-based structural retrieval over legal hierarchy
5. Inference layer for grounded answer generation and domain-specific output composition.
6. Persistence layer for users, approvals, conversations, FIR records, lawyer profiles, and analytics.

The system is also designed for operational reliability. Hosted startup was improved by making heavy retrieval components initialize lazily, while application authentication and session data can fall back to local SQLite in constrained hosted environments when remote database connectivity is unstable.

## 7. Hybrid Retrieval Workflow

When a user submits a legal query, the system follows a hybrid workflow:

1. Understand the query intent, role context, and possible legal domain.
2. Run semantic retrieval over embedded legal chunks.
3. Traverse the PageIndex to identify logically relevant sections in the legal hierarchy.
4. Fuse and rerank results using relevance, legal coverage, and structural confidence.
5. Build a grounded context package with citations and metadata.
6. Generate an answer that explains the law in plain language while avoiding unsupported assumptions.

This workflow is especially useful in law because legal meaning often depends on hierarchy, section boundaries, and closely related provisions rather than only semantic similarity.

## 8. Technology Stack

### Frontend

- React
- TypeScript
- Vite
- TailwindCSS
- shadcn/ui

### Backend

- Python
- FastAPI
- SQLAlchemy
- Pydantic

### Retrieval and Search

- FAISS for vector search
- sentence-transformer style embeddings
- structured PageIndex JSON for hierarchy-aware traversal
- metadata filtering and reranking

### Data and Storage

- SQLite and libSQL/Turso style support for application state
- DuckDB for corpus analytics
- JSON/JSONL based processed legal datasets
- filesystem-based local indexes and artifacts

### AI and Training

- Transformers
- PyTorch
- PEFT / LoRA / QLoRA
- task-specific fine-tuning experiments for legal assistance and FIR generation

### OCR and Speech Support

- OCR-based complaint extraction
- speech-to-text support for voice FIR workflows

## 9. Legal Data Sources

NyayaSetu is designed around Indian legal sources such as:

- Bharatiya Nyaya Sanhita (BNS)
- Bharatiya Nagarik Suraksha Sanhita (BNSS)
- Indian Penal Code (IPC) for historical comparison and transition support
- Code of Criminal Procedure (CrPC) for legacy legal references
- selected judgments and related legal materials

The dataset pipeline includes ingestion, cleaning, chunking, indexing, and structured mapping to support both retrieval and training.

## 10. Working Methodology

The platform works through the following stages:

1. Collect official or curated legal sources.
2. Clean and normalize the text.
3. Chunk the text for semantic retrieval.
4. Build embeddings and store vector indexes.
5. Build PageIndex hierarchies for structural navigation.
6. Accept user input through chat, upload, voice, or workflow forms.
7. Retrieve and rerank legal context.
8. Generate grounded outputs for legal assistance, FIR drafting, or case analysis.
9. Persist records, edits, messages, approvals, and user-facing workflow data.

This methodology helps balance speed, explainability, and legal usefulness.

## 11. Model Strategy

NyayaSetu uses a retrieval-first strategy rather than relying entirely on a fine-tuned model. The live system prioritizes grounded responses produced from retrieved legal context. Alongside this, local training pipelines are used to improve:

- plain-language legal explanation
- follow-up legal guidance
- FIR drafting quality
- multilingual workflow support

Experiments have shown that lower loss alone is not enough for legal quality. Therefore, model evaluation is done against benchmark prompts and compared with the grounded backend answer path before any model is promoted to live use.

## 12. Expected Outcomes

NyayaSetu aims to deliver the following outcomes:

- faster and more accessible legal assistance for citizens
- better quality complaint and FIR preparation
- stronger explainability through grounded legal citations
- improved operational support for police and lawyers
- a verified digital legal network for discovery, communication, and trust
- a scalable foundation for future Indian legal AI infrastructure

## 13. Advantages

The main advantages of NyayaSetu are:

- hybrid retrieval improves trustworthiness over plain LLM chat
- role-specific workflows make the platform practically useful, not just informational
- FIR generation is separated for citizen, police, and lawyer use cases
- admin approvals improve verification for sensitive professional roles
- social and messaging features make the platform a continuing ecosystem rather than a one-time tool
- modular architecture supports future model, data, and workflow upgrades

## 14. Current Limitations

Although NyayaSetu is functionally broad, some limitations remain:

- legal data coverage is still expanding, especially across judgments and additional statutes
- model fine-tuning has not yet surpassed the strongest grounded backend answer path for all benchmark cases
- hosted environments may still need careful tuning for latency, persistence, and heavy OCR or inference tasks
- multilingual performance and document understanding can be improved further

## 15. Future Scope

The future scope of NyayaSetu includes:

- expanding statute and judgment coverage
- stronger reranking and citation-aware answer generation
- better multilingual complaint and FIR support
- improved fine-tuned legal and FIR specialist models
- deeper analytics for crime patterns and operational dashboards
- production-grade persistent deployments across frontend, backend, and legal data services
- possible integration with institutional legal, police, or court workflows

## 16. Conclusion

NyayaSetu represents a practical legal AI platform built for the Indian justice ecosystem. By combining hybrid retrieval, grounded legal explanation, FIR workflow automation, verified professional access, and collaborative legal services, the system moves beyond a simple chatbot and toward a structured digital legal infrastructure. Its design emphasizes accuracy, explainability, usability, and scalability, making it a strong foundation for accessible and intelligent legal technology.
