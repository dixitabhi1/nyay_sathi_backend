const API_BASE = import.meta.env.VITE_API_URL ?? "/api/v1";
const AUTH_TOKEN_STORAGE_KEY = "nyayasetu.auth.token";

let authToken: string | null =
  typeof window !== "undefined" ? window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) : null;

type RequestMethod = "GET" | "POST" | "PUT";

function buildHeaders(contentType?: string): HeadersInit {
  const headers: Record<string, string> = {};
  if (contentType) {
    headers["Content-Type"] = contentType;
  }
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }
  return headers;
}

async function requestJson<T>(path: string, method: RequestMethod, payload?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: buildHeaders(payload instanceof FormData ? undefined : "application/json"),
    body:
      payload === undefined
        ? undefined
        : payload instanceof FormData
          ? payload
          : JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await extractError(response));
  }

  return response.json() as Promise<T>;
}

async function requestBlob(path: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    headers: buildHeaders(),
  });

  if (!response.ok) {
    throw new Error(await extractError(response));
  }

  return response.blob();
}

async function extractError(response: Response): Promise<string> {
  try {
    const payload = (await response.clone().json()) as { detail?: string };
    const detail = payload.detail ?? "";
    if (/<!doctype html|<html/i.test(detail)) {
      return "Backend received an HTML page instead of JSON. Check the deployed API / inference URL configuration.";
    }
    return detail || `API request failed with status ${response.status}`;
  } catch {
    const text = await response.text().catch(() => "");
    if (/<!doctype html|<html/i.test(text)) {
      return "Backend returned HTML instead of JSON. The frontend may be pointed at the wrong backend URL.";
    }
    return text || `API request failed with status ${response.status}`;
  }
}

export function setApiAuthToken(token: string | null) {
  authToken = token;
  if (typeof window === "undefined") {
    return;
  }
  if (token) {
    window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
  } else {
    window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
  }
}

export function getApiAuthToken() {
  return authToken;
}

export const api = {
  chat: (question: string) => requestJson("/chat/query", "POST", { question, language: "en" }),
  caseAnalysis: (payload: unknown) => requestJson("/analysis/case", "POST", payload),
  research: (query: string) => requestJson("/research/search", "POST", { query, top_k: 5 }),
  draft: (payload: unknown) => requestJson("/analysis/draft", "POST", payload),
  analyzeContract: (formData: FormData) => requestJson("/documents/contract/analyze", "POST", formData),
  analyzeEvidence: (formData: FormData) => requestJson("/documents/evidence/analyze", "POST", formData),
  fir: (payload: unknown) => requestJson("/analysis/fir", "POST", payload),
  strength: (payload: unknown) => requestJson("/analysis/strength", "POST", payload),
  firManualPreview: (payload: unknown) => requestJson("/fir/manual/preview", "POST", payload),
  firManual: (payload: unknown) => requestJson("/fir/manual", "POST", payload),
  firUploadPreview: (formData: FormData) => requestJson("/fir/upload/preview", "POST", formData),
  firUpload: (formData: FormData) => requestJson("/fir/upload", "POST", formData),
  firVoice: (formData: FormData) => requestJson("/fir/voice", "POST", formData),
  firVoicePreview: (formData: FormData) => requestJson("/fir/voice/preview", "POST", formData),
  firPredictSections: (payload: unknown) => requestJson("/fir/sections/predict", "POST", payload),
  firSuggestJurisdiction: (payload: unknown) => requestJson("/fir/jurisdiction", "POST", payload),
  firCompleteness: (payload: unknown) => requestJson("/fir/completeness", "POST", payload),
  firGet: (firId: string) => requestJson(`/fir/${firId}`, "GET"),
  firIntelligence: (firId: string) => requestJson(`/fir/${firId}/intelligence`, "GET"),
  firUpdateDraft: (firId: string, payload: unknown) => requestJson(`/fir/${firId}/draft`, "PUT", payload),
  firVersions: (firId: string) => requestJson(`/fir/${firId}/versions`, "GET"),
  firUploadEvidence: (firId: string, formData: FormData) => requestJson(`/fir/${firId}/evidence`, "POST", formData),
  firAnalyzeEvidence: (formData: FormData) => requestJson("/fir/evidence/analyze", "POST", formData),
  firCrimePatterns: (windowDays = 7) => requestJson(`/fir/analytics/patterns?window_days=${windowDays}`, "GET"),
  firDownloadDocumentPdf: (firId: string, documentKind: string, language = "en") =>
    requestBlob(`/fir/${firId}/documents/${documentKind}.pdf?language=${encodeURIComponent(language)}`),
  authRegister: (payload: unknown) => requestJson("/auth/register", "POST", payload),
  authLogin: (payload: unknown) => requestJson("/auth/login", "POST", payload),
  authMe: () => requestJson("/auth/me", "GET"),
  authLogout: () => requestJson("/auth/logout", "POST"),
};
