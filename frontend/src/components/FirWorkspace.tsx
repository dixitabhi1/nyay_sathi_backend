import {
  FormEvent,
  startTransition,
  useDeferredValue,
  useEffect,
  useRef,
  useState,
} from "react";

import { api } from "../services/api";

type WorkflowKey = "manual" | "upload" | "voice";

type FIRSectionSuggestion = {
  section: string;
  title: string;
  reasoning: string;
  confidence: number;
};

type FIREvidenceItem = {
  evidence_id: number;
  file_name: string;
  file_path: string;
  media_type: string;
  uploaded_at: string;
};

type FIRStructuredData = {
  complainant_name: string | null;
  parent_name: string | null;
  address: string | null;
  contact_number: string | null;
  police_station: string | null;
  incident_date: string | null;
  incident_time: string | null;
  incident_location: string | null;
  incident_description: string;
  accused_details: string[];
  witness_details: string[];
  evidence_information: string[];
};

type FIRJurisdictionSuggestion = {
  suggested_police_station: string;
  district: string | null;
  state: string | null;
  source: string;
  confidence: number;
  latitude: number | null;
  longitude: number | null;
};

type FIRCompletenessResponse = {
  completeness_score: number;
  missing_fields: string[];
  suggestions: string[];
};

type FIRRecordResponse = {
  fir_id: string;
  workflow: string;
  status: string;
  extracted_data: FIRStructuredData;
  transcript_text: string | null;
  sections: FIRSectionSuggestion[];
  legal_reasoning: string;
  draft_text: string;
  disclaimer: string;
  jurisdiction: FIRJurisdictionSuggestion | null;
  completeness: FIRCompletenessResponse | null;
  case_strength_score: number;
  case_strength_reasoning: string[];
  evidence_items: FIREvidenceItem[];
  current_version: number;
  last_edited_at: string;
};

type FIRVersionItem = {
  version_number: number;
  draft_text: string;
  edited_by: string | null;
  edit_summary: string | null;
  created_at: string;
};

type FIRPreviewResponse = {
  extracted_data: FIRStructuredData;
  transcript_text: string | null;
  cleaned_text: string;
  sections: FIRSectionSuggestion[];
  legal_reasoning: string;
  jurisdiction: FIRJurisdictionSuggestion | null;
  completeness: FIRCompletenessResponse | null;
  case_strength_score: number;
  case_strength_reasoning: string[];
  draft_text: string;
  disclaimer: string;
};

type FIRVoiceProcessingResponse = {
  transcript_text: string;
  cleaned_text: string;
  extracted_data: FIRStructuredData;
  sections: FIRSectionSuggestion[];
  jurisdiction: FIRJurisdictionSuggestion | null;
  completeness: FIRCompletenessResponse | null;
};

type FIREvidenceInsight = {
  file_name: string;
  media_type: string;
  file_category: string;
  extracted_text: string | null;
  transcript_text: string | null;
  detected_entities: string[];
  detected_objects: string[];
  event_markers: string[];
  threat_indicators: string[];
  notes: string[];
};

type FIREvidenceAnalysisResponse = {
  fir_id: string | null;
  analyses: FIREvidenceInsight[];
};

type FIRCrimePatternSummary = {
  crime_category: string;
  incident_count: number;
  location: string;
  window_days: number;
  insight: string;
  suggested_attention_area: string;
};

type FIRHeatmapPoint = {
  location: string;
  latitude: number | null;
  longitude: number | null;
  intensity: number;
  crime_category: string;
};

type FIRCrimePatternResponse = {
  total_records: number;
  hotspot_alerts: FIRCrimePatternSummary[];
  heatmap_points: FIRHeatmapPoint[];
};

type FIRIntelligenceResponse = {
  fir_id: string;
  jurisdiction: FIRJurisdictionSuggestion | null;
  completeness: FIRCompletenessResponse;
  bns_prediction: FIRSectionSuggestion[];
  crime_pattern: FIRCrimePatternSummary | null;
};

