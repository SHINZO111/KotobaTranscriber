// KotobaTranscriber Svelte stores (state management)

import { writable, derived } from "svelte/store";
import type {
  Route,
  Settings,
  Segment,
  RealtimeStatus,
  MonitorStatus,
  Toast,
  ToastType,
} from "./types";

// --- Routing ---
export const currentRoute = writable<Route>("transcribe");

// --- Theme ---
export const theme = writable<"light" | "dark">("dark");

// Apply theme to DOM on change
theme.subscribe((value) => {
  if (typeof document !== "undefined") {
    document.documentElement.setAttribute("data-theme", value);
  }
});

// --- Sidebar ---
export const sidebarCollapsed = writable(false);

// --- Connection state ---
export const apiConnected = writable(false);
export const wsConnected = writable(false);

// --- Settings ---
export const settings = writable<Settings>({});

// --- Transcription state ---
export const isTranscribing = writable(false);
export const transcriptionProgress = writable(0);
export const transcriptionResult = writable("");
export const transcriptionSegments = writable<Segment[]>([]);
export const transcriptionError = writable<string | null>(null);

// --- Batch processing state ---
export const isBatchProcessing = writable(false);
export const batchProgress = writable({ completed: 0, total: 0, filename: "" });
export const batchResults = writable<
  Array<{ file_path: string; text: string; success: boolean }>
>([]);

// --- Realtime state ---
export const realtimeStatus = writable<RealtimeStatus>({
  is_running: false,
  is_paused: false,
  model_size: null,
});
export const realtimeText = writable("");
export const realtimeVolume = writable(0);

// --- Folder monitor state ---
export const monitorStatus = writable<MonitorStatus>({
  is_running: false,
  folder_path: null,
  check_interval: 10,
  total_processed: 0,
  total_failed: 0,
});

// --- Derived stores ---
export const isProcessing = derived(
  [isTranscribing, isBatchProcessing],
  ([$isTranscribing, $isBatchProcessing]) =>
    $isTranscribing || $isBatchProcessing
);

// --- Toast notifications ---
export const toasts = writable<Toast[]>([]);

let toastCounter = 0;
const MAX_TOASTS = 8;

export function addToast(type: ToastType, message: string, duration = 4000) {
  const id = `toast-${++toastCounter}-${Date.now()}`;
  const toast: Toast = { id, type, message, duration };

  toasts.update((all) => {
    const updated = [...all, toast];
    // Evict oldest toasts if over limit
    return updated.length > MAX_TOASTS ? updated.slice(-MAX_TOASTS) : updated;
  });

  if (duration > 0) {
    setTimeout(() => {
      removeToast(id);
    }, duration);
  }

  return id;
}

export function removeToast(id: string) {
  toasts.update((all) => all.filter((t) => t.id !== id));
}
