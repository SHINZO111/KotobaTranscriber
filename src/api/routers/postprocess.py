"""後処理ルーター（テキストフォーマット、話者分離、テキスト補正）"""

import asyncio
import logging
import os

from fastapi import APIRouter, HTTPException

from api.dependencies import get_text_formatter
from api.schemas import CorrectTextRequest, DiarizeRequest, FormatTextRequest
from validators import ValidationError, Validator

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/format-text")
async def format_text(req: FormatTextRequest):
    """テキストをフォーマット（CPU-bound のためスレッドプールで実行）"""
    formatter = get_text_formatter()
    try:

        def _run_format():
            return formatter.format_all(
                req.text,
                remove_fillers=req.remove_fillers,
                add_punctuation=req.add_punctuation,
                format_paragraphs=req.format_paragraphs,
                clean_repeated=req.clean_repeated,
            )

        result = await asyncio.to_thread(_run_format)
        return {"text": result}
    except Exception as e:
        logger.error(f"Format text failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="テキストフォーマット中にエラーが発生しました")


@router.post("/diarize")
async def diarize(req: DiarizeRequest):
    """話者分離を実行（スレッドプールで非同期実行）"""
    if not os.path.isfile(req.file_path):
        raise HTTPException(status_code=404, detail="指定されたファイルが見つかりません")

    try:
        Validator.validate_file_path(req.file_path, must_exist=True)
    except ValidationError:
        raise HTTPException(status_code=400, detail="ファイルパスが不正です")

    try:
        from speaker_diarization_free import FreeSpeakerDiarizer

        def _run_diarization():
            diarizer = FreeSpeakerDiarizer()
            diar_segments = diarizer.diarize(req.file_path)
            text = ""
            if req.segments:
                text = diarizer.format_with_speakers(req.segments, diar_segments)
            stats = diarizer.get_speaker_statistics(diar_segments)
            return text, diar_segments, stats

        text, diar_segments, stats = await asyncio.to_thread(_run_diarization)
        return {
            "text": text,
            "diarization_segments": diar_segments,
            "statistics": stats,
        }
    except ImportError:
        raise HTTPException(status_code=501, detail="話者分離ライブラリがインストールされていません")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Diarization failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="話者分離処理中にエラーが発生しました")


@router.post("/correct-text")
async def correct_text(req: CorrectTextRequest):
    """テキストを補正（スレッドプールで非同期実行）"""
    # provider マッピング: API 層では "claude"/"openai"/"local" を受け付ける
    valid_providers = ("local", "claude", "openai")
    if req.provider not in valid_providers:
        raise HTTPException(status_code=400, detail="不明なプロバイダーです")

    try:

        def _run_correction():
            if req.provider == "local":
                from llm_corrector_standalone import StandaloneLLMCorrector

                corrector = StandaloneLLMCorrector()
                return corrector.correct_text(req.text)
            else:
                # api_corrector の create_corrector は "claude"/"openai" を受け付ける
                # ただし APIProvider enum は "anthropic" なので直接クラスを使う
                from api_corrector import APIProvider, ClaudeCorrector, CorrectionConfig, OpenAICorrector

                provider_map = {
                    "claude": (ClaudeCorrector, APIProvider.ANTHROPIC),
                    "openai": (OpenAICorrector, APIProvider.OPENAI),
                }
                cls, api_provider = provider_map[req.provider]
                # api_key は環境変数から取得、model は空文字（Corrector が DEFAULT_MODEL にフォールバック）
                env_key_map = {
                    "claude": "ANTHROPIC_API_KEY",
                    "openai": "OPENAI_API_KEY",
                }
                api_key = os.environ.get(env_key_map[req.provider], "")
                if not api_key:
                    raise HTTPException(
                        status_code=400,
                        detail="APIキーが設定されていません",
                    )
                config = CorrectionConfig(provider=api_provider, api_key=api_key, model="")
                corrector = cls(config)
                return corrector.correct_text(req.text)

        result = await asyncio.to_thread(_run_correction)
        return {"text": result}

    except ImportError:
        raise HTTPException(status_code=501, detail="補正ライブラリがインストールされていません")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Text correction failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="テキスト補正処理中にエラーが発生しました")
