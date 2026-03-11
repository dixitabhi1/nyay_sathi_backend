import { FormEvent } from "react";

import { ModuleKey, modules } from "../config/workspace";

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

type WorkspaceFormProps = {
  activeModule: Exclude<ModuleKey, "fir">;
  loading: boolean;
  onSubmit: (event: FormEvent) => void;
  question: string;
  setQuestion: (value: string) => void;
  caseForm: CaseFormState;
  setCaseForm: (value: CaseFormState) => void;
  researchQuery: string;
  setResearchQuery: (value: string) => void;
  draftForm: DraftFormState;
  setDraftForm: (value: DraftFormState) => void;
  contractText: string;
  setContractText: (value: string) => void;
  setContractFile: (file: File | null) => void;
  evidenceText: string;
  setEvidenceText: (value: string) => void;
  setEvidenceFile: (file: File | null) => void;
  strengthForm: StrengthFormState;
  setStrengthForm: (value: StrengthFormState) => void;
};

export function WorkspaceForm(props: WorkspaceFormProps) {
  const {
    activeModule,
    loading,
    onSubmit,
    question,
    setQuestion,
    caseForm,
    setCaseForm,
    researchQuery,
    setResearchQuery,
    draftForm,
    setDraftForm,
    contractText,
    setContractText,
    setContractFile,
    evidenceText,
    setEvidenceText,
    setEvidenceFile,
    strengthForm,
    setStrengthForm,
  } = props;

  return (
    <form className="composer-card" onSubmit={onSubmit}>
      <div className="composer-header">
        <div>
          <p className="section-kicker">Active module</p>
          <h2>{modules[activeModule].title}</h2>
        </div>
        <span className="rag-pill">NyayaSetu RAG</span>
      </div>

      {activeModule === "chat" && (
        <label className="field-block">
          <span>Legal question</span>
          <textarea
            className="message-composer"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            rows={7}
            placeholder="Ask about Indian law, rights, FIRs, BNS sections, contracts, judgments, or legal procedure."
          />
        </label>
      )}

      {activeModule === "case" && (
        <div className="form-stack">
          <label className="field-block">
            <span>Incident description</span>
            <textarea
              rows={5}
              value={caseForm.incident_description}
              onChange={(event) => setCaseForm({ ...caseForm, incident_description: event.target.value })}
            />
          </label>
          <div className="two-up">
            <label className="field-block">
              <span>Location</span>
              <input value={caseForm.location} onChange={(event) => setCaseForm({ ...caseForm, location: event.target.value })} />
            </label>
            <label className="field-block">
              <span>Incident date</span>
              <input value={caseForm.incident_date} onChange={(event) => setCaseForm({ ...caseForm, incident_date: event.target.value })} />
            </label>
          </div>
          <label className="field-block">
            <span>People involved</span>
            <input value={caseForm.people_involved} onChange={(event) => setCaseForm({ ...caseForm, people_involved: event.target.value })} />
          </label>
          <label className="field-block">
            <span>Evidence</span>
            <input value={caseForm.evidence} onChange={(event) => setCaseForm({ ...caseForm, evidence: event.target.value })} />
          </label>
        </div>
      )}

      {activeModule === "research" && (
        <label className="field-block">
          <span>Research query</span>
          <textarea value={researchQuery} onChange={(event) => setResearchQuery(event.target.value)} rows={5} />
        </label>
      )}

      {activeModule === "draft" && (
        <div className="form-stack">
          <div className="two-up">
            <label className="field-block">
              <span>Document type</span>
              <input value={draftForm.draft_type} onChange={(event) => setDraftForm({ ...draftForm, draft_type: event.target.value })} />
            </label>
            <label className="field-block">
              <span>Jurisdiction</span>
              <input value={draftForm.jurisdiction} onChange={(event) => setDraftForm({ ...draftForm, jurisdiction: event.target.value })} />
            </label>
          </div>
          <label className="field-block">
            <span>Facts</span>
            <textarea value={draftForm.facts} onChange={(event) => setDraftForm({ ...draftForm, facts: event.target.value })} rows={5} />
          </label>
          <label className="field-block">
            <span>Parties</span>
            <input value={draftForm.parties} onChange={(event) => setDraftForm({ ...draftForm, parties: event.target.value })} />
          </label>
          <label className="field-block">
            <span>Relief sought</span>
            <input value={draftForm.relief_sought} onChange={(event) => setDraftForm({ ...draftForm, relief_sought: event.target.value })} />
          </label>
        </div>
      )}

      {activeModule === "contract" && (
        <div className="form-stack">
          <label className="field-block">
            <span>Contract upload</span>
            <input type="file" accept=".pdf,.docx,.txt,.md" onChange={(event) => setContractFile(event.target.files?.[0] ?? null)} />
          </label>
          <label className="field-block">
            <span>Contract text</span>
            <textarea
              rows={6}
              value={contractText}
              onChange={(event) => setContractText(event.target.value)}
              placeholder="Paste contract clauses here if you are not uploading a file."
            />
          </label>
        </div>
      )}

      {activeModule === "evidence" && (
        <div className="form-stack">
          <label className="field-block">
            <span>Evidence upload</span>
            <input
              type="file"
              accept=".pdf,.docx,.txt,.png,.jpg,.jpeg,.mp3,.wav,.m4a,.ogg,.webm"
              onChange={(event) => setEvidenceFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <label className="field-block">
            <span>Evidence text</span>
            <textarea
              rows={6}
              value={evidenceText}
              onChange={(event) => setEvidenceText(event.target.value)}
              placeholder="Paste complaint text, transcript, or extracted evidence content."
            />
          </label>
        </div>
      )}

      {activeModule === "strength" && (
        <div className="form-stack">
          <div className="two-up">
            <label className="field-block">
              <span>Evidence items</span>
              <input
                type="number"
                value={strengthForm.evidence_items}
                onChange={(event) => setStrengthForm({ ...strengthForm, evidence_items: Number(event.target.value) })}
              />
            </label>
            <label className="field-block">
              <span>Witness count</span>
              <input
                type="number"
                value={strengthForm.witness_count}
                onChange={(event) => setStrengthForm({ ...strengthForm, witness_count: Number(event.target.value) })}
              />
            </label>
          </div>
          <div className="two-up">
            <label className="field-block">
              <span>Incident recency in days</span>
              <input
                type="number"
                value={strengthForm.incident_recency_days}
                onChange={(event) => setStrengthForm({ ...strengthForm, incident_recency_days: Number(event.target.value) })}
              />
            </label>
            <label className="field-block">
              <span>Documentary support</span>
              <select
                value={String(strengthForm.documentary_support)}
                onChange={(event) => setStrengthForm({ ...strengthForm, documentary_support: event.target.value === "true" })}
              >
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </label>
          </div>
          <div className="two-up">
            <label className="field-block">
              <span>Police complaint filed</span>
              <select
                value={String(strengthForm.police_complaint_filed)}
                onChange={(event) => setStrengthForm({ ...strengthForm, police_complaint_filed: event.target.value === "true" })}
              >
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </label>
            <label className="field-block">
              <span>Jurisdiction match</span>
              <select
                value={String(strengthForm.jurisdiction_match)}
                onChange={(event) => setStrengthForm({ ...strengthForm, jurisdiction_match: event.target.value === "true" })}
              >
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </label>
          </div>
        </div>
      )}

      <div className="composer-actions">
        <button className="submit-button" type="submit" disabled={loading}>
          {loading ? "Processing..." : modules[activeModule].actionLabel}
        </button>
      </div>
    </form>
  );
}
