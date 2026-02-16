"""設定ルーター"""

import logging

from fastapi import APIRouter, HTTPException

from api.dependencies import get_app_settings, get_config_manager
from api.schemas import ConfigModel, SettingsModel

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/settings")
async def get_settings():
    """アプリケーション設定を取得"""
    try:
        settings = get_app_settings()
        return _mask_sensitive_keys(settings.get_all())
    except Exception as e:
        logger.error(f"設定の取得に失敗: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="設定の取得に失敗しました")


@router.patch("/settings")
async def update_settings(updates: SettingsModel):
    """アプリケーション設定を更新"""
    settings = get_app_settings()
    update_dict = {k: v for k, v in updates.model_dump().items() if v is not None}

    if not update_dict:
        return {"message": "更新する項目がありません", "updated": {}}

    try:
        for key, value in update_dict.items():
            settings.set(key, value)
    except Exception as e:
        logger.error(f"設定の更新に失敗: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="設定の更新に失敗しました")

    return {"message": "設定を更新しました", "updated": update_dict}


def _mask_sensitive_keys(data, sensitive_keys=("api_key", "secret", "password", "token")):
    """辞書内の機密キーの値をマスクする（部分一致）"""
    if isinstance(data, dict):
        return {
            k: (
                "****"
                if any(s in k.lower() for s in sensitive_keys) and v is not None
                else _mask_sensitive_keys(v, sensitive_keys)
            )
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_mask_sensitive_keys(item, sensitive_keys) for item in data]
    return data


@router.get("/config")
async def get_config():
    """システム設定を取得（機密情報はマスク済み）"""
    try:
        config = get_config_manager()
        data = config.config.data
        return _mask_sensitive_keys(data)
    except Exception as e:
        logger.error(f"システム設定の取得に失敗: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="システム設定の取得に失敗しました")


def flatten_and_set(cfg, prefix: str, obj):
    """ネストされた dict を再帰的にフラットキーに展開して cfg.set() する"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            flatten_and_set(cfg, f"{prefix}.{k}" if prefix else k, v)
    else:
        cfg.set(prefix, obj)


@router.patch("/config")
async def update_config(updates: ConfigModel):
    """システム設定を更新"""
    config = get_config_manager()
    update_dict = {k: v for k, v in updates.model_dump().items() if v is not None}

    if not update_dict:
        return {"message": "更新する項目がありません", "updated": {}}

    try:
        cfg = config.config  # Config オブジェクト（set() メソッドを持つ）
        for key, value in update_dict.items():
            flatten_and_set(cfg, key, value)
    except Exception as e:
        logger.error(f"システム設定の更新に失敗: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="システム設定の更新に失敗しました")

    return {"message": "設定を更新しました", "updated": update_dict}
