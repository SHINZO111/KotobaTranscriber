// KotobaTranscriber TypeScript type definitions

export interface Segment {
  text: string;
  start: number;
  end: number;
  speaker?: string;
}

export interface TranscribeRequest {
  file_path: string;
  enable_diarization: boolean;
  remove_fillers: boolean;
  add_punctuation: boolean;
  format_paragraphs: boolean;
  use_llm_correction: boolean;
}

export interface TranscribeResponse {
  text: string;
  segments: Segment[];
  duration: number | null;
}

export interface BatchTranscribeRequest {
  file_paths: string[];
  enable_diarization: boolean;
  max_workers: number;
  remove_fillers: boolean;
  add_punctuation: boolean;
}

export interface RealtimeControlRequest {
  model_size: string;
  device: string;
  buffer_duration: number;
  vad_threshold: number;
}

export interface RealtimeStatus {
  is_running: boolean;
  is_paused: boolean;
  model_size: string | null;
}

export interface MonitorRequest {
  folder_path: string;
  check_interval: number;
  enable_diarization: boolean;
  auto_move: boolean;
  completed_folder: string | null;
}

export interface MonitorStatus {
  is_running: boolean;
  folder_path: string | null;
  check_interval: number;
  total_processed: number;
  total_failed: number;
}

export interface ExportRequest {
  text: string;
  segments: Segment[];
  output_path: string;
  format: string;
  include_timestamps: boolean;
  include_speakers: boolean;
}

export interface BatchTranscribeResponse {
  message: string;
  total_files: number;
}

export interface ExportResponse {
  success: boolean;
  output_path: string;
  message: string;
}

export interface FormatTextRequest {
  text: string;
  remove_fillers: boolean;
  add_punctuation: boolean;
  format_paragraphs: boolean;
  clean_repeated: boolean;
}

export interface CorrectTextRequest {
  text: string;
  provider: string;
}

export interface DiarizeRequest {
  file_path: string;
  segments: Segment[];
}

export interface ConfigModel {
  model?: Record<string, unknown>;
  audio?: Record<string, unknown>;
  output?: Record<string, unknown>;
}

export interface MessageResponse {
  message: string;
}

export interface Settings {
  theme?: string;
  language?: string;
  output_directory?: string;
  enable_diarization?: boolean;
  remove_fillers?: boolean;
  add_punctuation?: boolean;
  format_paragraphs?: boolean;
  use_llm_correction?: boolean;
  model_size?: string;
  device?: string;
  [key: string]: unknown;
}

export interface HealthResponse {
  status: string;
  version: string;
  engines: Record<string, boolean>;
}

export interface ModelInfo {
  engine: string;
  is_loaded: boolean;
  model_name: string | null;
  device: string | null;
}

// WebSocket event types
export interface WsEvent {
  type: string;
  data: Record<string, unknown>;
  timestamp?: number;
}

export interface ProgressEventData {
  value: number;
}

export interface FinishedEventData {
  text: string;
}

export interface ErrorEventData {
  message: string;
}

export interface BatchProgressEventData {
  completed: number;
  total: number;
  filename: string;
}

export interface FileFinishedEventData {
  file_path: string;
  text: string;
  success: boolean;
}

export interface AllFinishedEventData {
  success_count: number;
  failed_count: number;
}

export interface TextReadyEventData {
  text: string;
}

export interface VolumeChangedEventData {
  level: number;
}

export interface NewFilesDetectedEventData {
  files: string[];
}

/** @deprecated Use ProgressEventData instead */
export type ProgressEvent = ProgressEventData;
/** @deprecated Use BatchProgressEventData instead */
export type BatchProgressEvent = BatchProgressEventData;
/** @deprecated Use FileFinishedEventData instead */
export type FileFinishedEvent = FileFinishedEventData;
/** @deprecated Use AllFinishedEventData instead */
export type AllFinishedEvent = AllFinishedEventData;

export type Route =
  | "transcribe"
  | "batch"
  | "realtime"
  | "monitor"
  | "settings";

// Toast notification types
export type ToastType = "success" | "error" | "warning" | "info";

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
  duration?: number;
}
