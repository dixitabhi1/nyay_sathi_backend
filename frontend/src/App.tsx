import { FormEvent, Suspense, lazy, useMemo, useState } from "react";

import { AccountPanel } from "./components/AccountPanel";
import { ModuleCard } from "./components/ModuleCard";
import { ResponsePanel } from "./components/ResponsePanel";
import { WorkspaceForm } from "./components/WorkspaceForm";
import {
  ModuleKey,
  citizenAssistantHighlights,
  exploreCards,
  fillCasePreset,
  fillDraftPreset,
  fillStrengthPreset,
  lawyerNetworkFeed,
  lawyerProfiles,
  moduleOrder,
  modules,
  platformNavigation,
  policeDashboardCards,
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

function scrollToSection(sectionId: string) {
  requestAnimationFrame(() => {
    document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

export default function App() {
  const [activeModule, setActiveModule] = useState<ModuleKey>("chat");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<unknown>(null);

  const [question, setQuestion] = useState("My landlord is refusing to return my deposit. What legal options do I have?");
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
    scrollToSection("workspace");
  }

  function openModule(module: ModuleKey) {
    setActiveModule(module);
    scrollToSection("workspace");
  }

  function handlePlatformNavigation(item: (typeof platformNavigation)[number]) {
    if ("module" in item && item.module) {
      setActiveModule(item.module);
    }
    scrollToSection(item.section);
  }

  return (
    <div className="layout-shell product-shell">
      <aside className="side-rail">
        <div className="brand-block">
          <div className="brand-mark">NS</div>
          <div>
            <p className="brand-label">NyayaSetu</p>
            <p className="brand-subtitle">AI legal bridge for citizens, police, and lawyers</p>
          </div>
        </div>

        <button className="new-chat-button" onClick={() => openModule("chat")} type="button">
          <span className="new-chat-icon">+</span>
          <span>
            <strong>Start legal help</strong>
            <small>Open the AI legal assistant with grounded retrieval</small>
          </span>
        </button>

        <section className="side-section">
          <p className="section-kicker">Navigation</p>
          <div className="side-nav compact-nav">
            {platformNavigation.map((item) => (
              <button key={item.label} className="nav-link-card" onClick={() => handlePlatformNavigation(item)} type="button">
                {item.label}
              </button>
            ))}
          </div>
        </section>

        <section className="side-section">
          <p className="section-kicker">Core workspaces</p>
          <nav className="side-nav">
            {moduleOrder.map((key) => (
              <ModuleCard
                key={key}
                active={activeModule === key}
                title={modules[key].title}
                description={modules[key].description}
                onClick={() => openModule(key)}
              />
            ))}
          </nav>
        </section>
      </aside>

      <main className="main-stage">
        <section className="hero-panel" id="hero">
          <div className="hero-copy-grid">
            <div className="hero-copy-stack">
              <p className="eyebrow">Digital justice ecosystem</p>
              <h1>NyayaSetu — AI Powered Legal Bridge for Citizens, Police & Lawyers</h1>
              <p className="hero-copy">
                File complaints, analyze legal cases, connect with verified lawyers, and understand the law through one
                intelligent platform built around faster, transparent, and grounded legal access.
              </p>
              <div className="hero-actions">
                <button className="hero-primary" onClick={() => openModule("fir")} type="button">
                  File a Complaint
                </button>
                <button className="hero-secondary" onClick={() => openModule("case")} type="button">
                  Analyze My Case
                </button>
                <button className="hero-secondary" onClick={() => scrollToSection("lawyer-marketplace")} type="button">
                  Find a Lawyer
                </button>
              </div>
              <div className="hero-stats">
                <article className="hero-stat-card">
                  <span>AI workflows</span>
                  <strong>FIR + RAG + OCR</strong>
                </article>
                <article className="hero-stat-card">
                  <span>For institutions</span>
                  <strong>Police dashboard</strong>
                </article>
                <article className="hero-stat-card">
                  <span>Professional layer</span>
                  <strong>Verified lawyer network</strong>
                </article>
              </div>
            </div>

            <div className="hero-visual-panel">
              <div className="motif-stack">
                <div className="motif-card motif-scale">
                  <span>Scales of justice</span>
                  <strong>Complaint triage, FIR quality, legal guidance</strong>
                </div>
                <div className="motif-card motif-columns">
                  <span>Court columns</span>
                  <strong>Citizens, police, and lawyers on one operating layer</strong>
                </div>
                <div className="motif-card motif-books">
                  <span>Law books</span>
                  <strong>BNS, BNSS, IPC, judgments, and lawyer knowledge feed</strong>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="section-shell" id="explore">
          <div className="section-heading">
            <div>
              <p className="section-kicker">Explore NyayaSetu</p>
              <h2>AI-assisted complaint workflows, legal intelligence, and professional access.</h2>
            </div>
            <div className="section-search">
              <span>Search-first experience</span>
              <strong>Citizens ask. Police review. Lawyers connect.</strong>
            </div>
          </div>
          <section className="explore-grid product-grid">
            {exploreCards.map((card) => (
              <article key={card.title} className={`explore-card ${card.tone}`}>
                <p className="card-kicker">Core capability</p>
                <h3>{card.title}</h3>
                <p>{card.description}</p>
              </article>
            ))}
          </section>
        </section>

        <section className="section-shell citizen-shell">
          <div className="section-heading">
            <div>
              <p className="section-kicker">Citizen Legal Assistant</p>
              <h2>Plain-language issues become structured legal next steps.</h2>
            </div>
          </div>
          <div className="citizen-grid">
            <article className="assistant-scenario-card">
              <span className="mini-pill">Example issue</span>
              <h3>"My landlord is refusing to return my deposit."</h3>
              <p>
                NyayaSetu should translate this into legal provisions, suggested actions, complaint drafting support,
                and relevant lawyer discovery instead of forcing legal terminology upfront.
              </p>
            </article>
            <article className="assistant-outcome-card">
              <span className="mini-pill">Assistant output</span>
              <ul className="clean-list">
                {citizenAssistantHighlights.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>
          </div>
        </section>

        <section className="section-shell" id="lawyer-marketplace">
          <div className="section-heading">
            <div>
              <p className="section-kicker">Find Lawyers</p>
              <h2>Discover verified lawyers by specialization, city, experience, and trust signals.</h2>
            </div>
            <div className="marketplace-filter-card">
              <span>Search lawyers</span>
              <strong>Criminal Law · Delhi · 8+ years · 4.5+ rating</strong>
            </div>
          </div>
          <div className="lawyer-card-grid">
            {lawyerProfiles.map((lawyer) => (
              <article key={lawyer.handle} className="lawyer-card">
                <div className="lawyer-avatar">{lawyer.name.split(" ").map((part) => part[0]).slice(0, 2).join("")}</div>
                <div className="lawyer-card-body">
                  <div className="lawyer-card-header">
                    <div>
                      <h3>{lawyer.name}</h3>
                      <p>{lawyer.handle}</p>
                    </div>
                    <span className="verified-pill">Verified</span>
                  </div>
                  <p className="lawyer-practice">{lawyer.practice}</p>
                  <p className="lawyer-meta">
                    {lawyer.court} · {lawyer.experience} · {lawyer.location}
                  </p>
                  <div className="lawyer-card-footer">
                    <span>Rating {lawyer.rating}</span>
                    <span>{lawyer.fee} consultation</span>
                  </div>
                  <button className="consult-button" type="button">
                    Book Consultation
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="section-shell" id="lawyer-network">
          <div className="section-heading">
            <div>
              <p className="section-kicker">NyayaSetu Lawyer Network</p>
              <h2>A professional social layer for legal reputation, legal writing, and citizen trust.</h2>
            </div>
          </div>
          <div className="feed-grid">
            {lawyerNetworkFeed.map((post) => (
              <article key={`${post.handle}-${post.title}`} className="feed-card">
                <div className="feed-card-header">
                  <div>
                    <p className="feed-author">{post.author}</p>
                    <span>{post.handle}</span>
                  </div>
                  <span className="mini-pill">{post.category}</span>
                </div>
                <h3>{post.title}</h3>
                <p>{post.excerpt}</p>
                <div className="feed-card-footer">
                  <span>{post.stats}</span>
                  <div className="feed-actions">
                    <button type="button">Like</button>
                    <button type="button">Comment</button>
                    <button type="button">Follow Lawyer</button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="section-shell police-shell" id="police-dashboard">
          <div className="section-heading">
            <div>
              <p className="section-kicker">Police Dashboard</p>
              <h2>Reduce paperwork, improve FIR quality, and watch location-based crime signals.</h2>
            </div>
          </div>
          <div className="police-grid">
            {policeDashboardCards.map((card) => (
              <article key={card.title} className="police-card">
                <span className="metric-label">{card.title}</span>
                <strong>{card.value}</strong>
                <p>{card.detail}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="workspace-shell" id="workspace">
          <div className="section-heading">
            <div>
              <p className="section-kicker">Active Workspace</p>
              <h2>{modules[activeModule].title}</h2>
            </div>
            <div className="workspace-chip">Grounded legal mode</div>
          </div>

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
        </section>
      </main>

      <aside className="utility-rail">
        <AccountPanel />

        <section className="utility-card launchpad-card">
          <p className="section-kicker">Quick asks</p>
          <div className="utility-list">
            {rightRailPrompts.map((prompt) => (
              <button key={prompt} className="utility-item" onClick={() => activateChatPrompt(prompt)} type="button">
                {prompt}
              </button>
            ))}
          </div>
        </section>

        <section className="utility-card">
          <p className="section-kicker">Platform map</p>
          <div className="utility-list utility-links-list">
            {quickLinks.map((link) => (
              <div key={link} className="utility-link">
                {link}
              </div>
            ))}
          </div>
        </section>

        <section className="utility-card trust-card">
          <p className="section-kicker">Mission</p>
          <h3>Making legal access faster, transparent, and intelligent using AI.</h3>
          <p>
            NyayaSetu is being shaped as a complete digital justice ecosystem that combines AI legal assistance, FIR
            support, police review, and a professional lawyer network.
          </p>
        </section>
      </aside>
    </div>
  );
}
