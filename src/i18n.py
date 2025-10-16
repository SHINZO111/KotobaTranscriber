"""
Internationalization (i18n) Manager for KotobaTranscriber

This module provides internationalization support for the application,
allowing user-facing messages to be displayed in multiple languages
(Japanese and English).

Usage:
    from i18n import t, i18n_manager

    # Get translated message
    message = t("errors.file_not_found", path="/path/to/file")

    # Switch language
    i18n_manager.set_language("en")
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class I18nManager:
    """
    Manages internationalization for the application.

    Handles loading and retrieving localized messages from JSON files.
    Supports parameter interpolation using Python's format string syntax.

    Attributes:
        language: Current language code (e.g., "ja", "en")
        messages: Dictionary of loaded message keys and translations
        fallback_messages: Fallback messages when translation is missing
    """

    def __init__(self, language: str = "ja"):
        """
        Initialize the I18nManager.

        Args:
            language: Language code to load (default: "ja")
        """
        self.language = language
        self.messages: Dict[str, str] = {}
        self.fallback_messages: Dict[str, str] = {}
        self._base_path = Path(__file__).parent.parent / "locales"
        self.load_messages()

    def load_messages(self) -> None:
        """
        Load message translations from JSON file for current language.

        Attempts to load messages from locales/{language}/messages.json.
        If the file doesn't exist or can't be loaded, logs a warning and
        uses fallback messages.
        """
        locale_file = self._base_path / self.language / "messages.json"

        try:
            if locale_file.exists():
                with open(locale_file, 'r', encoding='utf-8') as f:
                    self.messages = json.load(f)
                logger.info(f"Loaded {len(self.messages)} messages for language: {self.language}")
            else:
                logger.warning(f"Locale file not found: {locale_file}")
                self.messages = self._get_fallback_messages()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in locale file {locale_file}: {e}")
            self.messages = self._get_fallback_messages()
        except Exception as e:
            logger.error(f"Error loading locale file {locale_file}: {e}")
            self.messages = self._get_fallback_messages()

    def t(self, key: str, **kwargs) -> str:
        """
        Get translated message for given key with optional parameter substitution.

        Args:
            key: Message key (e.g., "errors.file_not_found")
            **kwargs: Parameters to interpolate into the message

        Returns:
            Translated message with interpolated parameters, or the key itself
            if translation is not found

        Examples:
            >>> t("errors.file_not_found", path="/test.mp3")
            "ファイルが見つかりません: /test.mp3"

            >>> t("progress.processing", percent=50)
            "処理中... 50%"
        """
        message = self.messages.get(key)

        if message is None:
            logger.warning(f"Translation key not found: {key}")
            # Return key as fallback
            message = key

        try:
            # Interpolate parameters if provided
            if kwargs:
                return message.format(**kwargs)
            return message
        except KeyError as e:
            logger.error(f"Missing parameter in translation for key '{key}': {e}")
            return message
        except Exception as e:
            logger.error(f"Error formatting translation for key '{key}': {e}")
            return message

    def set_language(self, language: str) -> None:
        """
        Switch to a different language and reload messages.

        Args:
            language: Language code to switch to (e.g., "ja", "en")
        """
        if language != self.language:
            logger.info(f"Switching language from {self.language} to {language}")
            self.language = language
            self.load_messages()

    def get_available_languages(self) -> list[str]:
        """
        Get list of available language codes.

        Returns:
            List of language codes that have message files
        """
        available = []
        if self._base_path.exists():
            for lang_dir in self._base_path.iterdir():
                if lang_dir.is_dir() and (lang_dir / "messages.json").exists():
                    available.append(lang_dir.name)
        return sorted(available)

    def _get_fallback_messages(self) -> Dict[str, str]:
        """
        Get fallback messages in Japanese when locale file is unavailable.

        Returns:
            Dictionary of fallback messages
        """
        return {
            "errors.file_not_found": "ファイルが見つかりません: {path}",
            "errors.invalid_format": "サポートされていない形式です: {format}",
            "errors.model_load_failed": "モデルの読み込みに失敗しました: {model}",
            "errors.transcription_failed": "文字起こしに失敗しました",
            "errors.insufficient_memory": "メモリが不足しています",
            "errors.generic": "エラーが発生しました: {error}",
            "success.transcription_completed": "文字起こしが完了しました",
            "progress.loading_model": "モデルを読み込んでいます...",
            "progress.processing": "処理中... {percent}%",
        }


# Global singleton instance
_i18n_manager: Optional[I18nManager] = None


def get_i18n_manager(language: str = "ja") -> I18nManager:
    """
    Get or create the global I18nManager instance.

    Args:
        language: Language code for initialization (only used on first call)

    Returns:
        Global I18nManager instance
    """
    global _i18n_manager
    if _i18n_manager is None:
        _i18n_manager = I18nManager(language)
    return _i18n_manager


# Convenience reference to global instance
i18n_manager = get_i18n_manager()


def t(key: str, **kwargs) -> str:
    """
    Convenience function to get translated message from global manager.

    Args:
        key: Message key
        **kwargs: Parameters for interpolation

    Returns:
        Translated message

    Examples:
        >>> from i18n import t
        >>> t("errors.file_not_found", path="/test.mp3")
        "ファイルが見つかりません: /test.mp3"
    """
    return i18n_manager.t(key, **kwargs)


def set_language(language: str) -> None:
    """
    Convenience function to switch language globally.

    Args:
        language: Language code to switch to
    """
    i18n_manager.set_language(language)


# Module-level exports
__all__ = [
    'I18nManager',
    'i18n_manager',
    't',
    'set_language',
    'get_i18n_manager',
]
