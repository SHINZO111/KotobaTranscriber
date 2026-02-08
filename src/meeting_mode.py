"""
会議モードモジュール
長時間録音最適化・話者識別精度向上のための会議特化機能
"""

import logging
import time
import threading
from pathlib import Path
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
import json
import wave

logger = logging.getLogger(__name__)


@dataclass
class RecordingSegment:
    """録音セグメント情報"""
    index: int
    start_time: float
    end_time: float
    file_path: str
    duration: float
    speakers_detected: List[str] = field(default_factory=list)


@dataclass
class MeetingSession:
    """会議セッション情報"""
    session_id: str
    start_time: float
    title: str = ""
    segments: List[RecordingSegment] = field(default_factory=list)
    speakers: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "title": self.title,
            "segments": [
                {
                    "index": seg.index,
                    "start_time": seg.start_time,
                    "end_time": seg.end_time,
                    "file_path": seg.file_path,
                    "duration": seg.duration,
                    "speakers_detected": seg.speakers_detected
                }
                for seg in self.segments
            ],
            "speakers": self.speakers,
            "metadata": self.metadata
        }


class MeetingModeRecorder:
    """
    会議モード録音クラス
    長時間録音の自動分割・保存を実現
    """

    # デフォルト設定値
    DEFAULT_AUTO_SPLIT_DURATION = 1800   # 30分（秒）
    DEFAULT_AUTO_SAVE_INTERVAL = 300     # 5分（秒）
    DEFAULT_MIN_SPEAKERS = 2
    DEFAULT_MAX_SPEAKERS = 10

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初期化

        Args:
            config: 会議モード設定
        """
        self.config = config or {}

        # 自動分割設定
        self.auto_split_duration = self.config.get('auto_split_duration', self.DEFAULT_AUTO_SPLIT_DURATION)
        self.auto_save_interval = self.config.get('auto_save', {}).get('interval', self.DEFAULT_AUTO_SAVE_INTERVAL)

        # 話者検出設定
        speaker_config = self.config.get('speaker_detection', {})
        self.speaker_detection_enabled = speaker_config.get('enabled', True)
        self.min_speakers = speaker_config.get('min_speakers', self.DEFAULT_MIN_SPEAKERS)
        self.max_speakers = speaker_config.get('max_speakers', self.DEFAULT_MAX_SPEAKERS)

        # 録音状態
        self.is_recording = False
        self.current_session: Optional[MeetingSession] = None
        self.current_segment: Optional[RecordingSegment] = None
        self.segment_index = 0

        # オーディオバッファ
        self.audio_buffer: List[bytes] = []
        self.buffer_lock = threading.Lock()

        # スレッド
        self.recording_thread: Optional[threading.Thread] = None
        self.auto_save_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        # コールバック
        self.on_segment_saved: Optional[Callable[[RecordingSegment], None]] = None
        self.on_auto_save: Optional[Callable[[], None]] = None
        self.on_speaker_detected: Optional[Callable[[str], None]] = None

        # 出力ディレクトリ
        self.output_dir = Path("recordings/meetings")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"MeetingModeRecorder initialized (split: {self.auto_split_duration}s)")

    def start_recording(
        self,
        title: str = "",
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> str:
        """
        録音を開始

        Args:
            title: 会議タイトル
            sample_rate: サンプリングレート
            channels: チャンネル数

        Returns:
            セッションID
        """
        if self.is_recording:
            logger.warning("Recording already in progress")
            return self.current_session.session_id if self.current_session else ""

        # セッション作成
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_session = MeetingSession(
            session_id=session_id,
            start_time=time.time(),
            title=title or f"会議_{session_id}",
            metadata={
                "sample_rate": sample_rate,
                "channels": channels,
                "created_at": datetime.now().isoformat()
            }
        )

        self.segment_index = 0
        self.is_recording = True
        self.stop_event.clear()

        # 最初のセグメントを開始
        self._start_new_segment()

        # 自動保存スレッド開始
        if self.auto_save_interval > 0:
            self.auto_save_thread = threading.Thread(target=self._auto_save_loop)
            self.auto_save_thread.daemon = True
            self.auto_save_thread.start()

        logger.info(f"Started meeting recording: {session_id}")
        return session_id

    def stop_recording(self) -> Optional[MeetingSession]:
        """
        録音を停止

        Returns:
            会議セッション情報
        """
        if not self.is_recording:
            return None

        self.is_recording = False
        self.stop_event.set()

        # 現在のセグメントを保存
        if self.current_segment:
            self._save_current_segment()

        # スレッド終了待ち
        if self.auto_save_thread and self.auto_save_thread.is_alive():
            self.auto_save_thread.join(timeout=5.0)

        # セッションファイルを保存
        session = self.current_session
        if session:
            self._save_session_metadata(session)

        self.current_session = None
        self.current_segment = None
        self.audio_buffer.clear()

        logger.info(f"Stopped meeting recording: {session.session_id if session else 'unknown'}")
        return session

    def write_audio_data(self, audio_data: bytes):
        """
        オーディオデータを書き込み

        Args:
            audio_data: オーディオデータ（bytes）
        """
        if not self.is_recording:
            return

        with self.buffer_lock:
            self.audio_buffer.append(audio_data)

        # セグメント時間をチェック
        if self.current_segment:
            current_duration = time.time() - self.current_segment.start_time
            if current_duration >= self.auto_split_duration:
                self._rotate_segment()

    def _start_new_segment(self):
        """新しいセグメントを開始"""
        if self.current_session is None:
            return
        self.segment_index += 1
        segment_file = self.output_dir / f"{self.current_session.session_id}_seg{self.segment_index:03d}.wav"

        self.current_segment = RecordingSegment(
            index=self.segment_index,
            start_time=time.time(),
            end_time=0.0,
            file_path=str(segment_file),
            duration=0.0
        )

        with self.buffer_lock:
            self.audio_buffer.clear()
        logger.debug(f"Started new segment: {segment_file.name}")

    def _save_current_segment(self) -> bool:
        """
        現在のセグメントを保存

        Returns:
            成功したかどうか
        """
        if not self.current_segment or not self.audio_buffer or self.current_session is None:
            return False

        try:
            with self.buffer_lock:
                audio_data = b"".join(self.audio_buffer)
                self.audio_buffer.clear()

            # WAVファイルとして保存
            segment = self.current_segment
            segment.end_time = time.time()
            segment.duration = segment.end_time - segment.start_time

            sample_rate = self.current_session.metadata.get('sample_rate', 16000)
            channels = self.current_session.metadata.get('channels', 1)

            with wave.open(segment.file_path, 'wb') as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(2)  # 16bit
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data)

            # セッションに追加
            self.current_session.segments.append(segment)

            # コールバック呼び出し
            if self.on_segment_saved:
                try:
                    self.on_segment_saved(segment)
                except Exception as e:
                    logger.error(f"Error in on_segment_saved callback: {e}")

            logger.info(f"Saved segment {segment.index}: {segment.duration:.1f}s")
            return True

        except Exception as e:
            logger.error(f"Failed to save segment: {e}")
            return False

    def _rotate_segment(self):
        """セグメントを切り替え"""
        if self._save_current_segment():
            self._start_new_segment()

    def _auto_save_loop(self):
        """自動保存ループ"""
        while not self.stop_event.is_set():
            self.stop_event.wait(self.auto_save_interval)
            if self.is_recording and self.on_auto_save:
                try:
                    self.on_auto_save()
                except Exception as e:
                    logger.error(f"Error in on_auto_save callback: {e}")

    def _save_session_metadata(self, session: MeetingSession):
        """
        セッションメタデータを保存

        Args:
            session: 会議セッション
        """
        try:
            metadata_file = self.output_dir / f"{session.session_id}_metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info(f"Saved session metadata: {metadata_file}")
        except Exception as e:
            logger.error(f"Failed to save session metadata: {e}")

    def get_current_status(self) -> Dict[str, Any]:
        """
        現在の録音状態を取得

        Returns:
            状態情報
        """
        if not self.is_recording or not self.current_session:
            return {"recording": False}

        total_duration = time.time() - self.current_session.start_time
        current_segment_duration = 0.0
        if self.current_segment:
            current_segment_duration = time.time() - self.current_segment.start_time

        return {
            "recording": True,
            "session_id": self.current_session.session_id,
            "title": self.current_session.title,
            "total_duration": total_duration,
            "segment_count": len(self.current_session.segments),
            "current_segment": self.segment_index,
            "current_segment_duration": current_segment_duration,
            "buffer_size": len(self.audio_buffer)
        }


class MeetingModeProcessor:
    """
    会議モード処理クラス
    会議録音後の処理（書き起こし・議事録生成）を管理
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初期化

        Args:
            config: 処理設定
        """
        self.config = config or {}

        # 話者識別設定（会議向け最適化）
        self.speaker_config = {
            "enabled": self.config.get('speaker_detection', {}).get('enabled', True),
            "min_speakers": self.config.get('speaker_detection', {}).get('min_speakers', 2),
            "max_speakers": self.config.get('speaker_detection', {}).get('max_speakers', 10),
            "clustering_method": "spectral",  # 会議向けにspectralクラスタリングを使用
            "embedding_model": "speechbrain",  # 高精度な埋め込みモデル
        }

        # 進捗コールバック
        self.on_progress: Optional[Callable[[int, int, str], None]] = None

        logger.info("MeetingModeProcessor initialized")

    def process_session(
        self,
        session: MeetingSession,
        generate_minutes: bool = True,
    ) -> Dict[str, Any]:
        """
        会議セッションを処理

        Args:
            session: 会議セッション
            generate_minutes: 議事録を生成するか

        Returns:
            処理結果
        """
        results = {
            "session_id": session.session_id,
            "transcriptions": [],
            "minutes": None,
            "speakers": [],
            "errors": []
        }

        total_segments = len(session.segments)

        # 各セグメントを書き起こし
        for i, segment in enumerate(session.segments):
            try:
                self._report_progress(i, total_segments, f"セグメント {i+1}/{total_segments} を処理中...")

                transcription = self._transcribe_segment(segment)
                if transcription:
                    results["transcriptions"].append(transcription)

            except Exception as e:
                logger.error(f"Failed to process segment {segment.index}: {e}")
                results["errors"].append({"segment": segment.index, "error": str(e)})

        # 話者情報を統合
        results["speakers"] = self._merge_speaker_info(results["transcriptions"])

        # 議事録を生成
        if generate_minutes and results["transcriptions"]:
            try:
                self._report_progress(total_segments, total_segments, "議事録を生成中...")
                results["minutes"] = self._generate_minutes(results["transcriptions"], session)
            except Exception as e:
                logger.error(f"Failed to generate minutes: {e}")
                results["errors"].append({"step": "minutes_generation", "error": str(e)})

        self._report_progress(total_segments, total_segments, "処理完了")
        return results

    def _transcribe_segment(self, segment: RecordingSegment) -> Optional[Dict]:
        """
        セグメントを書き起こし

        Args:
            segment: 録音セグメント

        Returns:
            書き起こし結果
        """
        try:
            from transcription_engine import TranscriptionEngine
            from speaker_diarization_free import FreeSpeakerDiarizer

            # 書き起こし
            engine = TranscriptionEngine()
            engine.load_model()

            result = engine.transcribe(
                segment.file_path,
                return_timestamps=True
            )

            # 話者識別（会議向け設定）
            if result and self.speaker_config.get("enabled", True):
                diarizer = FreeSpeakerDiarizer()
                num_speakers = self.speaker_config.get("max_speakers")
                speaker_segments = diarizer.diarize(
                    segment.file_path,
                    num_speakers=num_speakers
                )
                result["speaker_segments"] = speaker_segments

            return result

        except Exception as e:
            logger.error(f"Transcription failed for {segment.file_path}: {e}")
            return None

    def _merge_speaker_info(self, transcriptions: List[Dict]) -> List[str]:
        """
        複数セグメントの話者情報を統合

        Args:
            transcriptions: 書き起こし結果リスト

        Returns:
            話者リスト
        """
        speakers = set()
        for trans in transcriptions:
            for segment in trans.get("speaker_segments", []):
                speaker = segment.get("speaker")
                if speaker:
                    speakers.add(speaker)
        return sorted(list(speakers))

    def _generate_minutes(
        self,
        transcriptions: List[Dict],
        session: MeetingSession
    ) -> Optional[Dict]:
        """
        議事録を生成

        Args:
            transcriptions: 書き起こし結果リスト
            session: 会議セッション

        Returns:
            議事録データ
        """
        try:
            from meeting_minutes_generator import MeetingMinutesGenerator

            # セグメントを統合
            all_segments = []
            for trans in transcriptions:
                all_segments.extend(trans.get("speaker_segments", []))

            # 時間順にソート
            all_segments.sort(key=lambda x: x.get("start", 0))

            # 議事録生成
            generator = MeetingMinutesGenerator()
            minutes = generator.generate_minutes(
                segments=all_segments,
                title=session.title,
                date=datetime.fromtimestamp(session.start_time).strftime("%Y年%m月%d日 %H:%M"),
            )

            return {
                "text": minutes.to_text(),
                "markdown": minutes.to_markdown(),
                "data": minutes
            }

        except Exception as e:
            logger.error(f"Minutes generation failed: {e}")
            return None

    def _report_progress(self, current: int, total: int, message: str):
        """進捗を報告"""
        if self.on_progress:
            try:
                self.on_progress(current, total, message)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")


# グローバルインスタンス
_meeting_recorder = None
_meeting_processor = None
_meeting_singleton_lock = threading.Lock()


def get_meeting_recorder(config: Optional[Dict[str, Any]] = None) -> MeetingModeRecorder:
    """
    会議モードレコーダーのシングルトンインスタンスを取得

    Args:
        config: 設定辞書

    Returns:
        MeetingModeRecorderインスタンス
    """
    global _meeting_recorder
    if _meeting_recorder is None:
        with _meeting_singleton_lock:
            if _meeting_recorder is None:
                _meeting_recorder = MeetingModeRecorder(config)
    return _meeting_recorder


def get_meeting_processor(config: Optional[Dict[str, Any]] = None) -> MeetingModeProcessor:
    """
    会議モードプロセッサーのシングルトンインスタンスを取得

    Args:
        config: 設定辞書

    Returns:
        MeetingModeProcessorインスタンス
    """
    global _meeting_processor
    if _meeting_processor is None:
        with _meeting_singleton_lock:
            if _meeting_processor is None:
                _meeting_processor = MeetingModeProcessor(config)
    return _meeting_processor


if __name__ == "__main__":
    # テスト用コード
    logging.basicConfig(level=logging.INFO)

    print("=== Meeting Mode Test ===\n")

    # レコーダーテスト
    config = {
        "auto_split_duration": 60,  # 1分で分割（テスト用）
        "auto_save": {"enabled": True, "interval": 10},
        "speaker_detection": {"enabled": True, "min_speakers": 2, "max_speakers": 5}
    }

    recorder = MeetingModeRecorder(config)

    # セッション開始
    session_id = recorder.start_recording(title="テスト会議")
    print(f"Started session: {session_id}")

    # ステータス確認
    status = recorder.get_current_status()
    print(f"Status: {status}")

    # 停止
    time.sleep(1)
    session = recorder.stop_recording()
    if session:
        print(f"\nSession completed:")
        print(f"  - Segments: {len(session.segments)}")
        print(f"  - Duration: {time.time() - session.start_time:.1f}s")

    print("\n=== Meeting Mode Test Complete ===")
