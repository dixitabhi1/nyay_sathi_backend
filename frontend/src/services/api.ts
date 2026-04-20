const API_BASE = import.meta.env.VITE_API_URL ?? "/api/v1";
const AUTH_TOKEN_STORAGE_KEY = "nyayasetu.auth.token";
const DEFAULT_REQUEST_TIMEOUT_MS = 20000;
const AUTH_REQUEST_TIMEOUT_MS = 12000;
const UPLOAD_REQUEST_TIMEOUT_MS = 45000;

let authToken: string | null =
  typeof window !== "undefined" ? window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) : null;
let unauthorizedHandler: (() => void) | null = null;

type RequestMethod = "GET" | "POST" | "PUT";
type RequestOptions = {
  timeoutMs?: number;
};

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

async function fetchWithTimeout(input: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = globalThis.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("The server is taking too long to respond. Please retry in a moment.");
    }
    throw error;
  } finally {
    globalThis.clearTimeout(timeoutId);
  }
}

async function requestJson<T>(path: string, method: RequestMethod, payload?: unknown, options: RequestOptions = {}): Promise<T> {
  const response = await fetchWithTimeout(`${API_BASE}${path}`, {
    method,
    headers: buildHeaders(payload instanceof FormData ? undefined : "application/json"),
    body:
      payload === undefined
        ? undefined
        : payload instanceof FormData
          ? payload
          : JSON.stringify(payload),
  }, options.timeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS);

  if (!response.ok) {
    if (response.status === 401 && path !== "/auth/login" && path !== "/auth/register") {
      setApiAuthToken(null);
      unauthorizedHandler?.();
    }
    throw new Error(await extractError(response));
  }

  return response.json() as Promise<T>;
}

async function requestBlob(path: string, options: RequestOptions = {}): Promise<Blob> {
  const response = await fetchWithTimeout(`${API_BASE}${path}`, {
    method: "GET",
    headers: buildHeaders(),
  }, options.timeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS);

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

export function setApiUnauthorizedHandler(handler: (() => void) | null) {
  unauthorizedHandler = handler;
}

export const api = {
  chat: (question: string) => requestJson("/chat/query", "POST", { question, language: "en" }),
  caseAnalysis: (payload: unknown) => requestJson("/analysis/case", "POST", payload),
  research: (query: string) => requestJson("/research/search", "POST", { query, top_k: 5 }, { timeoutMs: 30000 }),
  draft: (payload: unknown) => requestJson("/analysis/draft", "POST", payload),
  analyzeContract: (formData: FormData) =>
    requestJson("/documents/contract/analyze", "POST", formData, { timeoutMs: UPLOAD_REQUEST_TIMEOUT_MS }),
  analyzeEvidence: (formData: FormData) =>
    requestJson("/documents/evidence/analyze", "POST", formData, { timeoutMs: UPLOAD_REQUEST_TIMEOUT_MS }),
  fir: (payload: unknown) => requestJson("/analysis/fir", "POST", payload, { timeoutMs: 30000 }),
  strength: (payload: unknown) => requestJson("/analysis/strength", "POST", payload),
  firManualPreview: (payload: unknown) => requestJson("/fir/manual/preview", "POST", payload, { timeoutMs: 30000 }),
  firManual: (payload: unknown) => requestJson("/fir/manual", "POST", payload, { timeoutMs: 30000 }),
  firUploadPreview: (formData: FormData) => requestJson("/fir/upload/preview", "POST", formData, { timeoutMs: UPLOAD_REQUEST_TIMEOUT_MS }),
  firUpload: (formData: FormData) => requestJson("/fir/upload", "POST", formData, { timeoutMs: UPLOAD_REQUEST_TIMEOUT_MS }),
  firVoice: (formData: FormData) => requestJson("/fir/voice", "POST", formData, { timeoutMs: UPLOAD_REQUEST_TIMEOUT_MS }),
  firVoicePreview: (formData: FormData) => requestJson("/fir/voice/preview", "POST", formData, { timeoutMs: UPLOAD_REQUEST_TIMEOUT_MS }),
  firPredictSections: (payload: unknown) => requestJson("/fir/sections/predict", "POST", payload),
  firSuggestJurisdiction: (payload: unknown) => requestJson("/fir/jurisdiction", "POST", payload),
  firCompleteness: (payload: unknown) => requestJson("/fir/completeness", "POST", payload),
  firGet: (firId: string) => requestJson(`/fir/${firId}`, "GET"),
  firIntelligence: (firId: string) => requestJson(`/fir/${firId}/intelligence`, "GET", undefined, { timeoutMs: 30000 }),
  firUpdateDraft: (firId: string, payload: unknown) => requestJson(`/fir/${firId}/draft`, "PUT", payload, { timeoutMs: 30000 }),
  firVersions: (firId: string) => requestJson(`/fir/${firId}/versions`, "GET"),
  firUploadEvidence: (firId: string, formData: FormData) =>
    requestJson(`/fir/${firId}/evidence`, "POST", formData, { timeoutMs: UPLOAD_REQUEST_TIMEOUT_MS }),
  firAnalyzeEvidence: (formData: FormData) => requestJson("/fir/evidence/analyze", "POST", formData, { timeoutMs: UPLOAD_REQUEST_TIMEOUT_MS }),
  firCrimePatterns: (windowDays = 7) => requestJson(`/fir/analytics/patterns?window_days=${windowDays}`, "GET"),
  firDownloadDocumentPdf: (firId: string, documentKind: string, language = "en") =>
    requestBlob(`/fir/${firId}/documents/${documentKind}.pdf?language=${encodeURIComponent(language)}`, { timeoutMs: 30000 }),
  authRegister: (payload: unknown) => requestJson("/auth/register", "POST", payload, { timeoutMs: AUTH_REQUEST_TIMEOUT_MS }),
  authLogin: (payload: unknown) => requestJson("/auth/login", "POST", payload, { timeoutMs: AUTH_REQUEST_TIMEOUT_MS }),
  authMe: () => requestJson("/auth/me", "GET", undefined, { timeoutMs: 8000 }),
  authLogout: () => requestJson("/auth/logout", "POST", undefined, { timeoutMs: 8000 }),
};
