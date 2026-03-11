import { FormEvent, Suspense, lazy, useMemo, useState } from "react";

import { ModuleCard } from "./components/ModuleCard";
import { ResponsePanel } from "./components/ResponsePanel";
import { WorkspaceForm } from "./components/WorkspaceForm";
import {
  ModuleKey,
  exploreCards,
  fillCasePreset,
  fillDraftPreset,
  fillStrengthPreset,
  moduleOrder,
  modules,
  quickLinks,
  rightRailPrompts,
  samplePrompts,
} from "./config/workspace";
import { api } from "./services/api";

const FirWorkspace = lazy(async () => {
  const module = await import("./components/FirWorkspace");
  return { default: module.FirWorkspace };
});

type CaseFormState = {
  incident_description: string;
  location: string;
  incident_date: string;
  people_involved: string;
  evidence: string;
};

type DraftFormState = {
  draft_type: string;
  facts: string;
  parties: string;
  relief_sought: string;
  jurisdiction: string;
};

type StrengthFormState = {
  evidence_items: number;
  witness_count: number;
  documentary_support: boolean;
  police_complaint_filed: boolean;
  incident_recency_days: number;
  jurisdiction_match: boolean;
};

export default function App() {
  const [activeModule, setActiveModule] = useState<ModuleKey>("chat");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<unknown>(null);

  const [question, setQuestion] = useState("Explain what should be included in an FIR for phone theft near a market.");
  const [caseForm, setCaseForm] = useState<CaseFormState>({
    incident_description: "A person sent repeated extortion threats over WhatsApp after demanding money.",
    location: "Bengaluru",
    incident_date: "2026-03-01",
    people_involved: "Complainant, Unknown sender",
    evidence: "WhatsApp screenshots, payment request, call log",
  });
  const [draftForm, setDraftForm] = useState<DraftFormState>({
    draft_type: "legal notice",
    facts: "The buyer paid the full amount but the seller never delivered the goods or refunded the money.",
    parties: "Buyer, Seller",
    relief_sought: "Refund with interest and compensation",
    jurisdiction: "Bengaluru",
  });
  const [contractText, setContractText] = useState(
    "Service Agreement: The provider may terminate this agreement at its sole discretion without notice. The client shall indemnify the provider for all losses.",
  );
  const [contractFile, setContractFile] = useState<File | null>(null);
  const [evidenceText, setEvidenceText] = useState(
    "On 10/03/2026 I received a call from 9876543210. The caller claimed to be from the bank and asked for OTP. Funds were debited after the call.",
  );
  const [evidenceFile, setEvidenceFile] = useState<File | null>(null);
  const [researchQuery, setResearchQuery] = useState("criminal intimidation for online threats");
  const [strengthForm, setStrengthForm] = useState<StrengthFormState>({
    evidence_items: 3,
    witness_count: 1,
    documentary_support: true,
    police_complaint_filed: false,
    incident_recency_days: 5,
    jurisdiction_match: true,
  });

  const currentPrompts = useMemo(() => {
    if (activeModule === "fir") {
      return [];
    }
    return samplePrompts[activeModule];
  }, [activeModule]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      const handlers: Partial<Record<Exclude<ModuleKey, "fir">, () => Promise<unknown>>> = {
        chat: () => api.chat(question),
        case: () =>
          api.caseAnalysis({
            ...caseForm,
            people_involved: caseForm.people_involved.split(",").map((item) => item.trim()).filter(Boolean),
            evidence: caseForm.evidence.split(",").map((item) => item.trim()).filter(Boolean),
          }),
        research: () => api.research(researchQuery),
        draft: () =>
          api.draft({
            ...draftForm,
            parties: draftForm.parties.split(",").map((item) => item.trim()).filter(Boolean),
          }),
        contract: () => {
          const formData = new FormData();
          if (contractFile) {
            formData.append("contract_file", contractFile);
          }
          if (contractText.trim()) {
            formData.append("contract_text", contractText);
          }
          return api.analyzeContract(formData);
        },
        evidence: () => {
          const formData = new FormData();
          if (evidenceFile) {
            formData.append("evidence_file", evidenceFile);
          }
          if (evidenceText.trim()) {
            formData.append("evidence_text", evidenceText);
          }
          return api.analyzeEvidence(formData);
        },
        strength: () => api.strength(strengthForm),
      };

      if (activeModule !== "fir") {
        const handler = handlers[activeModule];
        if (handler) {
          setResponse(await handler());
        }
      }
    } catch (error) {
      setResponse({ error: error instanceof Error ? error.message : "Unknown error" });
    } finally {
      setLoading(false);
    }
  }

  function applyPrompt(prompt: string) {
    switch (activeModule) {
      case "chat":
        setQuestion(prompt);
        return;
      case "research":
        setResearchQuery(prompt);
        return;
      case "case":
        setCaseForm(fillCasePreset(prompt));
        return;
      case "draft":
        setDraftForm(fillDraftPreset(prompt));
        return;
      case "contract":
        setContractText(prompt);
        return;
      case "evidence":
        setEvidenceText(prompt);
        return;
      case "strength":
        setStrengthForm(fillStrengthPreset(prompt));
        return;
      default:
        return;
    }
  }

  function activateChatPrompt(prompt: string) {
    setActiveModule("chat");
    setQuestion(prompt);
  }

  return (
    <div className="layout-shell">
      <aside className="side-rail">
        <div className="brand-block">
          <div className="brand-mark">NS</div>
          <div>
            <p className="brand-label">NyayaSetu</p>
            <p className="brand-subtitle">AI-powered legal intelligence platform</p>
          </div>
        </div>

        <button className="new-chat-button" onClick={() => setActiveModule("chat")} type="button">
          <span className="new-chat-icon">+</span>
          <span>
            <strong>Start Legal Query</strong>
            <small>Open the AI Legal Chatbot</small>
          </span>
        </button>

        <nav className="side-nav">
          {moduleOrder.map((key) => (
            <ModuleCard
              key={key}
              active={activeModule === key}
              title={modules[key].title}
              description={modules[key].description}
              onClick={() => setActiveModule(key)}
            />
          ))}
        </nav>

        <section className="side-section">
          <p className="section-kicker">NyayaSetu flows</p>
          <button className="history-item" onClick={() => setActiveModule("chat")} type="button">
            AI Legal Chatbot
          </button>
          <button className="history-item" onClick={() => setActiveModule("research")} type="button">
            Legal Research Engine
          </button>
          <button className="history-item" onClick={() => setActiveModule("fir")} type="button">
            FIR Generator
          </button>
        </section>
      </aside>

      <main className="main-stage">
        <section className="headline-panel">
          <p className="eyebrow">NyayaSetu Platform</p>
          <h1>Self-hosted legal workflows for research, drafting, FIR generation, and evidence support.</h1>
          <p className="hero-copy">
            The frontend is optimized to load primary legal workflows first and defer heavier tools like the FIR workspace
            until they are actually opened.
          </p>
        </section>

        <section className="explore-grid">
          {exploreCards.map((card) => (
            <article key={card.title} className={`explore-card ${card.tone}`}>
              <h3>{card.title}</h3>
              <p>{card.description}</p>
            </article>
          ))}
        </section>

        {activeModule === "fir" ? (
          <Suspense fallback={<section className="response-panel"><p className="placeholder-copy">Loading FIR workspace...</p></section>}>
            <FirWorkspace />
          </Suspense>
        ) : (
          <>
            <section className="prompt-strip">
              {currentPrompts.map((prompt) => (
                <button key={prompt} className="prompt-chip" onClick={() => applyPrompt(prompt)} type="button">
                  {prompt}
                </button>
              ))}
            </section>

            <WorkspaceForm
              activeModule={activeModule}
              loading={loading}
              onSubmit={handleSubmit}
              question={question}
              setQuestion={setQuestion}
              caseForm={caseForm}
              setCaseForm={setCaseForm}
              researchQuery={researchQuery}
              setResearchQuery={setResearchQuery}
              draftForm={draftForm}
              setDraftForm={setDraftForm}
              contractText={contractText}
              setContractText={setContractText}
              setContractFile={setContractFile}
              evidenceText={evidenceText}
              setEvidenceText={setEvidenceText}
              setEvidenceFile={setEvidenceFile}
              strengthForm={strengthForm}
              setStrengthForm={setStrengthForm}
            />

            <ResponsePanel module={activeModule} title={modules[activeModule].title} content={response} loading={loading} />
          </>
        )}
      </main>

      <aside className="utility-rail">
        <section className="utility-card">
          <p className="section-kicker">Example tasks</p>
          <div className="utility-list">
            {rightRailPrompts.map((prompt) => (
              <button key={prompt} className="utility-item" onClick={() => activateChatPrompt(prompt)} type="button">
                {prompt}
              </button>
            ))}
          </div>
        </section>

        <section className="utility-card">
          <p className="section-kicker">Platform modules</p>
          <div className="utility-list">
            {quickLinks.map((link) => (
              <div key={link} className="utility-link">
                {link}
              </div>
            ))}
          </div>
        </section>

        <section className="utility-card rag-note">
          <p className="section-kicker">Optimization</p>
          <h3>Faster initial load</h3>
          <p>
            Static workspace config is split out, the non-FIR form is isolated into its own component, and the FIR module
            is now lazy-loaded to reduce the initial frontend payload.
          </p>
        </section>
      </aside>
    </div>
  );
}
