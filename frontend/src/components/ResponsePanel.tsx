type ModuleKey = "chat" | "case" | "research" | "draft" | "contract" | "evidence" | "fir" | "strength";

type SourceDocument = {
  title: string;
  citation: string;
  excerpt: string;
  source_type: string;
  score: number;
  source_url?: string | null;
  reference_path?: string | null;
  retrieval_mode?: string | null;
  confidence?: number | null;
  metadata: Record<string, string>;
};

type ChatResponse = {
  answer: string;
  reasoning: string;
  sources: SourceDocument[];
  disclaimer?: string;
  in_scope?: boolean;
  scope_warning?: string | null;
};

type CaseAnalysisResponse = {
  case_summary: string;
  applicable_laws: string[];
  legal_reasoning: string;
  possible_punishment: string;
  evidence_required: string[];
  recommended_next_steps: string[];
  sources: SourceDocument[];
};

type ResearchResponse = {
  summary: string;
  message?: string | null;
  results?: ResearchCaseResult[];
  hits: SourceDocument[];
};

type ResearchCaseResult = {
  case_title: string;
  court: string;
  similarity_score: string;
  parties: string;
  fir_summary: string;
  charges: string;
  verdict: string;
  source_link: string;
  comparison_reasoning: string;
};

type DraftResponse = {
  draft_type: string;
  content: string;
  notes: string[];
};

type ContractClause = {
  heading: string;
  content: string;
};

type ContractRisk = {
  severity: string;
  issue: string;
  recommendation: string;
};

type ContractAnalysisResponse = {
  summary: string;
  clauses: ContractClause[];
  risks: ContractRisk[];
  missing_clauses: string[];
};

type EvidenceEntity = {
  label: string;
  value: string;
};

type EvidenceAnalysisResponse = {
  extracted_text: string;
  entities: EvidenceEntity[];
  timeline: string[];
  observations: string[];
};

type StrengthResponse = {
  score: number;
  verdict: string;
  rationale: string[];
};

