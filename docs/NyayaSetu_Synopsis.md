# NyayaSetu: AI-Powered Legal Intelligence and FIR Assistance Platform

## 1. Title of the Project

**NyayaSetu: AI-Powered Legal Intelligence and FIR Assistance Platform**

## 2. Introduction

India's legal system is complex, document-heavy, multilingual, and often difficult for ordinary citizens to navigate without expert assistance. People frequently struggle to understand which law applies to a given incident, how to prepare an effective complaint, what evidence should be preserved, and what immediate legal steps are practical before engaging a lawyer. Police personnel also face operational challenges when converting unstructured complaints into structured FIR drafts, identifying potentially relevant legal sections, and maintaining consistent procedural detail across reports.

NyayaSetu is designed as a practical legal-tech platform that combines artificial intelligence, retrieval-augmented generation, document understanding, and structured legal workflows to improve early-stage legal assistance. The platform is intended to help citizens understand legal situations, support police officers in drafting FIRs, assist in legal research, analyze documents and contracts, and produce readable legal drafts grounded in retrieved legal materials.

The project is intentionally built using self-hosted, open-source components. This ensures greater control over data privacy, legal-domain customization, deployment flexibility, and independence from proprietary hosted APIs. NyayaSetu therefore functions not merely as a chatbot, but as a modular legal intelligence platform tailored to Indian legal workflows.

## 3. Problem Statement

Access to legal knowledge in India remains uneven. Citizens often do not know whether an issue falls under criminal law, civil law, consumer law, cyber law, or contract law. Even when legal information is publicly available, it is rarely presented in a structured, citizen-friendly format. As a result, people delay action, draft incomplete complaints, fail to preserve critical evidence, or approach the wrong authority.

At the institutional level, police and legal support teams often receive complaints in fragmented or unstructured forms such as handwritten applications, voice narratives, screenshots, or scanned documents. Converting these materials into a consistent FIR draft or investigative summary takes time and is vulnerable to omission of important details such as date, location, witness information, or evidence references.

Legal professionals and researchers also spend substantial effort in searching statutes, reading judgments, extracting legal principles, comparing provisions, and reviewing contract language. The absence of integrated AI tooling for Indian legal materials increases time, cost, and procedural inefficiency.

NyayaSetu addresses these gaps by creating a unified platform for legal Q and A, document analysis, FIR generation, research retrieval, evidence support, and legal drafting using open-source AI and grounded legal retrieval.

## 4. Objectives

The key objectives of NyayaSetu are:

- To provide accessible legal question answering for Indian law.
- To assist in mapping incidents to likely IPC or BNS sections.
- To generate structured and editable FIR drafts from multiple input modes.
- To generate role-specific FIR outputs for citizens, police, and lawyers from the same complaint record.
- To support legal research through semantic retrieval of statutes and case materials.
- To generate legal drafts such as notices, complaints, and structured legal documents.
- To analyze contracts for clauses, risks, and missing protections.
- To analyze evidence and extract text, entities, and timeline clues.
- To estimate case strength based on evidence and procedural inputs.
- To support multilingual legal workflows, especially English and Hindi.
- To maintain a self-hosted, privacy-preserving, open-source deployment model.
- To support role-aware onboarding and approval workflows for police and lawyer accounts.

## 5. Proposed Solution

NyayaSetu is proposed as a complete AI-driven legal intelligence platform built around retrieval-augmented generation, legal document processing, and workflow-oriented backend services. The solution combines open-source large language models, embedding models, OCR pipelines, speech-to-text pipelines, legal corpus ingestion, and a modular API layer for frontend consumption.

At the center of the system is a RAG pipeline. Legal texts from official sources are cleaned, chunked, embedded, indexed in FAISS, and stored with metadata in DuckDB and JSONL. When a user submits a legal question or document, the system converts the query into an embedding, retrieves the most relevant legal chunks, and uses those retrieved materials to generate a grounded answer or legal draft. This improves factual grounding and reduces hallucinated output.

For FIR generation, NyayaSetu accepts manual entry, uploaded complaint documents, and voice transcripts. OCR and speech recognition extract text, entity extraction structures the complaint, a section classifier suggests likely BNS sections, and the system produces role-specific outputs including a citizen complaint application, police FIR draft, and lawyer review note. The FIR workflow also supports reasoning, completeness checks, comparative BNS/BNSS/IPC/CrPC mapping, PDF export for citizen applications, and version history support.

