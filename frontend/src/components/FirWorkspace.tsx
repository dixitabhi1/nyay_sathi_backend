import {
  FormEvent,
  startTransition,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { useAuth } from "../lib/auth-context";
import { api } from "../services/api";

type WorkflowKey = "manual" | "upload" | "voice";
type DraftRole = "citizen_application" | "police_fir" | "lawyer_analysis";
type LanguageKey = "en" | "hi";

type FIRSectionSuggestion = {
  statute_code: string;
  section: string;
  title: string;
  reasoning: string;
  confidence: number;
};

type FIRComparativeSections = {
  bns: FIRSectionSuggestion[];
  bnss: FIRSectionSuggestion[];
  ipc: FIRSectionSuggestion[];
  crpc: FIRSectionSuggestion[];
};

type FIRGeneratedDocument = {
  kind: DraftRole;
  title: string;
  language: LanguageKey;
  content: string;
  download_ready: boolean;
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
  draft_role: DraftRole;
  draft_language: LanguageKey;
  status: string;
  extracted_data: FIRStructuredData;
  transcript_text: string | null;
  source_application_text: string | null;
  sections: FIRSectionSuggestion[];
  comparative_sections: FIRComparativeSections | null;
  legal_reasoning: string;
  draft_text: string;
  generated_documents: FIRGeneratedDocument[];
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
  document_kind: DraftRole;
  language: LanguageKey;
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
  comparative_sections: FIRComparativeSections | null;
  legal_reasoning: string;
  jurisdiction: FIRJurisdictionSuggestion | null;
  completeness: FIRCompletenessResponse | null;
  case_strength_score: number;
  case_strength_reasoning: string[];
  draft_text: string;
  generated_documents: FIRGeneratedDocument[];
  disclaimer: string;
};

type FIRVoiceProcessingResponse = {
  transcript_text: string;
  cleaned_text: string;
  extracted_data: FIRStructuredData;
  sections: FIRSectionSuggestion[];
  comparative_sections: FIRComparativeSections | null;
  generated_documents: FIRGeneratedDocument[];
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
  comparative_sections: FIRComparativeSections | null;
  crime_pattern: FIRCrimePatternSummary | null;
};

const workflows: Record<WorkflowKey, { title: string; description: string }> = {
  manual: {
    title: "Manual Intake",
    description: "Capture structured facts and generate the document track you need.",
  },
  upload: {
    title: "Upload + OCR",
    description: "Use handwritten or scanned complaint applications as the drafting source.",
  },
  voice: {
    title: "Voice Complaint",
    description: "Convert a spoken complaint into a multilingual application or FIR draft.",
  },
};

const draftModes: Record<
  DraftRole,
  { title: string; description: string; roleRequirement: "public" | "police" | "lawyer" }
> = {
  citizen_application: {
    title: "Citizen Application",
    description: "Draft a complaint application that can be submitted to a police station or police officer.",
    roleRequirement: "public",
  },
  police_fir: {
    title: "Police FIR Draft",
    description: "Turn the complaint application into a structured FIR draft with comparative sections.",
    roleRequirement: "police",
  },
  lawyer_analysis: {
    title: "Lawyer FIR Review",
    description: "Analyze the complaint or FIR for missing facts, evidentiary gaps, and legal strategy.",
    roleRequirement: "lawyer",
  },
};

const languageOptions: { value: LanguageKey; label: string }[] = [
  { value: "en", label: "English" },
  { value: "hi", label: "Hindi" },
];

export function FirWorkspace() {
  const { user, isAuthenticated } = useAuth();
  const [workflow, setWorkflow] = useState<WorkflowKey>("manual");
  const [draftRole, setDraftRole] = useState<DraftRole>("citizen_application");
  const [language, setLanguage] = useState<LanguageKey>((user?.preferred_language as LanguageKey) ?? "en");
  const [selectedDocumentKind, setSelectedDocumentKind] = useState<DraftRole>("citizen_application");
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

  const generatedDocuments = useMemo(() => {
    if (workflow === "voice" && voicePreview) {
      return voicePreview.generated_documents;
    }
    return preview?.generated_documents ?? record?.generated_documents ?? [];
  }, [preview, record, voicePreview, workflow]);

  const extractedData = (workflow === "voice" ? voicePreview?.extracted_data : preview?.extracted_data) ?? record?.extracted_data ?? null;
  const sectionSuggestions = (workflow === "voice" ? voicePreview?.sections : preview?.sections) ?? record?.sections ?? [];
  const comparativeSections =
    (workflow === "voice" ? voicePreview?.comparative_sections : preview?.comparative_sections) ??
    record?.comparative_sections ??
    intelligence?.comparative_sections ??
    null;
  const jurisdiction = (workflow === "voice" ? voicePreview?.jurisdiction : preview?.jurisdiction) ?? record?.jurisdiction ?? null;
  const completeness = (workflow === "voice" ? voicePreview?.completeness : preview?.completeness) ?? record?.completeness ?? null;
  const caseStrengthScore = preview?.case_strength_score ?? record?.case_strength_score ?? 0;
  const caseStrengthReasons = preview?.case_strength_reasoning ?? record?.case_strength_reasoning ?? [];
  const draftDisclaimer = preview?.disclaimer ?? record?.disclaimer ?? null;
  const currentDocumentContent =
    generatedDocuments.find((item) => item.kind === selectedDocumentKind)?.content ?? record?.draft_text ?? "";

  useEffect(() => {
    setLanguage(((user?.preferred_language as LanguageKey) ?? "en"));
  }, [user?.preferred_language]);

  useEffect(() => {
    void loadCrimePatterns();
  }, []);

  useEffect(() => {
    const selected = generatedDocuments.find((item) => item.kind === draftRole) ?? generatedDocuments[0];
    if (!selected) {
      return;
    }
    setSelectedDocumentKind(selected.kind);
    setDraftText(selected.content);
  }, [draftRole, generatedDocuments]);

  useEffect(() => {
    if (!record) {
      return;
    }
    if (deferredDraft.trim() === "" || deferredDraft === currentDocumentContent) {
      return;
    }
    const timeout = window.setTimeout(async () => {
      try {
        setSaving(true);
        const updated = (await api.firUpdateDraft(record.fir_id, {
          draft_text: deferredDraft,
          document_kind: selectedDocumentKind,
          language,
          edited_by: user?.id ?? "ui-auto-save",
          edit_summary: `Auto-save for ${selectedDocumentKind}`,
        })) as FIRRecordResponse;
        startTransition(() => {
          setRecord(updated);
        });
        await loadVersions(record.fir_id);
      } catch (caughtError) {
        setError(caughtError instanceof Error ? caughtError.message : "Failed to auto-save FIR draft.");
      } finally {
        setSaving(false);
      }
    }, 1500);
    return () => window.clearTimeout(timeout);
  }, [deferredDraft, record, selectedDocumentKind, language, currentDocumentContent, user?.id]);

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

  function queueResultsScroll() {
    window.setTimeout(() => {
      resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 50);
  }

  function ensureRoleAccess(nextRole: DraftRole) {
    const requirement = draftModes[nextRole].roleRequirement;
    if (requirement === "public") {
      return true;
    }
    if (requirement === "police" && user?.can_access_police_dashboard) {
      return true;
    }
    if (requirement === "lawyer" && user?.can_access_lawyer_dashboard) {
      return true;
    }
    setError(
      requirement === "police"
        ? "Police FIR drafting is available only to approved police accounts."
        : "Lawyer FIR analysis is available only to approved lawyer accounts.",
    );
    return false;
  }

  async function handleManualSubmit(event: FormEvent) {
    event.preventDefault();
    if (!ensureRoleAccess(draftRole)) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = (await api.firManual({
        ...manualForm,
        draft_role: draftRole,
        language,
        accused_details: splitList(manualForm.accused_details),
        witness_details: splitList(manualForm.witness_details),
        evidence_information: splitList(manualForm.evidence_information),
      })) as FIRRecordResponse;
      setPreview(null);
      setVoicePreview(null);
      setRecord(response);
      setSelectedDocumentKind(response.draft_role);
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
    if (!ensureRoleAccess(draftRole)) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = (await api.firManualPreview({
        ...manualForm,
        draft_role: draftRole,
        language,
        accused_details: splitList(manualForm.accused_details),
        witness_details: splitList(manualForm.witness_details),
        evidence_information: splitList(manualForm.evidence_information),
      })) as FIRPreviewResponse;
      setRecord(null);
      setVersions([]);
      setIntelligence(null);
      setVoicePreview(null);
      setPreview(response);
      setSelectedDocumentKind(draftRole);
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
    if (!ensureRoleAccess(draftRole)) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("complaint_file", uploadFile);
      formData.append("police_station", uploadPoliceStation);
      formData.append("draft_role", draftRole);
      formData.append("language", language);
      const response = (await api.firUploadPreview(formData)) as FIRPreviewResponse;
      setRecord(null);
      setVersions([]);
      setIntelligence(null);
      setVoicePreview(null);
      setPreview(response);
      setSelectedDocumentKind(draftRole);
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
    if (!ensureRoleAccess(draftRole)) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("complaint_file", uploadFile);
      formData.append("police_station", uploadPoliceStation);
      formData.append("draft_role", draftRole);
      formData.append("language", language);
      const response = (await api.firUpload(formData)) as FIRRecordResponse;
      setPreview(null);
      setVoicePreview(null);
      setRecord(response);
      setSelectedDocumentKind(response.draft_role);
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
    if (!ensureRoleAccess(draftRole)) {
      return;
    }
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
      formData.append("draft_role", draftRole);
      formData.append("language", language);
      const response = (await api.firVoice(formData)) as FIRRecordResponse;
      setPreview(null);
      setVoicePreview(null);
      setRecord(response);
      setSelectedDocumentKind(response.draft_role);
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

  async function handleVoicePreview() {
    if (!ensureRoleAccess(draftRole)) {
      return;
    }
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
      formData.append("draft_role", draftRole);
      formData.append("language", language);
      const response = (await api.firVoicePreview(formData)) as FIRVoiceProcessingResponse;
      setRecord(null);
      setVersions([]);
      setIntelligence(null);
      setPreview(null);
      setVoicePreview(response);
      setSelectedDocumentKind(draftRole);
      queueResultsScroll();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to preview voice FIR.");
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

  async function handleManualSave() {
    if (!record) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const response = (await api.firUpdateDraft(record.fir_id, {
        draft_text: draftText,
        document_kind: selectedDocumentKind,
        language,
        edited_by: user?.id ?? "manual-review",
        edit_summary: `Manual save for ${selectedDocumentKind}`,
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

  async function handleDownloadPdf() {
    if (!record) {
      setError("Create or save the complaint application before downloading the PDF.");
      return;
    }
    try {
      const blob = await api.firDownloadDocumentPdf(record.fir_id, selectedDocumentKind, language);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${record.fir_id}-${selectedDocumentKind}-${language}.pdf`;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to download the PDF.");
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

  const lockedModeReason =
    draftModes[draftRole].roleRequirement === "police"
      ? "Approved police access is required for police FIR drafting."
      : draftModes[draftRole].roleRequirement === "lawyer"
        ? "Approved lawyer access is required for lawyer FIR analysis."
        : null;

  return (
    <div className="fir-workspace">
      <div className="fir-shell">
        <section className="fir-intake">
          <div className="fir-header">
            <div>
              <p className="eyebrow">Dedicated FIR Studio</p>
              <h2>Citizen, police, and lawyer FIR workflows</h2>
            </div>
            <span className="status-pill">{loading ? "Processing" : saving ? "Saving" : "Ready"}</span>
          </div>

          <div className="fir-workflow-tabs">
            {(Object.entries(draftModes) as [DraftRole, (typeof draftModes)[DraftRole]][]).map(([key, value]) => {
              const locked =
                (value.roleRequirement === "police" && !user?.can_access_police_dashboard) ||
                (value.roleRequirement === "lawyer" && !user?.can_access_lawyer_dashboard);
              return (
                <button
                  key={key}
                  type="button"
                  className={`fir-tab ${draftRole === key ? "active" : ""} ${locked ? "locked" : ""}`}
                  onClick={() => {
                    if (locked) {
                      setError(
                        value.roleRequirement === "police"
                          ? "Approved police access is required for this drafting lane."
                          : "Approved lawyer access is required for this drafting lane.",
                      );
                      return;
                    }
                    setDraftRole(key);
                  }}
                >
                  <strong>{value.title}</strong>
                  <span>{locked ? "Approval required" : value.description}</span>
                </button>
              );
            })}
          </div>

          <div className="two-up">
            <label>
              Draft Language
              <select value={language} onChange={(event) => setLanguage(event.target.value as LanguageKey)}>
                {languageOptions.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Input Mode
              <select value={workflow} onChange={(event) => setWorkflow(event.target.value as WorkflowKey)}>
                {(Object.entries(workflows) as [WorkflowKey, { title: string; description: string }][]).map(([key, value]) => (
                  <option key={key} value={key}>
                    {value.title}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {lockedModeReason && !ensureRolePreviewOnly(draftRole, user) && (
            <div className="preview-card">
              <h3>Approval needed</h3>
              <p>{lockedModeReason}</p>
              <p className="helper-text">
                {isAuthenticated
                  ? user?.approval_notes ?? "Your professional account is still under review."
                  : "Create an account and request the right role to unlock this lane."}
              </p>
            </div>
          )}

          {workflow === "manual" && (
            <form className="fir-form" onSubmit={handleManualSubmit}>
              <div className="two-up">
                <label>
                  Complainant Name
                  <input value={manualForm.complainant_name} onChange={(event) => setManualForm({ ...manualForm, complainant_name: event.target.value })} />
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
                  <input value={manualForm.contact_number} onChange={(event) => setManualForm({ ...manualForm, contact_number: event.target.value })} />
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
                <input value={manualForm.incident_location} onChange={(event) => setManualForm({ ...manualForm, incident_location: event.target.value })} />
              </label>
              <label>
                Incident Description
                <textarea rows={6} value={manualForm.incident_description} onChange={(event) => setManualForm({ ...manualForm, incident_description: event.target.value })} />
              </label>
              <label>
                Accused Details
                <input value={manualForm.accused_details} onChange={(event) => setManualForm({ ...manualForm, accused_details: event.target.value })} />
              </label>
              <label>
                Witness Details
                <input value={manualForm.witness_details} onChange={(event) => setManualForm({ ...manualForm, witness_details: event.target.value })} />
              </label>
              <label>
                Evidence Information
                <input value={manualForm.evidence_information} onChange={(event) => setManualForm({ ...manualForm, evidence_information: event.target.value })} />
              </label>
              <div className="button-row">
                <button className="submit-button" type="submit" disabled={loading}>
                  Save Draft
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
                Complaint Application / FIR Source
                <input type="file" accept=".jpg,.jpeg,.png,.pdf,.doc,.docx" onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} />
              </label>
              <label>
                Police Station
                <input value={uploadPoliceStation} onChange={(event) => setUploadPoliceStation(event.target.value)} />
              </label>
              <p className="helper-text">
                Upload is especially useful for handwritten citizen applications that police officers want to convert into a structured FIR draft.
              </p>
              <div className="button-row">
                <button className="submit-button" type="submit" disabled={loading}>
                  OCR + Preview
                </button>
                <button className="ghost-button" type="button" onClick={handleUploadCreate} disabled={loading || !uploadFile}>
                  Create Saved Draft
                </button>
              </div>
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
                <span className="helper-text">{audioBlob ? "Audio captured and ready." : "Or paste the transcript below."}</span>
              </div>
              <label>
                Voice Transcript
                <textarea rows={6} value={voiceForm.transcript_text} onChange={(event) => setVoiceForm({ ...voiceForm, transcript_text: event.target.value })} />
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
              <div className="button-row">
                <button className="submit-button" type="submit" disabled={loading}>
                  Convert and Save
                </button>
                <button className="ghost-button" type="button" onClick={handleVoicePreview} disabled={loading}>
                  Preview Voice Extraction
                </button>
              </div>
            </form>
          )}

          {error && <div className="error-banner">{error}</div>}
        </section>

        <section className="fir-results">
          <div className="fir-summary-card" ref={resultsRef}>
            <div className="card-header-inline">
              <h3>Structured Complaint Data</h3>
              <span className="status-pill">{preview || voicePreview ? "Preview Loaded" : record ? "Saved Draft" : "Waiting"}</span>
            </div>
            {extractedData ? (
              <dl className="fir-data-list">
                <div><dt>Complainant</dt><dd>{extractedData.complainant_name ?? "Not provided"}</dd></div>
                <div><dt>Police Station</dt><dd>{extractedData.police_station ?? "Not provided"}</dd></div>
                <div><dt>Date / Time</dt><dd>{extractedData.incident_date ?? "Not provided"}{extractedData.incident_time ? ` · ${extractedData.incident_time}` : ""}</dd></div>
                <div><dt>Location</dt><dd>{extractedData.incident_location ?? "Not provided"}</dd></div>
                <div className="fir-data-wide"><dt>Description</dt><dd>{extractedData.incident_description}</dd></div>
                <div><dt>Accused</dt><dd>{extractedData.accused_details.length > 0 ? extractedData.accused_details.join(", ") : "Not provided"}</dd></div>
                <div><dt>Witnesses</dt><dd>{extractedData.witness_details.length > 0 ? extractedData.witness_details.join(", ") : "Not provided"}</dd></div>
                <div><dt>Evidence</dt><dd>{extractedData.evidence_information.length > 0 ? extractedData.evidence_information.join(", ") : "Not provided"}</dd></div>
              </dl>
            ) : (
              <p className="helper-text">Start a preview or save a draft to load the extracted complaint structure.</p>
            )}
          </div>

          <div className="fir-summary-card">
            <h3>Comparative Sections</h3>
            <div className="comparison-grid">
              {renderStatuteColumn("BNS", comparativeSections?.bns ?? [])}
              {renderStatuteColumn("BNSS", comparativeSections?.bnss ?? [])}
              {renderStatuteColumn("IPC", comparativeSections?.ipc ?? [])}
              {renderStatuteColumn("CrPC", comparativeSections?.crpc ?? [])}
            </div>
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
              <li>Confidence: {Math.round((jurisdiction?.confidence ?? 0) * 100)}%</li>
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
          <div>
            <h2>{draftModes[draftRole].title}</h2>
            <p className="helper-text">{draftModes[draftRole].description}</p>
          </div>
          <div className="button-row">
            <span className="status-pill">{record ? `Version ${record.current_version}` : "Preview mode"}</span>
            <button className="ghost-button" type="button" onClick={handleDownloadPdf} disabled={!record || selectedDocumentKind !== "citizen_application"}>
              Download PDF
            </button>
            <button className="ghost-button" type="button" onClick={handleManualSave} disabled={!record || saving}>
              Save Draft
            </button>
          </div>
        </div>

        {generatedDocuments.length > 0 && (
          <div className="fir-workflow-tabs secondary-tabs">
            {generatedDocuments.map((document) => (
              <button
                key={`${document.kind}-${document.language}`}
                type="button"
                className={`fir-tab ${selectedDocumentKind === document.kind ? "active" : ""}`}
                onClick={() => {
                  setSelectedDocumentKind(document.kind);
                  setDraftText(document.content);
                }}
              >
                <strong>{document.title}</strong>
                <span>{document.language.toUpperCase()}</span>
              </button>
            ))}
          </div>
        )}

        <textarea className="fir-draft-editor" rows={18} value={draftText} onChange={(event) => setDraftText(event.target.value)} placeholder="The selected FIR document will appear here." />
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
              Link Evidence
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
          <h3>Edit Log</h3>
          <ul className="version-list">
            {versions.map((item) => (
              <li key={`${item.version_number}-${item.created_at}`}>
                <strong>v{item.version_number}</strong>
                <span>{new Date(item.created_at).toLocaleString()}</span>
                <p>{item.document_kind.replace("_", " ")}</p>
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

function renderStatuteColumn(statute: string, items: FIRSectionSuggestion[]) {
  return (
    <div className="comparison-column" key={statute}>
      <h4>{statute}</h4>
      <ul className="section-list compact-section-list">
        {items.length === 0 ? (
          <li>
            <span>No mapped section yet.</span>
          </li>
        ) : (
          items.map((item) => (
            <li key={`${statute}-${item.section}`}>
              <strong>{item.section}</strong>
              <span>{item.title}</span>
              <p>{item.reasoning}</p>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}

function ensureRolePreviewOnly(
  draftRole: DraftRole,
  user: { can_access_police_dashboard?: boolean; can_access_lawyer_dashboard?: boolean } | null,
) {
  const requirement = draftModes[draftRole].roleRequirement;
  if (requirement === "public") {
    return true;
  }
  if (requirement === "police") {
    return Boolean(user?.can_access_police_dashboard);
  }
  return Boolean(user?.can_access_lawyer_dashboard);
}
