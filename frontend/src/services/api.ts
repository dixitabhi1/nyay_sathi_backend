const API_BASE = import.meta.env.VITE_API_URL ?? "/api/v1";

async function postJson<T>(path: string, payload: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`API request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

async function putJson<T>(path: string, payload: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`API request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

async function postForm<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`API request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);

  if (!response.ok) {
    throw new Error(`API request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  chat: (question: string) => postJson("/chat/query", { question, language: "en" }),
  caseAnalysis: (payload: unknown) => postJson("/analysis/case", payload),
  research: (query: string) => postJson("/research/search", { query, top_k: 5 }),
  draft: (payload: unknown) => postJson("/analysis/draft", payload),
  analyzeContract: (formData: FormData) => postForm("/documents/contract/analyze", formData),
  analyzeEvidence: (formData: FormData) => postForm("/documents/evidence/analyze", formData),
  fir: (payload: unknown) => postJson("/analysis/fir", payload),
  strength: (payload: unknown) => postJson("/analysis/strength", payload),
  firManualPreview: (payload: unknown) => postJson("/fir/manual/preview", payload),
  firManual: (payload: unknown) => postJson("/fir/manual", payload),
  firUploadPreview: (formData: FormData) => postForm("/fir/upload/preview", formData),
  firUpload: (formData: FormData) => postForm("/fir/upload", formData),
  firVoice: (formData: FormData) => postForm("/fir/voice", formData),
  firVoicePreview: (formData: FormData) => postForm("/fir/voice/preview", formData),
  firPredictSections: (payload: unknown) => postJson("/fir/sections/predict", payload),
  firSuggestJurisdiction: (payload: unknown) => postJson("/fir/jurisdiction", payload),
  firCompleteness: (payload: unknown) => postJson("/fir/completeness", payload),
  firGet: (firId: string) => getJson(`/fir/${firId}`),
  firIntelligence: (firId: string) => getJson(`/fir/${firId}/intelligence`),
  firUpdateDraft: (firId: string, payload: unknown) => putJson(`/fir/${firId}/draft`, payload),
  firVersions: (firId: string) => getJson(`/fir/${firId}/versions`),
  firUploadEvidence: (firId: string, formData: FormData) => postForm(`/fir/${firId}/evidence`, formData),
  firAnalyzeEvidence: (formData: FormData) => postForm("/fir/evidence/analyze", formData),
  firCrimePatterns: (windowDays = 7) => getJson(`/fir/analytics/patterns?window_days=${windowDays}`),
};