The platform uses FastAPI for backend services, React for interactive frontend flows, FAISS for vector retrieval, SQLite for lightweight application state, DuckDB for corpus analytics, and self-hosted inference gateways for future deployment of fine-tuned open-source models.

## 6. Key Features and Modules

### 6.1 AI Legal Chatbot

The AI Legal Chatbot allows users to ask natural-language legal questions. It retrieves relevant legal context from the vectorized corpus and returns grounded answers with citations, reasoning, and a disclaimer. The chatbot is designed to reject or warn on out-of-scope questions when the query is not sufficiently close to the legal corpus in embedding space.

### 6.2 Case Analysis Engine

This module analyzes incident narratives and attempts to map them to relevant legal provisions. It returns a structured case summary, applicable laws, legal reasoning, possible punishment context, evidence requirements, and recommended next steps. It is intended as an early-stage guidance layer, not a substitute for judicial determination.

### 6.3 Legal Research Engine

The Legal Research Engine supports semantic search across statutes, legal passages, and case law chunks. Rather than relying on exact keyword matching alone, it uses embeddings to retrieve legally similar content. This helps users locate relevant materials even when their wording does not match the formal legal phrasing in the source text.

### 6.4 Legal Document Drafting

NyayaSetu can generate structured drafts such as legal notices, complaints, basic contract skeletons, affidavits, and support letters. Draft generation is intended to provide an editable first version that can be reviewed and finalized by the user or legal counsel.

### 6.5 Contract Analysis

This module ingests contract text or uploaded contract files and identifies clauses, missing protections, and potential risks. It highlights areas such as unilateral discretion, uncapped indemnity, governing law gaps, dispute resolution issues, and missing termination logic.

### 6.6 Evidence Analyzer

The Evidence Analyzer processes uploaded or pasted evidence material and extracts text, entities, and timeline indicators. It can be extended to support image understanding, audio transcription, and event extraction for investigative workflows.

### 6.7 FIR Generator

The FIR Generator is one of the core modules of NyayaSetu. It supports manual FIR entry, complaint upload, and voice FIR filing. The module extracts structured information, predicts relevant BNS sections, generates legal reasoning, recommends jurisdiction, assesses completeness, and produces three role-aware outputs: a citizen complaint application, a police FIR draft, and a lawyer FIR analysis note. The citizen application can be exported as PDF and each draft remains editable with version history.

### 6.8 Voice FIR Filing

Users may narrate the complaint instead of typing it. Speech is converted into text using an open-source speech recognition model such as Whisper, cleaned, structured, and pushed into the FIR generation workflow.

### 6.9 BNS Section Predictor

This module suggests relevant provisions under Bharatiya Nyaya Sanhita based on incident description and corpus proximity. It combines rule-based support, corpus retrieval, and model-ready extension points for future fine-tuned classification.

### 6.10 Police Jurisdiction Detection

Using incident location and a jurisdiction gazetteer, the system suggests a probable police station. This improves FIR routing and helps users identify the likely jurisdiction for filing.

### 6.11 FIR Completeness Checker

The FIR Completeness Checker verifies whether key fields such as location, date, accused details, evidence information, and witness references are present. It returns a completeness score and actionable suggestions.

### 6.12 Crime Pattern Detection

This module aggregates FIR-related data over location and time windows to identify repeat incident clusters or hotspot trends. It can assist police and analysts in identifying repeated crime activity.

### 6.13 Case Strength Prediction

Case strength is estimated using structured inputs such as number of evidence items, witness count, documentary support, complaint status, recency, and jurisdiction match. The score is not a legal verdict but an operational readiness estimate.

### 6.14 Admin and Dataset Management

The project includes administrative support for updating datasets, refreshing the legal corpus, retraining models in the future, monitoring corpus size or ingestion status, and reviewing professional role applications. Operator emails configured through `ADMIN_EMAILS` can open the admin console, approve or reject pending police and lawyer accounts, and view supporting registration details, linked lawyer profiles, and recent FIR activity.

## 7. System Architecture

NyayaSetu follows a layered architecture:

