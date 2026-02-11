"""エクスポートルーター"""

import asyncio
import logging
import os

from fastapi import APIRouter, HTTPException

from api.schemas import ExportRequest, ExportResponse
from validators import Validator, ValidationError

logger = logging.getLogger(__name__)
router = APIRouter()

# フォーマットと拡張子の対応
_FORMAT_EXTENSIONS = {
    "txt": ".txt",
    "docx": ".docx",
    "xlsx": ".xlsx",
    "srt": ".srt",
    "vtt": ".vtt",
    "json": ".json",
}


def _validate_output_path(output_path: str):
    """出力パスのバリデーション（パストラバーサル防止）"""
    try:
        Validator.validate_file_path(output_path, must_exist=False)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail="出力パスが不正です")


def _get_segments(req: ExportRequest):
    """セグメントを返す。セグメントがない場合はテキストから単一セグメントを作成"""
    if req.segments:
        return req.segments
    return [{"text": req.text, "start": 0, "end": 0, "speaker": ""}]


@router.post("/export/{format}", response_model=ExportResponse)
async def export_file(format: str, req: ExportRequest):
    """文字起こし結果をエクスポート"""
    _validate_output_path(req.output_path)

    # 拡張子とフォーマットの整合性チェック
    expected_ext = _FORMAT_EXTENSIONS.get(format)
    if expected_ext:
        actual_ext = os.path.splitext(req.output_path)[1].lower()
        if actual_ext and actual_ext != expected_ext:
            raise HTTPException(status_code=400, detail="出力パスの拡張子がフォーマットと一致しません")

    try:
        if format == "txt":
            return await asyncio.to_thread(_export_txt, req)
        elif format == "docx":
            return await asyncio.to_thread(_export_docx, req)
        elif format == "xlsx":
            return await asyncio.to_thread(_export_xlsx, req)
        elif format == "srt":
            return await asyncio.to_thread(_export_srt, req)
        elif format == "vtt":
            return await asyncio.to_thread(_export_vtt, req)
        elif format == "json":
            return await asyncio.to_thread(_export_json, req)
        else:
            raise HTTPException(status_code=400, detail="未対応のフォーマットです")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="エクスポート処理中にエラーが発生しました")


def _export_txt(req: ExportRequest) -> ExportResponse:
    """テキストファイルとしてエクスポート"""
    from export.common import atomic_write_text, validate_export_path
    validate_export_path(req.output_path)
    atomic_write_text(req.output_path, req.text)
    return ExportResponse(success=True, output_path=req.output_path, message="TXTエクスポート完了")


def _export_docx(req: ExportRequest) -> ExportResponse:
    """Word文書としてエクスポート"""
    from export.word_exporter import WordExporter
    exporter = WordExporter()
    if not exporter.has_python_docx:
        raise HTTPException(status_code=501, detail="python-docxがインストールされていません")
    segments = _get_segments(req)
    success = exporter.export_transcription(segments, req.output_path)
    if not success:
        raise HTTPException(status_code=500, detail="DOCXエクスポートに失敗しました")
    return ExportResponse(success=True, output_path=req.output_path, message="DOCXエクスポート完了")


def _export_xlsx(req: ExportRequest) -> ExportResponse:
    """Excelファイルとしてエクスポート"""
    from export.excel_exporter import ExcelExporter
    exporter = ExcelExporter()
    if not exporter.has_openpyxl:
        raise HTTPException(status_code=501, detail="openpyxlがインストールされていません")
    segments = _get_segments(req)
    success = exporter.export_transcription(segments, req.output_path)
    if not success:
        raise HTTPException(status_code=500, detail="XLSXエクスポートに失敗しました")
    return ExportResponse(success=True, output_path=req.output_path, message="XLSXエクスポート完了")


def _export_srt(req: ExportRequest) -> ExportResponse:
    """SRT字幕ファイルとしてエクスポート"""
    if not req.segments:
        raise HTTPException(status_code=400, detail="SRTエクスポートにはセグメント情報が必要です")
    from export.common import validate_export_path
    validate_export_path(req.output_path)
    from subtitle_exporter import SubtitleExporter
    exporter = SubtitleExporter()
    success = exporter.export_srt(req.segments, req.output_path)
    if not success:
        raise HTTPException(status_code=500, detail="SRTエクスポートに失敗しました")
    return ExportResponse(success=True, output_path=req.output_path, message="SRTエクスポート完了")


def _export_vtt(req: ExportRequest) -> ExportResponse:
    """VTT字幕ファイルとしてエクスポート"""
    if not req.segments:
        raise HTTPException(status_code=400, detail="VTTエクスポートにはセグメント情報が必要です")
    from export.common import validate_export_path
    validate_export_path(req.output_path)
    from subtitle_exporter import SubtitleExporter
    exporter = SubtitleExporter()
    success = exporter.export_vtt(req.segments, req.output_path)
    if not success:
        raise HTTPException(status_code=500, detail="VTTエクスポートに失敗しました")
    return ExportResponse(success=True, output_path=req.output_path, message="VTTエクスポート完了")


def _export_json(req: ExportRequest) -> ExportResponse:
    """JSONファイルとしてエクスポート"""
    import json
    from export.common import atomic_write_text, validate_export_path
    validate_export_path(req.output_path)
    data = {
        "text": req.text,
        "segments": req.segments,
    }
    atomic_write_text(req.output_path, json.dumps(data, ensure_ascii=False, indent=2))
    return ExportResponse(success=True, output_path=req.output_path, message="JSONエクスポート完了")
