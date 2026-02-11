// KotobaTranscriber REST API client

import type {
  TranscribeRequest,
  TranscribeResponse,
  BatchTranscribeRequest,
  RealtimeControlRequest,
  RealtimeStatus,
  MonitorRequest,
  MonitorStatus,
  ExportRequest,
  Settings,
  HealthResponse,
  ModelInfo,
} from "./types";

let baseUrl = "http://127.0.0.1:8000";
let apiToken = "";

/** Set the API base URL */
export function setBaseUrl(url: string) {
  baseUrl = url;
}

/** Get the current API base URL */
export function getBaseUrl(): string {
  return baseUrl;
}

/** Set the API authentication token */
export function setApiToken(token: string) {
  apiToken = token;
}

/** Get the current API token */
export function getApiToken(): string {
  return apiToken;
}

/** Generic request helper with error handling */
async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${baseUrl}${path}`;
  const { headers: customHeaders, ...restOptions } = options;
  const authHeaders: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (apiToken) {
    authHeaders["Authorization"] = `Bearer ${apiToken}`;
  }

  const res = await fetch(url, {
    headers: {
      ...authHeaders,
      ...(customHeaders instanceof Headers
        ? Object.fromEntries(customHeaders.entries())
        : Array.isArray(customHeaders)
          ? Object.fromEntries(customHeaders)
          : customHeaders ?? {}),
    },
    ...restOptions,
  });

  if (!res.ok) {
    const body = await res.text();
    let detail = body;
    try {
      const json = JSON.parse(body);
      detail = json.detail || body;
    } catch {
      // keep raw body
    }
    throw new Error(`API Error ${res.status}: ${detail}`);
  }

  return res.json();
}

// --- Health ---

export async function getHealth(): Promise<HealthResponse> {
  return request("/api/health");
}

// --- Transcription ---

export async function transcribe(
  req: TranscribeRequest
): Promise<TranscribeResponse> {
  return request("/api/transcribe", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function batchTranscribe(req: BatchTranscribeRequest): Promise<void> {
  return request("/api/batch-transcribe", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function cancelTranscription(): Promise<void> {
  return request("/api/cancel-transcription", { method: "POST" });
}

export async function cancelBatch(): Promise<void> {
  return request("/api/cancel-batch", { method: "POST" });
}

// --- Realtime ---

export async function startRealtime(req: RealtimeControlRequest): Promise<void> {
  return request("/api/realtime/start", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function stopRealtime(): Promise<void> {
  return request("/api/realtime/stop", { method: "POST" });
}

export async function pauseRealtime(): Promise<void> {
  return request("/api/realtime/pause", { method: "POST" });
}

export async function resumeRealtime(): Promise<void> {
  return request("/api/realtime/resume", { method: "POST" });
}

export async function getRealtimeStatus(): Promise<RealtimeStatus> {
  return request("/api/realtime/status");
}

// --- Models ---

export async function loadModel(engine: string): Promise<void> {
  return request(`/api/models/${encodeURIComponent(engine)}/load`, { method: "POST" });
}

export async function unloadModel(engine: string): Promise<void> {
  return request(`/api/models/${encodeURIComponent(engine)}/unload`, { method: "POST" });
}

export async function getModelInfo(engine: string): Promise<ModelInfo> {
  return request(`/api/models/${encodeURIComponent(engine)}/info`);
}

// --- Post-processing ---

export async function formatText(text: string, options?: Partial<{
  remove_fillers: boolean;
  add_punctuation: boolean;
  format_paragraphs: boolean;
  clean_repeated: boolean;
}>) {
  return request<{ text: string }>("/api/format-text", {
    method: "POST",
    body: JSON.stringify({ text, ...options }),
  });
}

export async function correctText(text: string, provider: string = "local") {
  return request<{ text: string }>("/api/correct-text", {
    method: "POST",
    body: JSON.stringify({ text, provider }),
  });
}

// --- Settings ---

export async function getSettings(): Promise<Settings> {
  return request("/api/settings");
}

export async function updateSettings(updates: Partial<Settings>): Promise<Settings> {
  return request("/api/settings", {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

export async function getConfig(): Promise<Record<string, unknown>> {
  return request("/api/config");
}

export async function updateConfig(updates: Record<string, unknown>): Promise<Record<string, unknown>> {
  return request("/api/config", {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

// --- Monitor ---

export async function startMonitor(req: MonitorRequest): Promise<void> {
  return request("/api/monitor/start", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function stopMonitor(): Promise<void> {
  return request("/api/monitor/stop", { method: "POST" });
}

export async function getMonitorStatus(): Promise<MonitorStatus> {
  return request("/api/monitor/status");
}

// --- Export ---

export async function exportFile(format: string, req: ExportRequest): Promise<{ path: string }> {
  return request(`/api/export/${encodeURIComponent(format)}`, {
    method: "POST",
    body: JSON.stringify(req),
  });
}