1. User interaction occurs through a web frontend.
2. The frontend sends a query, document, FIR input, or evidence file to the FastAPI backend.
3. The backend preprocesses the request and converts text into embeddings using a multilingual embedding model.
4. The retrieval layer searches the FAISS index for the most relevant legal chunks.
5. Retrieved legal context is formatted and passed into the response generation pipeline.
6. The output is returned as a grounded legal answer, draft, analysis, or FIR response.

In RAG terms, the flow is:

User Query  
-> Embedding Generation  
-> Vector Retrieval  
-> Legal Context Fetch  
-> LLM Reasoning / Response Assembly  
-> Structured Output

The architecture includes:

- **Frontend Layer**: React-based interface for legal chat, drafting, FIR workflows, and previews.
- **Backend Layer**: FastAPI routes for chat, research, FIR, analysis, documents, and admin.
- **Retrieval Layer**: FAISS index with metadata-backed retrieval.
- **Application Storage**: SQLite for audit logs and FIR-related records.
- **Corpus Analytics Layer**: DuckDB for corpus chunk analytics, mappings, and ingestion state.
- **Ingestion Layer**: Scripts for fetching official legal documents, cleaning text, chunking, and indexing.
- **Inference Layer**: Mock mode, local pipeline mode, or self-hosted inference endpoints such as vLLM or TGI.
- **Training Layer**: QLoRA and instruction-tuning scripts for future domain-adapted model refinement.

## 8. Technology Stack

### Frontend

- React
- Vite
- TypeScript

### Backend

- Python
- FastAPI
- SQLAlchemy

### Machine Learning and Training

- PyTorch
- Hugging Face Transformers
- PEFT
- LoRA / QLoRA

### Embeddings

- BGE multilingual models
- Sentence Transformers

### Inference and Model Serving

- vLLM
- Text Generation Inference
- Ollama for local development

### OCR and Speech

- Tesseract OCR
- Whisper

### Databases and Retrieval

- SQLite
- DuckDB
- FAISS

### File and Data Handling

- JSONL
- Local filesystem storage

## 9. Dataset Sources

NyayaSetu is designed around official and authoritative legal sources. These include:

- Gazette of India publications
- India Code
- Ministry of Law and Justice releases
- Bharatiya Nyaya Sanhita
- Bharatiya Nagarik Suraksha Sanhita
- Bharatiya Sakshya Adhiniyam
- Indian Penal Code historical references
- Supreme Court of India judgments
- High Court judgments
- eCourts and related official legal repositories

Using official material is essential to maintain legal reliability, traceability, and grounded output.

## 10. Working Methodology

The methodology of NyayaSetu can be explained in stages.

### 10.1 Data Collection

Official legal documents, statutes, and judgments are collected using structured manifests and ingestion scripts.

### 10.2 Cleaning and Preprocessing

Downloaded content is cleaned to remove noise, normalize whitespace, and prepare usable legal text.

### 10.3 Chunking

Statutes are chunked by sections and structured boundaries, while judgments are chunked into passage windows suitable for retrieval.

### 10.4 Embedding Generation

Each chunk is converted into a vector representation using a multilingual embedding model.

### 10.5 FAISS Indexing

The generated embeddings are indexed in FAISS for efficient similarity search.

### 10.6 Query Embedding

User questions, incident descriptions, and document excerpts are embedded in the same vector space.

### 10.7 Retrieval

The system retrieves the top relevant legal chunks from the index.

### 10.8 Response Generation

Retrieved content is used to produce grounded answers, legal drafts, or FIR analysis.

### 10.9 Persistence and Editing

Generated FIRs and drafts can be stored, versioned, reopened, and edited.

### 10.10 FIR Workflow

The FIR workflow follows three paths:

- **Manual FIR**: user fills a structured form.
- **Complaint Upload**: OCR extracts text from image or PDF complaint applications.
- **Voice FIR**: speech is converted to transcript and then structured.

After extraction, the system performs:

- entity extraction
- legal section suggestion
- jurisdiction detection
- completeness evaluation
- case strength scoring
- draft generation
- save and version tracking

## 11. Model Strategy

NyayaSetu follows a hybrid open-source model strategy. The platform may use models such as LLaMA 3, Mistral, Mixtral, Falcon, or Phi-3 for generation tasks; BGE and similar models for embeddings; and Whisper for speech transcription.

The system supports three complementary approaches:

- **Instruction Fine-Tuning** for structured legal response behavior
- **Domain Adaptation** on Indian legal material
- **Retrieval-Augmented Generation** for grounded output and lower hallucination risk

