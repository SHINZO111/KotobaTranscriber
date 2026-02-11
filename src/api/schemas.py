"""
Pydantic モデル定義
FastAPI のリクエスト/レスポンススキーマ。
"""

from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field


# --- Transcription ---

class TranscribeRequest(BaseModel):
    """単一ファイル文字起こしリクエスト"""
    file_path: str = Field(..., description="音声/動画ファイルパス")
    enable_diarization: bool = Field(False, description="話者分離を有効にする")
    remove_fillers: bool = Field(True, description="フィラー除去")
    add_punctuation: bool = Field(True, description="句読点付与")
    format_paragraphs: bool = Field(True, description="段落整形")
    use_llm_correction: bool = Field(False, description="LLM補正を使用")


class TranscribeResponse(BaseModel):
    """文字起こし結果"""
    text: str = Field("", description="文字起こしテキスト")
    segments: List[Dict[str, Any]] = Field(default_factory=list, description="セグメント情報")
    duration: Optional[float] = Field(None, description="処理時間（秒）")


class BatchTranscribeRequest(BaseModel):
    """バッチ文字起こしリクエスト"""
    file_paths: List[str] = Field(..., max_length=100, description="音声/動画ファイルパスリスト")
    enable_diarization: bool = Field(False, description="話者分離を有効にする")
    max_workers: int = Field(1, ge=1, le=1, description="ワーカー数（エンジン排他のため常に1）")
    remove_fillers: bool = Field(True, description="フィラー除去")
    add_punctuation: bool = Field(True, description="句読点付与")


class BatchTranscribeResponse(BaseModel):
    """バッチ文字起こし開始応答"""
    message: str = "バッチ処理を開始しました"
    total_files: int = Field(..., description="総ファイル数")


# --- Realtime ---

class RealtimeControlRequest(BaseModel):
    """リアルタイム文字起こし制御リクエスト"""
    model_size: Literal["tiny", "base", "small", "medium", "large-v3"] = Field("base", description="モデルサイズ")
    device: str = Field("auto", description="デバイス (auto/cpu/cuda)")
    buffer_duration: float = Field(3.0, ge=1.0, le=10.0, description="バッファ時間（秒）")
    vad_threshold: float = Field(0.5, ge=0.0, le=1.0, description="VAD閾値")


class RealtimeStatusResponse(BaseModel):
    """リアルタイム文字起こし状態"""
    is_running: bool = False
    is_paused: bool = False
    model_size: Optional[str] = None


# --- Models ---

class ModelInfoResponse(BaseModel):
    """モデル情報"""
    engine: str
    is_loaded: bool = False
    model_name: Optional[str] = None
    device: Optional[str] = None


# --- Post-processing ---

class FormatTextRequest(BaseModel):
    """テキストフォーマットリクエスト"""
    text: str = Field(..., max_length=1_000_000, description="フォーマット対象テキスト")
    remove_fillers: bool = Field(True)
    add_punctuation: bool = Field(True)
    format_paragraphs: bool = Field(True)
    clean_repeated: bool = Field(True)


class CorrectTextRequest(BaseModel):
    """テキスト補正リクエスト"""
    text: str = Field(..., max_length=1_000_000, description="補正対象テキスト")
    provider: Literal["local", "claude", "openai"] = Field("local", description="補正プロバイダー")


class DiarizeRequest(BaseModel):
    """話者分離リクエスト"""
    file_path: str = Field(..., description="音声ファイルパス")
    segments: List[Dict[str, Any]] = Field(default_factory=list, max_length=100_000, description="文字起こしセグメント")


# --- Settings ---

class SettingsModel(BaseModel):
    """アプリケーション設定"""
    theme: Optional[str] = None
    language: Optional[str] = None
    output_directory: Optional[str] = None
    enable_diarization: Optional[bool] = None
    remove_fillers: Optional[bool] = None
    add_punctuation: Optional[bool] = None
    format_paragraphs: Optional[bool] = None
    use_llm_correction: Optional[bool] = None
    model_size: Optional[str] = None
    device: Optional[str] = None


class ConfigModel(BaseModel):
    """システム設定（config.yaml）"""
    model: Optional[Dict[str, Any]] = None
    audio: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None


# --- Export ---

class ExportRequest(BaseModel):
    """エクスポートリクエスト"""
    text: str = Field(..., max_length=10_000_000, description="エクスポート対象テキスト")
    segments: List[Dict[str, Any]] = Field(default_factory=list, max_length=100_000, description="セグメント情報")
    output_path: str = Field(..., description="出力ファイルパス")
    format: Literal["txt", "docx", "xlsx", "srt", "vtt", "json"] = Field("txt", description="出力フォーマット")
    include_timestamps: bool = Field(True, description="タイムスタンプを含める")
    include_speakers: bool = Field(False, description="話者情報を含める")


class ExportResponse(BaseModel):
    """エクスポート結果"""
    success: bool = True
    output_path: str = ""
    message: str = ""


# --- Monitor ---

class MonitorRequest(BaseModel):
    """フォルダ監視リクエスト"""
    folder_path: str = Field(..., description="監視フォルダパス")
    check_interval: int = Field(10, ge=5, le=60, description="チェック間隔（秒）")
    enable_diarization: bool = Field(False, description="話者分離を有効にする")
    auto_move: bool = Field(False, description="完了ファイルを自動移動")
    completed_folder: Optional[str] = Field(None, description="完了フォルダパス")


class MonitorStatusResponse(BaseModel):
    """フォルダ監視状態"""
    is_running: bool = False
    folder_path: Optional[str] = None
    check_interval: int = 10
    total_processed: int = 0
    total_failed: int = 0


# --- Common ---

class MessageResponse(BaseModel):
    """汎用メッセージ応答"""
    message: str = ""


# --- Health ---

class HealthResponse(BaseModel):
    """ヘルスチェック応答"""
    status: str = "ok"
    version: str = "2.2"
    engines: Dict[str, bool] = Field(default_factory=dict)