type ResponsePanelProps = {
  title: string;
  module: ModuleKey;
  content: unknown;
  loading: boolean;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function asSources(value: unknown): SourceDocument[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(isRecord).map((item) => ({
    title: typeof item.title === "string" ? item.title : "Untitled source",
    citation: typeof item.citation === "string" ? item.citation : "Unknown citation",
    excerpt: typeof item.excerpt === "string" ? item.excerpt : "",
    source_type: typeof item.source_type === "string" ? item.source_type : "source",
    score: typeof item.score === "number" ? item.score : 0,
    source_url: typeof item.source_url === "string" ? item.source_url : null,
    reference_path: typeof item.reference_path === "string" ? item.reference_path : null,
    retrieval_mode: typeof item.retrieval_mode === "string" ? item.retrieval_mode : null,
    confidence: typeof item.confidence === "number" ? item.confidence : null,
    metadata: asMetadata(item.metadata),
  }));
}

function asMetadata(value: unknown): Record<string, string> {
  if (!isRecord(value)) {
    return {};
  }
  return Object.fromEntries(
    Object.entries(value)
      .filter(([, entry]) => entry !== null && entry !== undefined && String(entry).trim() !== "")
      .map(([key, entry]) => [key, String(entry)]),
  );
}

function buildDownloadText(module: ModuleKey, content: unknown): string {
  if (!isRecord(content)) {
    return "No preview available.";
  }

  if (module === "chat") {
    const item = content as ChatResponse;
    const sources = asSources(item.sources);
    return [
      "NyayaSetu Legal Chat Preview",
      "",
      `Answer: ${item.answer ?? ""}`,
      "",
      `Reasoning: ${item.reasoning ?? ""}`,
      item.scope_warning ? `Warning: ${item.scope_warning}` : "",
      "",
      "Sources:",
      ...sources.map((source) =>
        [
          `- ${source.citation}: ${source.excerpt}${source.source_url ? ` (${source.source_url})` : ""}`,
          ...Object.entries(source.metadata).map(([key, value]) => `  ${key}: ${value}`),
        ].join("\n"),
      ),
      "",
      `Disclaimer: ${item.disclaimer ?? ""}`,
    ]
      .filter(Boolean)
      .join("\n");
  }

  if (module === "case") {
    const item = content as CaseAnalysisResponse;
    return [
      "NyayaSetu Case Analysis Preview",
      "",
      `Summary: ${item.case_summary}`,
      `Applicable laws: ${(item.applicable_laws ?? []).join(", ")}`,
      "",
      `Reasoning: ${item.legal_reasoning}`,
      `Possible punishment: ${item.possible_punishment}`,
      "",
      "Evidence required:",
      ...(item.evidence_required ?? []).map((entry) => `- ${entry}`),
      "",
      "Recommended next steps:",
      ...(item.recommended_next_steps ?? []).map((entry) => `- ${entry}`),
    ].join("\n");
  }

  if (module === "research") {
    const item = content as ResearchResponse;
    const cases = Array.isArray(item.results) ? item.results : [];
    return [
      "NyayaSetu Research Preview",
      "",
      item.summary,
      item.message ? `Note: ${item.message}` : "",
      "",
      "Similar cases:",
      ...cases.map((result) => `- ${result.case_title} (${result.court}, ${result.similarity_score}): ${result.verdict} ${result.source_link}`),
      "",
      "Retrieved sources:",
      ...asSources(item.hits).map((hit) =>
        [`- ${hit.citation}: ${hit.excerpt}`, ...Object.entries(hit.metadata).map(([key, value]) => `  ${key}: ${value}`)].join("\n"),
      ),
    ].filter(Boolean).join("\n");
  }

  if (module === "draft") {
    const item = content as DraftResponse;
    return [
      `NyayaSetu ${item.draft_type ?? "Draft"} Preview`,
      "",
      item.content ?? "",
      "",
      "Review notes:",
      ...(item.notes ?? []).map((note) => `- ${note}`),
    ].join("\n");
  }

  if (module === "strength") {
    const item = content as StrengthResponse;
    return [
      "NyayaSetu Case Strength Preview",
      "",
      `Score: ${item.score ?? 0}`,
      `Verdict: ${item.verdict ?? ""}`,
      "",
      "Rationale:",
      ...(item.rationale ?? []).map((note) => `- ${note}`),
    ].join("\n");
  }

  if (module === "contract") {
    const item = content as ContractAnalysisResponse;
    return [
      "NyayaSetu Contract Analysis Preview",
      "",
      item.summary ?? "",
      "",
      "Detected risks:",
      ...(item.risks ?? []).map((risk) => `- [${risk.severity}] ${risk.issue} | ${risk.recommendation}`),
      "",
      "Missing clauses:",
      ...(item.missing_clauses ?? []).map((entry) => `- ${entry}`),
    ].join("\n");
  }

  if (module === "evidence") {
    const item = content as EvidenceAnalysisResponse;
    return [
      "NyayaSetu Evidence Analysis Preview",
      "",
      "Extracted text:",
      item.extracted_text ?? "",
      "",
      "Entities:",
      ...(item.entities ?? []).map((entity) => `- ${entity.label}: ${entity.value}`),
      "",
      "Timeline:",
      ...(item.timeline ?? []).map((entry) => `- ${entry}`),
      "",
      "Observations:",
      ...(item.observations ?? []).map((entry) => `- ${entry}`),
    ].join("\n");
  }

  return JSON.stringify(content, null, 2);
}

function downloadPreview(module: ModuleKey, content: unknown) {
  const text = buildDownloadText(module, content);
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `nyayasetu-${module}-preview.txt`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function renderMetadata(metadata: Record<string, string>) {
  const entries = Object.entries(metadata);
  if (entries.length === 0) {
    return null;
  }

  return (
    <dl className="source-metadata">
      {entries.map(([key, value]) => (
        <div key={key}>
          <dt>{key.replace(/_/g, " ")}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function renderSources(label: string, sources: SourceDocument[]) {
  if (!sources.length) {
    return null;
  }

  return (
    <section className="preview-section">
      <div className="section-heading-row">
        <h3>{label}</h3>
        <span className="mini-pill">RAG citations</span>
      </div>
      <div className="source-list">
        {sources.map((source) => (
          <article key={`${source.citation}-${source.title}`} className="source-card">
            <div className="source-card-header">
              {source.source_url ? (
                <a href={source.source_url} target="_blank" rel="noopener noreferrer">
                  <strong>{source.citation}</strong>
                </a>
              ) : (
                <strong>{source.citation}</strong>
              )}
              <span>{source.source_type}</span>
            </div>
            <p className="source-title">{source.title}</p>
            <p>{source.excerpt}</p>
            {renderMetadata(source.metadata)}
            {source.source_url && (
              <p className="source-link-row">
                <a href={source.source_url} target="_blank" rel="noopener noreferrer">
                  Open official source
                </a>
              </p>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

function renderBody(module: ModuleKey, content: unknown) {
  if (!content) {
    return <p className="placeholder-copy">Run a legal workflow to load a readable preview here.</p>;
  }

  if (!isRecord(content)) {
    return <p className="placeholder-copy">{String(content)}</p>;
  }

  if (typeof content.error === "string") {
    return <div className="scope-warning">Request failed: {content.error}</div>;
  }

  if (module === "chat") {
    const item = content as ChatResponse;
    const sources = asSources(item.sources);

    return (
      <>
        {item.in_scope === false && item.scope_warning && <div className="scope-warning">{item.scope_warning}</div>}
        <section className="preview-section">
          <h3>Answer preview</h3>
          <div className="preview-document">
            <p>{item.answer}</p>
          </div>
        </section>
        <section className="preview-section">
          <h3>Legal reasoning</h3>
          <p>{item.reasoning}</p>
        </section>
        {renderSources("Retrieved legal context", sources)}
        {item.disclaimer && <p className="preview-disclaimer">{item.disclaimer}</p>}
      </>
    );
  }

  if (module === "case") {
    const item = content as CaseAnalysisResponse;
    return (
      <>
        <section className="preview-grid">
          <article className="metric-card">
            <span className="metric-label">Case summary</span>
            <p>{item.case_summary}</p>
          </article>
          <article className="metric-card">
            <span className="metric-label">Likely laws</span>
            <p>{(item.applicable_laws ?? []).join(", ")}</p>
          </article>
        </section>
        <section className="preview-section">
          <h3>Legal reasoning</h3>
          <p>{item.legal_reasoning}</p>
        </section>
        <section className="preview-grid">
          <article className="list-card">
            <h3>Evidence required</h3>
            <ul className="clean-list">
              {(item.evidence_required ?? []).map((entry) => (
                <li key={entry}>{entry}</li>
              ))}
            </ul>
          </article>
          <article className="list-card">
            <h3>Next steps</h3>
            <ul className="clean-list">
              {(item.recommended_next_steps ?? []).map((entry) => (
                <li key={entry}>{entry}</li>
              ))}
            </ul>
          </article>
        </section>
        <section className="preview-section">
          <h3>Possible punishment context</h3>
          <p>{item.possible_punishment}</p>
        </section>
        {renderSources("Retrieved authorities", asSources(item.sources))}
      </>
    );
  }

  if (module === "research") {
    const item = content as ResearchResponse;
    const cases = Array.isArray(item.results) ? item.results : [];
    return (
      <>
        <section className="preview-section">
          <div className="section-heading-row">
            <h3>Research summary</h3>
            <span className="mini-pill">Semantic retrieval</span>
          </div>
          <p>{item.summary}</p>
          {item.message ? <p className="muted-text">{item.message}</p> : null}
        </section>
        {cases.length > 0 ? (
          <section className="preview-section">
            <h3>Similar verified cases</h3>
            <div className="source-list">
              {cases.map((result) => (
                <article className="source-card" key={`${result.case_title}-${result.source_link}`}>
                  <div className="section-heading-row">
                    <h4>{result.case_title}</h4>
                    <span className="mini-pill">{result.similarity_score}</span>
                  </div>
                  <p className="muted-text">{result.court}</p>
                  <p>{result.fir_summary}</p>
                  <p>
                    <strong>Verdict:</strong> {result.verdict || "Not available in retrieved metadata"}
                  </p>
                  <p>
                    <strong>Reasoning:</strong> {result.comparison_reasoning}
                  </p>
                  {result.source_link ? (
                    <a href={result.source_link} target="_blank" rel="noreferrer">
                      Open source
                    </a>
                  ) : null}
                </article>
              ))}
            </div>
          </section>
        ) : null}
        {renderSources("Relevant statutes and judgments", asSources(item.hits))}
      </>
    );
  }

  if (module === "draft") {
    const item = content as DraftResponse;
    return (
      <>
        <section className="preview-section">
          <div className="section-heading-row">
            <h3>Draft preview</h3>
            <span className="mini-pill">{item.draft_type}</span>
          </div>
          <div className="preview-document">
            {String(item.content ?? "")
              .split("\n")
              .map((line, index) => (
                <p key={`${line}-${index}`}>{line || "\u00a0"}</p>
              ))}
          </div>
        </section>
        <section className="preview-section">
          <h3>Review notes</h3>
          <ul className="clean-list">
            {(item.notes ?? []).map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </section>
      </>
    );
  }

  if (module === "strength") {
    const item = content as StrengthResponse;
    return (
      <>
        <section className="preview-grid">
          <article className="score-card">
            <span className="metric-label">Case strength</span>
            <strong>{item.score}%</strong>
          </article>
          <article className="score-card">
            <span className="metric-label">Verdict</span>
            <strong className="verdict-text">{item.verdict}</strong>
          </article>
        </section>
        <section className="preview-section">
          <h3>Why this score was assigned</h3>
          <ul className="clean-list">
            {(item.rationale ?? []).map((entry) => (
              <li key={entry}>{entry}</li>
            ))}
          </ul>
        </section>
      </>
    );
  }

  if (module === "contract") {
    const item = content as ContractAnalysisResponse;
    return (
      <>
        <section className="preview-section">
          <h3>Contract summary</h3>
          <p>{item.summary}</p>
        </section>
        <section className="preview-grid">
          <article className="list-card">
            <h3>Detected clauses</h3>
            <ul className="clean-list">
              {(item.clauses ?? []).map((clause) => (
                <li key={clause.heading}>
                  <strong>{clause.heading}</strong>: {clause.content}
                </li>
              ))}
            </ul>
          </article>
          <article className="list-card">
            <h3>Missing clauses</h3>
            <ul className="clean-list">
              {(item.missing_clauses ?? []).map((entry) => (
                <li key={entry}>{entry}</li>
              ))}
            </ul>
          </article>
        </section>
        <section className="preview-section">
          <h3>Risk review</h3>
          <ul className="clean-list">
            {(item.risks ?? []).map((risk) => (
              <li key={`${risk.severity}-${risk.issue}`}>
                <strong>{risk.severity}</strong>: {risk.issue}. {risk.recommendation}
              </li>
            ))}
          </ul>
        </section>
      </>
    );
  }

  if (module === "evidence") {
    const item = content as EvidenceAnalysisResponse;
    return (
      <>
        <section className="preview-section">
          <h3>Extracted evidence text</h3>
          <div className="preview-document">
            <p>{item.extracted_text}</p>
          </div>
        </section>
        <section className="preview-grid">
          <article className="list-card">
            <h3>Entities</h3>
            <ul className="clean-list">
              {(item.entities ?? []).map((entity) => (
                <li key={`${entity.label}-${entity.value}`}>
                  <strong>{entity.label}</strong>: {entity.value}
                </li>
              ))}
            </ul>
          </article>
          <article className="list-card">
            <h3>Timeline</h3>
            <ul className="clean-list">
              {(item.timeline ?? []).map((entry) => (
                <li key={entry}>{entry}</li>
              ))}
            </ul>
          </article>
        </section>
        <section className="preview-section">
          <h3>Investigation notes</h3>
          <ul className="clean-list">
            {(item.observations ?? []).map((entry) => (
              <li key={entry}>{entry}</li>
            ))}
          </ul>
        </section>
      </>
    );
  }

  return <pre className="fallback-json">{JSON.stringify(content, null, 2)}</pre>;
}

export function ResponsePanel({ title, module, content, loading }: ResponsePanelProps) {
  return (
    <section className="response-panel">
      <div className="panel-header">
        <div>
          <p className="section-kicker">Preview</p>
          <h2>{title}</h2>
        </div>
        <div className="panel-actions">
          <span className="status-pill">{loading ? "Working" : "Ready"}</span>
          <button
            className="download-button"
            disabled={!content || loading}
            onClick={() => downloadPreview(module, content)}
            type="button"
          >
            Download preview
          </button>
        </div>
      </div>
      {loading ? <p className="placeholder-copy">Generating a structured legal preview...</p> : renderBody(module, content)}
    </section>
  );
}
