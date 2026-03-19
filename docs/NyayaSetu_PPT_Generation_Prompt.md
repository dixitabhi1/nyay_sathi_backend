# NyayaSetu PPT Generation Prompt

Use the prompt below in ChatGPT, Gamma, Canva, Tome, or any presentation-generation tool to create a polished project PPT for NyayaSetu.

## Prompt

Create a professional presentation deck for **NyayaSetu**, an **AI-powered legal-tech platform for India** that connects **citizens, police, lawyers, and administrators** through a single digital justice workflow.

Presentation goals:

- Explain the real problem NyayaSetu solves in Indian legal access.
- Present NyayaSetu as a full-stack platform, not just a chatbot.
- Highlight the product workflows, AI architecture, FIR studio, and role-based approval system.
- Keep the tone investor-ready, academic, and product-demo friendly at the same time.
- Use a modern legal-tech visual style with deep navy, white, light grey, and subtle gold accents.

Target audience:

- professors or academic evaluators
- hackathon or demo-day judges
- product reviewers or incubator panels
- legal-tech stakeholders

Deck requirements:

- 12 to 15 slides
- strong visual hierarchy
- concise but polished language
- each slide should have:
  - a slide title
  - 3 to 5 high-signal points
  - a suggestion for visuals or diagrams
  - speaker notes in short form

Mandatory slide flow:

1. Title slide
   - NyayaSetu
   - AI Powered Legal Bridge for Citizens, Police, Lawyers, and Admins
   - subtitle about fast, transparent, intelligent legal access

2. Problem statement
   - citizens struggle with legal complexity
   - police receive unstructured complaints
   - lawyers spend time on repetitive research and review
   - approvals and trust are weak in public legal marketplaces

3. Vision and platform mission
   - make justice accessible and intelligent through technology
   - connect all legal stakeholders through one workflow system

4. Product overview
   - AI legal assistant
   - FIR studio
   - lawyer discovery and social network
   - police dashboard
   - admin approval console

5. Hybrid AI architecture
   - semantic RAG using embeddings and FAISS
   - PageIndex-based reasoning retrieval using legal structure
   - grounded response assembly
   - low-hallucination design

6. Query handling workflow
   - user query
   - intent detection
   - parallel RAG and PageIndex retrieval
   - fusion and reranking
   - grounded answer with citations

7. FIR studio
   - manual entry
   - complaint upload with OCR
   - voice complaint intake
   - outputs:
     - citizen complaint application
     - police FIR draft
     - lawyer FIR analysis
   - comparative BNS, BNSS, IPC, and CrPC sections

8. Role-based onboarding and trust system
   - citizen account starts immediately
   - lawyer and police roles require admin approval
   - requested role, ID, organization, and city captured at registration
   - dashboards visible only after approval

9. Admin panel
   - approval queue
   - linked lawyer profile details
   - recent FIR activity
   - platform metrics
   - operational control and governance

10. Lawyer marketplace and network
   - verified handles
   - public profiles
   - follow and like features
   - messaging
   - reputation building

11. Technical stack
   - frontend: React / Vite / TypeScript / Tailwind / shadcn
   - backend: FastAPI / SQLAlchemy
   - retrieval: FAISS / PageIndex
   - databases: SQLite or Turso plus DuckDB
   - OCR and speech: Tesseract / Whisper
   - training: QLoRA pipeline

12. Key differentiators
   - Indian legal focus
   - grounded hybrid retrieval
   - role-aware FIR generation
   - admin approval workflow
   - self-hosted open-source stack

13. Demo or workflow slide
   - citizen registers
   - chooses role
   - files complaint
   - admin approves professional roles
   - lawyer or police uses specialized dashboard

14. Impact and future roadmap
   - better legal access
   - better complaint quality
   - lower legal confusion
   - future improvements: stronger fine-tuned models, better OCR, broader court coverage

15. Closing slide
   - NyayaSetu
   - bridging citizens, police, lawyers, and legal intelligence
   - thank you / Q&A

Visual guidance:

- use flowcharts for architecture
- use journey diagrams for product workflow
- use cards for features
- use iconography for citizen, police, lawyer, admin, FIR, AI, and legal search
- avoid generic startup visuals
- keep it serious, clean, and credible

Output format:

- first provide the full slide-by-slide structure
- then provide suggested speaker notes
- then provide a final condensed version suitable for direct PPT import