The intended training pipeline includes:

Legal Dataset  
-> Cleaning and Preprocessing  
-> Instruction Formatting  
-> LoRA / QLoRA Fine-Tuning  
-> Evaluation  
-> Deployment

This approach allows the system to remain deployable even before full fine-tuning is complete, because retrieval provides grounded context while fine-tuning improves style, instruction following, and legal-domain response quality.

## 12. Expected Outcomes

The expected outcomes of NyayaSetu include:

- faster access to structured legal guidance
- better FIR drafting support for police and citizens
- improved understanding of legal sections and procedure
- reduced research effort for legal users
- improved quality of first-draft legal documents
- stronger organization of evidence and incident details
- a privacy-conscious self-hosted legal AI platform

## 13. Advantages of the System

NyayaSetu offers multiple advantages:

- fully based on open-source and self-hosted architecture
- better privacy control than third-party hosted AI APIs
- modular system design
- support for retrieval-grounded legal outputs
- useful for both citizens and institutional users
- capable of multilingual extension
- suitable for future scaling and fine-tuning

## 14. Limitations

Despite its usefulness, NyayaSetu has important limitations:

- it is not a substitute for a licensed advocate or judicial advice
- legal conclusions still depend on facts, evidence quality, and court interpretation
- OCR and speech-to-text may introduce extraction errors
- retrieval quality depends on corpus quality and freshness
- legal nuance and jurisdiction-specific interpretation may still require human review
- model outputs can still be imperfect even when grounded

## 15. Future Scope

The future scope of NyayaSetu includes:

- deeper multilingual legal support across Indian languages
- more advanced legal voice assistant workflows
- real-time court and cause-list integration
- broader case law analytics
- mobile application deployment
- lawyer and legal aid discovery integration
- advanced legal risk dashboards
- e-signature and document workflow support
- richer police jurisdiction maps
- GPU-backed scalable inference deployment for larger models

## 16. Conclusion

NyayaSetu represents a practical and socially meaningful use of open-source AI in the legal domain. By combining retrieval-augmented generation, legal corpus search, FIR drafting, document analysis, and evidence workflows, it aims to reduce barriers to legal understanding and improve operational efficiency. The platform is especially relevant in contexts where early legal guidance, structured complaint handling, and grounded legal retrieval can significantly improve outcomes for users. With continued corpus expansion, model refinement, and deployment hardening, NyayaSetu has the potential to become a valuable legal-support infrastructure for citizens, police workflows, and legal-tech innovation in India.

## Abstract

NyayaSetu is an AI-powered legal intelligence platform designed to support Indian legal workflows through open-source and self-hosted technologies. The system combines retrieval-augmented generation, legal document processing, FIR drafting assistance, semantic legal research, contract analysis, evidence analysis, and case strength estimation in a unified platform. It is built to help citizens, police officers, legal researchers, and legal professionals by converting unstructured legal inputs into grounded, structured, and editable outputs. The platform uses official legal sources such as India Code, Gazette publications, BNS, BNSS, BSA, IPC references, and court judgments, which are cleaned, chunked, embedded, and indexed in FAISS for efficient retrieval. FastAPI powers the backend, React provides the frontend interface, SQLite stores lightweight application records, and DuckDB supports corpus analytics. NyayaSetu also includes OCR and speech-to-text pipelines for complaint extraction and voice FIR filing. The project demonstrates how legal AI can be built with privacy-preserving, open-source infrastructure while remaining practical for real-world legal assistance and procedural support.

## Keywords

- Legal AI
- NyayaSetu
- FIR Generator
- Retrieval-Augmented Generation
- Indian Law
- FAISS
- Legal Research
- Open-Source AI

## Executive Summary

NyayaSetu is a self-hosted legal-tech platform built to support grounded legal assistance in the Indian context. It integrates legal Q and A, FIR generation, case analysis, document drafting, contract review, evidence analysis, and case strength estimation using open-source models and retrieval over official legal documents. The system is designed for both citizens and institutional users, especially where structured early-stage legal guidance is valuable. By combining FastAPI services, a React interface, FAISS-based retrieval, SQLite and DuckDB storage, and model-ready open-source pipelines, NyayaSetu offers a practical foundation for privacy-conscious and scalable legal intelligence tooling.