const workflows: Record<WorkflowKey, { title: string; description: string }> = {
  manual: {
    title: "Manual Entry",
    description: "Fill a structured FIR form and generate the draft immediately.",
  },
  upload: {
    title: "Complaint Upload",
    description: "Upload a handwritten or scanned complaint for OCR and extraction.",
  },
  voice: {
    title: "Voice Filing",
    description: "Record or paste a spoken complaint and convert it into an FIR draft.",
  },
};

export function FirWorkspace() {
  const [workflow, setWorkflow] = useState<WorkflowKey>("manual");
  const [record, setRecord] = useState<FIRRecordResponse | null>(null);
  const [preview, setPreview] = useState<FIRPreviewResponse | null>(null);
  const [voicePreview, setVoicePreview] = useState<FIRVoiceProcessingResponse | null>(null);
  const [versions, setVersions] = useState<FIRVersionItem[]>([]);
  const [intelligence, setIntelligence] = useState<FIRIntelligenceResponse | null>(null);
  const [crimePatterns, setCrimePatterns] = useState<FIRCrimePatternResponse | null>(null);
  const [evidenceAnalysis, setEvidenceAnalysis] = useState<FIREvidenceAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draftText, setDraftText] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [evidenceFiles, setEvidenceFiles] = useState<FileList | null>(null);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const resultsRef = useRef<HTMLDivElement | null>(null);
  const deferredDraft = useDeferredValue(draftText);

  const [manualForm, setManualForm] = useState({
    complainant_name: "Rahul Sharma",
    parent_name: "",
    address: "Lucknow, Uttar Pradesh",
    contact_number: "9876543210",
    police_station: "Hazratganj Police Station",
    incident_date: "12 March 2026",
    incident_time: "7:30 PM",
    incident_location: "Hazratganj Market",
    incident_description: "My mobile phone was stolen by an unknown person near Hazratganj market while I was returning home.",
    accused_details: "Unknown person",
    witness_details: "",
    evidence_information: "Phone purchase invoice, nearby CCTV request",
  });
  const [uploadPoliceStation, setUploadPoliceStation] = useState("Hazratganj Police Station");
  const [voiceForm, setVoiceForm] = useState({
    transcript_text: "Yesterday evening at around 7 PM near Hazratganj market someone stole my phone.",
    police_station: "Hazratganj Police Station",
    complainant_name: "Rahul Sharma",
  });

  useEffect(() => {
    void loadCrimePatterns();
  }, []);

  useEffect(() => {
    if (!record) {
      return;
    }
    if (deferredDraft.trim() === "" || deferredDraft === record.draft_text) {
      return;
    }
    const timeout = window.setTimeout(async () => {
      try {
        setSaving(true);
        const updated = await api.firUpdateDraft(record.fir_id, {
          draft_text: deferredDraft,
          edited_by: "ui-auto-save",
          edit_summary: "Auto-save",
        });
        startTransition(() => {
          setRecord(updated as FIRRecordResponse);
        });
        await loadVersions(record.fir_id);
      } catch (caughtError) {
        setError(caughtError instanceof Error ? caughtError.message : "Failed to auto-save FIR draft.");
      } finally {
        setSaving(false);
      }
    }, 1500);
    return () => window.clearTimeout(timeout);
  }, [deferredDraft, record]);

  async function loadVersions(firId: string) {
    const response = (await api.firVersions(firId)) as { fir_id: string; versions: FIRVersionItem[] };
    startTransition(() => {
      setVersions(response.versions);
    });
  }

  async function loadCrimePatterns() {
    const response = (await api.firCrimePatterns(7)) as FIRCrimePatternResponse;
    startTransition(() => {
      setCrimePatterns(response);
    });
  }

  async function loadIntelligence(firId: string) {
    const response = (await api.firIntelligence(firId)) as FIRIntelligenceResponse;
    startTransition(() => {
      setIntelligence(response);
    });
  }

  async function handleManualSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const response = (await api.firManual({
        ...manualForm,
        accused_details: splitList(manualForm.accused_details),
        witness_details: splitList(manualForm.witness_details),
        evidence_information: splitList(manualForm.evidence_information),
      })) as FIRRecordResponse;
      setPreview(null);
      setVoicePreview(null);
      setRecord(response);
      setDraftText(response.draft_text);
      await loadVersions(response.fir_id);
      await loadIntelligence(response.fir_id);
      await loadCrimePatterns();
      queueResultsScroll();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to create FIR draft.");
    } finally {
      setLoading(false);
    }
  }

  async function handleManualPreview() {
    setLoading(true);
    setError(null);
    try {
      const response = (await api.firManualPreview({
        ...manualForm,
        accused_details: splitList(manualForm.accused_details),
        witness_details: splitList(manualForm.witness_details),
        evidence_information: splitList(manualForm.evidence_information),
      })) as FIRPreviewResponse;
      setRecord(null);
      setVersions([]);
      setIntelligence(null);
      setVoicePreview(null);
      setPreview(response);
      setDraftText(response.draft_text);
      queueResultsScroll();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to load FIR preview.");
    } finally {
      setLoading(false);
    }
  }

  async function handleUploadPreview(event: FormEvent) {
    event.preventDefault();
    if (!uploadFile) {
      setError("Select a complaint file first.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("complaint_file", uploadFile);
      formData.append("police_station", uploadPoliceStation);
      const response = (await api.firUploadPreview(formData)) as FIRPreviewResponse;
      setRecord(null);
      setVersions([]);
      setIntelligence(null);
      setVoicePreview(null);
      setPreview(response);
      setDraftText(response.draft_text);
      queueResultsScroll();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to preview complaint extraction.");
    } finally {
      setLoading(false);
    }
  }

  async function handleUploadCreate() {
    if (!uploadFile) {
      setError("Select a complaint file first.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("complaint_file", uploadFile);
      formData.append("police_station", uploadPoliceStation);
      const response = (await api.firUpload(formData)) as FIRRecordResponse;
      setPreview(null);
      setVoicePreview(null);
      setRecord(response);
      setDraftText(response.draft_text);
      await loadVersions(response.fir_id);
      await loadIntelligence(response.fir_id);
      await loadCrimePatterns();
      queueResultsScroll();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to create FIR from upload.");
    } finally {
      setLoading(false);
    }
  }

  async function handleVoiceSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      if (audioBlob) {
        formData.append("audio_file", new File([audioBlob], "voice-fir.webm", { type: audioBlob.type || "audio/webm" }));
      } else {
        formData.append("transcript_text", voiceForm.transcript_text);
      }
      formData.append("police_station", voiceForm.police_station);
      formData.append("complainant_name", voiceForm.complainant_name);
      const response = (await api.firVoice(formData)) as FIRRecordResponse;
      setPreview(null);
      setVoicePreview(null);
      setRecord(response);
      setDraftText(response.draft_text);
      await loadVersions(response.fir_id);
      await loadIntelligence(response.fir_id);
      await loadCrimePatterns();
      queueResultsScroll();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to process voice FIR.");
    } finally {
      setLoading(false);
    }
  }

  async function handleEvidenceUpload() {
    if (!record || !evidenceFiles || evidenceFiles.length === 0) {
      setError("Select evidence files to upload.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      Array.from(evidenceFiles).forEach((file) => formData.append("evidence_files", file));
      const response = (await api.firUploadEvidence(record.fir_id, formData)) as FIRRecordResponse;
      setRecord(response);
      await loadCrimePatterns();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to upload FIR evidence.");
    } finally {
      setLoading(false);
    }
  }

  async function handleManualSave() {
    if (!record) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const response = (await api.firUpdateDraft(record.fir_id, {
        draft_text: draftText,
        edited_by: "officer-review",
        edit_summary: "Manual save from editor",
      })) as FIRRecordResponse;
      setRecord(response);
      await loadVersions(record.fir_id);
      await loadIntelligence(record.fir_id);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to save FIR draft.");
    } finally {
      setSaving(false);
    }
  }

  async function startRecording() {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Audio recording is not supported in this browser.");
      return;
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunksRef.current = [];
    const recorder = new MediaRecorder(stream);
    mediaRecorderRef.current = recorder;
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunksRef.current.push(event.data);
      }
    };
    recorder.onstop = () => {
      const blob = new Blob(audioChunksRef.current, { type: recorder.mimeType || "audio/webm" });
      setAudioBlob(blob);
      stream.getTracks().forEach((track) => track.stop());
      setIsRecording(false);
    };
    recorder.start();
    setIsRecording(true);
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
  }

  async function handleVoicePreview() {
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      if (audioBlob) {
        formData.append("audio_file", new File([audioBlob], "voice-fir.webm", { type: audioBlob.type || "audio/webm" }));
      } else {
        formData.append("transcript_text", voiceForm.transcript_text);
      }
      formData.append("police_station", voiceForm.police_station);
      formData.append("complainant_name", voiceForm.complainant_name);
      const response = (await api.firVoicePreview(formData)) as FIRVoiceProcessingResponse;
      setRecord(null);
      setVersions([]);
      setIntelligence(null);
      setPreview(null);
      setVoicePreview(response);
      setDraftText(
        [
          "Voice Preview Transcript:",
          response.cleaned_text,
          "",
          "Predicted Sections:",
          ...response.sections.map((section) => `- ${section.section}: ${section.title}`),
        ].join("\n"),
      );
      queueResultsScroll();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to preview voice FIR.");
    } finally {
      setLoading(false);
    }
  }

  async function handleEvidenceAnalyze() {
    if (!evidenceFiles || evidenceFiles.length === 0) {
      setError("Select evidence files to analyze.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      Array.from(evidenceFiles).forEach((file) => formData.append("evidence_files", file));
      if (record) {
        formData.append("fir_id", record.fir_id);
      }
      const response = (await api.firAnalyzeEvidence(formData)) as FIREvidenceAnalysisResponse;
      setEvidenceAnalysis(response);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to analyze evidence.");
    } finally {
      setLoading(false);
    }
  }

  function queueResultsScroll() {
    window.setTimeout(() => {
      resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
  }

  const activePreview = workflow === "voice" ? voicePreview : preview;
  const extractedData = activePreview?.extracted_data ?? record?.extracted_data ?? null;
  const sectionSuggestions = activePreview?.sections ?? record?.sections ?? [];
  const jurisdiction = activePreview?.jurisdiction ?? record?.jurisdiction ?? null;
  const completeness = activePreview?.completeness ?? record?.completeness ?? null;
  const caseStrengthScore =
    workflow === "voice"
      ? record?.case_strength_score ?? 0
      : preview?.case_strength_score ?? record?.case_strength_score ?? 0;
  const caseStrengthReasons =
    workflow === "voice"
      ? record?.case_strength_reasoning ?? []
      : preview?.case_strength_reasoning ?? record?.case_strength_reasoning ?? [];
  const draftDisclaimer = preview?.disclaimer ?? record?.disclaimer ?? null;

  return (
    <div className="fir-workspace">
      <div className="fir-shell">
        <section className="fir-intake">
          <div className="fir-header">
            <div>
              <p className="eyebrow">AI FIR Generator</p>
              <h2>Multi-input FIR drafting</h2>
            </div>
            <span className="status-pill">{loading ? "Processing" : saving ? "Saving" : "Ready"}</span>
          </div>

          <div className="fir-workflow-tabs">
            {(Object.entries(workflows) as [WorkflowKey, { title: string; description: string }][]).map(([key, value]) => (
              <button
                key={key}
                type="button"
                className={`fir-tab ${workflow === key ? "active" : ""}`}
                onClick={() => setWorkflow(key)}
              >
                <strong>{value.title}</strong>
                <span>{value.description}</span>
              </button>
            ))}
          </div>

          {workflow === "manual" && (
            <form className="fir-form" onSubmit={handleManualSubmit}>
              <div className="two-up">
                <label>
                  Complainant Name
                  <input
                    value={manualForm.complainant_name}
                    onChange={(event) => setManualForm({ ...manualForm, complainant_name: event.target.value })}
                  />
                </label>
                <label>
                  Parent Name
                  <input value={manualForm.parent_name} onChange={(event) => setManualForm({ ...manualForm, parent_name: event.target.value })} />
                </label>
              </div>
              <div className="two-up">
                <label>
                  Address
                  <input value={manualForm.address} onChange={(event) => setManualForm({ ...manualForm, address: event.target.value })} />
                </label>
                <label>
                  Contact Number
                  <input
                    value={manualForm.contact_number}
                    onChange={(event) => setManualForm({ ...manualForm, contact_number: event.target.value })}
                  />
                </label>
              </div>
              <label>
                Police Station
                <input value={manualForm.police_station} onChange={(event) => setManualForm({ ...manualForm, police_station: event.target.value })} />
              </label>
              <div className="two-up">
                <label>
                  Incident Date
                  <input value={manualForm.incident_date} onChange={(event) => setManualForm({ ...manualForm, incident_date: event.target.value })} />
                </label>
                <label>
                  Incident Time
                  <input value={manualForm.incident_time} onChange={(event) => setManualForm({ ...manualForm, incident_time: event.target.value })} />
                </label>
              </div>
              <label>
                Incident Location
                <input
                  value={manualForm.incident_location}
                  onChange={(event) => setManualForm({ ...manualForm, incident_location: event.target.value })}
                />
              </label>
              <label>
                Incident Description
                <textarea
                  rows={6}
                  value={manualForm.incident_description}
                  onChange={(event) => setManualForm({ ...manualForm, incident_description: event.target.value })}
                />
              </label>
              <label>
                Accused Details
                <input
                  value={manualForm.accused_details}
                  onChange={(event) => setManualForm({ ...manualForm, accused_details: event.target.value })}
                />
              </label>
              <label>
                Witness Details
                <input
                  value={manualForm.witness_details}
                  onChange={(event) => setManualForm({ ...manualForm, witness_details: event.target.value })}
                />
              </label>
              <label>
                Evidence Information
                <input
                  value={manualForm.evidence_information}
                  onChange={(event) => setManualForm({ ...manualForm, evidence_information: event.target.value })}
                />
              </label>
              <div className="button-row">
                <button className="submit-button" type="submit" disabled={loading}>
                  Create FIR Draft
                </button>
                <button className="ghost-button" type="button" onClick={handleManualPreview} disabled={loading}>
                  Load Preview
                </button>
              </div>
            </form>
          )}

          {workflow === "upload" && (
            <form className="fir-form" onSubmit={handleUploadPreview}>
              <label>
                Complaint Application
                <input
                  type="file"
                  accept=".jpg,.jpeg,.png,.pdf"
                  onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
                />
              </label>
              <label>
                Police Station
                <input value={uploadPoliceStation} onChange={(event) => setUploadPoliceStation(event.target.value)} />
              </label>
              <div className="button-row">
                <button className="submit-button" type="submit" disabled={loading}>
                  Extract Complaint Data
                </button>
                <button className="ghost-button" type="button" onClick={handleUploadCreate} disabled={loading || !uploadFile}>
                  Create FIR from Upload
                </button>
              </div>
              {preview && (
                <div className="preview-card">
                  <h3>Extraction Preview</h3>
                  <p>{preview.cleaned_text}</p>
                </div>
              )}
            </form>
          )}

          {workflow === "voice" && (
            <form className="fir-form" onSubmit={handleVoiceSubmit}>
              <div className="button-row">
                {!isRecording ? (
                  <button className="ghost-button" type="button" onClick={startRecording}>
                    Start Recording
                  </button>
                ) : (
                  <button className="ghost-button" type="button" onClick={stopRecording}>
                    Stop Recording
                  </button>
                )}
                <span className="helper-text">{audioBlob ? "Audio captured and ready for transcription." : "Or paste the transcript below."}</span>
              </div>
              <label>
                Voice Transcript
                <textarea
                  rows={6}
                  value={voiceForm.transcript_text}
                  onChange={(event) => setVoiceForm({ ...voiceForm, transcript_text: event.target.value })}
                />
              </label>
              <div className="two-up">
                <label>
                  Police Station
                  <input value={voiceForm.police_station} onChange={(event) => setVoiceForm({ ...voiceForm, police_station: event.target.value })} />
                </label>
                <label>
                  Complainant Name
                  <input value={voiceForm.complainant_name} onChange={(event) => setVoiceForm({ ...voiceForm, complainant_name: event.target.value })} />
                </label>
              </div>
              <button className="submit-button" type="submit" disabled={loading}>
                Convert to FIR Draft
              </button>
              <button className="ghost-button" type="button" onClick={handleVoicePreview} disabled={loading}>
                Preview Voice Extraction
              </button>
            </form>
          )}

          {error && <div className="error-banner">{error}</div>}
        </section>

        <section className="fir-results">
          <div className="fir-summary-card" ref={resultsRef}>
            <div className="card-header-inline">
              <h3>Extracted Data</h3>
              <span className="status-pill">{activePreview ? "Preview Loaded" : record ? "Saved Draft" : "Waiting"}</span>
            </div>
            {extractedData ? (
              <dl className="fir-data-list">
                <div>
                  <dt>Complainant</dt>
                  <dd>{extractedData.complainant_name ?? "Not provided"}</dd>
                </div>
                <div>
                  <dt>Parent</dt>
                  <dd>{extractedData.parent_name ?? "Not provided"}</dd>
                </div>
                <div>
                  <dt>Address</dt>
                  <dd>{extractedData.address ?? "Not provided"}</dd>
                </div>
                <div>
                  <dt>Contact</dt>
                  <dd>{extractedData.contact_number ?? "Not provided"}</dd>
                </div>
                <div>
                  <dt>Police Station</dt>
                  <dd>{extractedData.police_station ?? "Not provided"}</dd>
                </div>
                <div>
                  <dt>Incident Date</dt>
                  <dd>{extractedData.incident_date ?? "Not provided"}</dd>
                </div>
                <div>
                  <dt>Incident Time</dt>
                  <dd>{extractedData.incident_time ?? "Not provided"}</dd>
                </div>
                <div>
                  <dt>Location</dt>
                  <dd>{extractedData.incident_location ?? "Not provided"}</dd>
                </div>
                <div className="fir-data-wide">
                  <dt>Description</dt>
                  <dd>{extractedData.incident_description}</dd>
                </div>
                <div>
                  <dt>Accused</dt>
                  <dd>{extractedData.accused_details.length > 0 ? extractedData.accused_details.join(", ") : "Not provided"}</dd>
                </div>
                <div>
                  <dt>Witnesses</dt>
                  <dd>{extractedData.witness_details.length > 0 ? extractedData.witness_details.join(", ") : "Not provided"}</dd>
                </div>
                <div>
                  <dt>Evidence</dt>
                  <dd>
                    {extractedData.evidence_information.length > 0
                      ? extractedData.evidence_information.join(", ")
                      : "Not provided"}
                  </dd>
                </div>
              </dl>
            ) : (
              <p className="helper-text">Load a preview or create an FIR draft to see the extracted complaint details here.</p>
            )}
          </div>

          <div className="fir-summary-card">
            <h3>BNS Suggestions</h3>
            <ul className="section-list">
              {sectionSuggestions.map((section) => (
                <li key={`${section.section}-${section.title}`}>
                  <strong>{section.section}</strong>
                  <span>{section.title}</span>
                  <p>{section.reasoning}</p>
                </li>
              ))}
            </ul>
          </div>

          <div className="fir-summary-card">
            <h3>Case Strength</h3>
            <p className="strength-score">{caseStrengthScore}%</p>
            <ul className="rationale-list">
              {caseStrengthReasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </div>

          <div className="fir-summary-card">
            <h3>Jurisdiction Suggestion</h3>
            <p className="strength-score jurisdiction-name">{jurisdiction?.suggested_police_station ?? "Pending"}</p>
            <ul className="rationale-list">
              <li>Source: {jurisdiction?.source ?? "n/a"}</li>
              <li>
                Confidence: {Math.round(((jurisdiction?.confidence ?? 0) * 100))}%
              </li>
            </ul>
          </div>

          <div className="fir-summary-card">
            <h3>Completeness Check</h3>
            <p className="strength-score">{completeness?.completeness_score ?? 0}%</p>
            <ul className="rationale-list">
              {(completeness?.missing_fields ?? []).map((field) => (
                <li key={field}>{field}</li>
              ))}
            </ul>
          </div>
        </section>
      </div>

      <section className="fir-draft-panel">
        <div className="panel-header">
          <h2>Editable FIR Draft</h2>
          <div className="button-row">
            <span className="status-pill">{record ? `Version ${record.current_version}` : "No draft yet"}</span>
            <button className="ghost-button" type="button" onClick={handleManualSave} disabled={!record || saving}>
              Save Draft
            </button>
          </div>
        </div>
        <textarea
          className="fir-draft-editor"
          rows={18}
          value={draftText}
          onChange={(event) => setDraftText(event.target.value)}
          placeholder="Generated FIR draft will appear here."
        />
        <p className="helper-text">{draftDisclaimer}</p>
      </section>

      <section className="fir-evidence-grid">
        <div className="fir-summary-card">
          <h3>Evidence Upload</h3>
          <input type="file" multiple onChange={(event) => setEvidenceFiles(event.target.files)} />
          <div className="button-row">
            <button className="ghost-button evidence-button" type="button" onClick={handleEvidenceAnalyze}>
              Analyze Evidence
            </button>
            <button className="ghost-button evidence-button" type="button" onClick={handleEvidenceUpload} disabled={!record}>
              Link Evidence to FIR
            </button>
          </div>
          <ul className="rationale-list">
            {(record?.evidence_items ?? []).map((item) => (
              <li key={item.evidence_id}>{item.file_name}</li>
            ))}
          </ul>
          {evidenceAnalysis && (
            <div className="evidence-analysis">
              {evidenceAnalysis.analyses.map((analysis) => (
                <div key={analysis.file_name} className="analysis-card">
                  <strong>{analysis.file_name}</strong>
                  <p>{analysis.file_category}</p>
                  <p>Objects: {analysis.detected_objects.join(", ") || "None"}</p>
                  <p>Threats: {analysis.threat_indicators.join(", ") || "None"}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="fir-summary-card">
          <h3>Version History</h3>
          <ul className="version-list">
            {versions.map((item) => (
              <li key={`${item.version_number}-${item.created_at}`}>
                <strong>v{item.version_number}</strong>
                <span>{new Date(item.created_at).toLocaleString()}</span>
                <p>{item.edit_summary ?? "Draft update"}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="fir-evidence-grid">
        <div className="fir-summary-card">
          <h3>Crime Hotspot Alerts</h3>
          <ul className="version-list">
            {(crimePatterns?.hotspot_alerts ?? []).map((alert) => (
              <li key={`${alert.crime_category}-${alert.location}`}>
                <strong>{alert.location}</strong>
                <span>{alert.incident_count} incidents</span>
                <p>{alert.insight}</p>
              </li>
            ))}
          </ul>
        </div>
        <div className="fir-summary-card">
          <h3>Heatmap Intensity</h3>
          <div className="heatmap-list">
            {(crimePatterns?.heatmap_points ?? []).slice(0, 8).map((point) => (
              <div key={`${point.crime_category}-${point.location}`} className="heatmap-row">
                <span>{point.location}</span>
                <div className="heatbar">
                  <div className="heatbar-fill" style={{ width: `${Math.min(point.intensity * 18, 100)}%` }} />
                </div>
                <strong>{point.intensity}</strong>
              </div>
            ))}
          </div>
          {intelligence?.crime_pattern && <p className="helper-text">{intelligence.crime_pattern.insight}</p>}
        </div>
      </section>
    </div>
  );
}

function splitList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}
