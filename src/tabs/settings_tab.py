"""
設定タブ
統合アプリの共通設定を管理
"""

import logging

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app_settings import AppSettings
from config_manager import get_config, ConfigManager

logger = logging.getLogger(__name__)


class SettingsTab(QWidget):
    """設定タブ"""

    # カスタムシグナル
    status_message = Signal(str)
    settings_applied = Signal(dict)  # 設定適用時に通知（ダークモード切り替えなど）

    # モデル名マッピング（表示名 -> 内部名）
    MODEL_MAPPING = {
        "tiny": "kotoba-tech/kotoba-whisper-v2.2-tiny",
        "base": "kotoba-tech/kotoba-whisper-v2.2-base",
        "small": "kotoba-tech/kotoba-whisper-v2.2-small",
        "medium": "kotoba-tech/kotoba-whisper-v2.2-medium",
        "large": "kotoba-tech/kotoba-whisper-v2.2-large",
        "large-v2": "kotoba-tech/kotoba-whisper-v2.2-large-v2",
        "large-v3": "kotoba-tech/kotoba-whisper-v2.2",
    }

    # 逆マッピング（内部名 -> 表示名）
    MODEL_REVERSE_MAPPING = {v: k for k, v in MODEL_MAPPING.items()}

    def __init__(self):
        super().__init__()

        # 設定管理
        self.settings = AppSettings("unified_settings.json")
        self.settings.load()
        self.config = get_config()
        self.config_manager = ConfigManager()  # save()メソッド用

        self.init_ui()
        self.load_settings()

        logger.info("SettingsTab initialized")

    def init_ui(self):
        """UI初期化"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # === モデル設定グループ ===
        model_group = QGroupBox("モデル設定")
        model_layout = QVBoxLayout()
        model_layout.setContentsMargins(12, 16, 12, 12)
        model_layout.setSpacing(8)

        # Whisperモデル選択
        model_layout.addWidget(QLabel("Whisperモデル:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"])
        self.model_combo.setToolTip(
            "使用するWhisperモデルを選択します。\nlarge-v3が最も精度が高いですが、処理時間がかかります。"
        )
        model_layout.addWidget(self.model_combo)

        # デバイス選択
        model_layout.addWidget(QLabel("処理デバイス:"))
        self.device_combo = QComboBox()
        self.device_combo.addItems(["auto", "cpu", "cuda"])
        self.device_combo.setToolTip("処理に使用するデバイスを選択します。\nauto: 自動検出\ncuda: GPU (NVIDIA)")
        model_layout.addWidget(self.device_combo)

        model_group.setLayout(model_layout)
        main_layout.addWidget(model_group)

        # === 処理オプショングループ ===
        processing_group = QGroupBox("処理オプション")
        processing_layout = QVBoxLayout()
        processing_layout.setContentsMargins(12, 16, 12, 12)
        processing_layout.setSpacing(8)

        self.diarization_checkbox = QCheckBox("話者分離を有効化")
        self.diarization_checkbox.setToolTip("複数の話者を識別して文字起こしします（処理時間が増加します）")
        processing_layout.addWidget(self.diarization_checkbox)

        self.filler_checkbox = QCheckBox("フィラー削除を有効化")
        self.filler_checkbox.setToolTip("「えー」「あー」などのフィラーを自動削除します")
        processing_layout.addWidget(self.filler_checkbox)

        self.llm_checkbox = QCheckBox("LLM補正を有効化")
        self.llm_checkbox.setToolTip("AIを使用して文字起こし結果を補正します（推奨）")
        processing_layout.addWidget(self.llm_checkbox)

        self.preprocessing_checkbox = QCheckBox("音声前処理を有効化")
        self.preprocessing_checkbox.setToolTip("ノイズ除去や音量正規化を行います（実験的機能）")
        processing_layout.addWidget(self.preprocessing_checkbox)

        processing_group.setLayout(processing_layout)
        main_layout.addWidget(processing_group)

        # === UI設定グループ ===
        ui_group = QGroupBox("UI設定")
        ui_layout = QVBoxLayout()
        ui_layout.setContentsMargins(12, 16, 12, 12)
        ui_layout.setSpacing(8)

        self.dark_mode_checkbox = QCheckBox("ダークモードを有効化")
        self.dark_mode_checkbox.setToolTip("ダークテーマで表示します（即座に反映）")
        ui_layout.addWidget(self.dark_mode_checkbox)

        ui_group.setLayout(ui_layout)
        main_layout.addWidget(ui_group)

        # === 自動起動グループ ===
        autostart_group = QGroupBox("自動起動設定")
        autostart_layout = QVBoxLayout()
        autostart_layout.setContentsMargins(12, 16, 12, 12)
        autostart_layout.setSpacing(8)

        self.autostart_checkbox = QCheckBox("Windows起動時に自動起動")
        self.autostart_checkbox.setToolTip("システム起動時に自動でアプリケーションを起動します（未実装）")
        self.autostart_checkbox.setEnabled(False)  # 後のタスクで実装
        autostart_layout.addWidget(self.autostart_checkbox)

        self.autostart_monitor_checkbox = QCheckBox("起動時にフォルダ監視を開始")
        self.autostart_monitor_checkbox.setToolTip("アプリケーション起動時に自動でフォルダ監視を開始します（未実装）")
        self.autostart_monitor_checkbox.setEnabled(False)  # 後のタスクで実装
        autostart_layout.addWidget(self.autostart_monitor_checkbox)

        autostart_group.setLayout(autostart_layout)
        main_layout.addWidget(autostart_group)

        # スペーサー
        main_layout.addStretch()

        # === 保存ボタン ===
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.save_button = QPushButton("設定を保存")
        self.save_button.setObjectName("primary")
        self.save_button.setMinimumWidth(150)
        self.save_button.setMinimumHeight(36)
        self.save_button.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_button)

        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        logger.info("Settings UI initialized")

    def load_settings(self):
        """設定を読み込んでUIに反映"""
        try:
            # モデル設定
            model_name = self.config.get("model.whisper.name", "kotoba-tech/kotoba-whisper-v2.2")
            display_name = self.MODEL_REVERSE_MAPPING.get(model_name, "large-v3")
            index = self.model_combo.findText(display_name)
            if index >= 0:
                self.model_combo.setCurrentIndex(index)

            device = self.config.get("model.whisper.device", "auto")
            index = self.device_combo.findText(device)
            if index >= 0:
                self.device_combo.setCurrentIndex(index)

            # 処理オプション
            self.diarization_checkbox.setChecked(self.settings.get("enable_diarization", False))
            self.filler_checkbox.setChecked(self.settings.get("remove_fillers", True))
            self.llm_checkbox.setChecked(self.settings.get("enable_llm_correction", True))
            self.preprocessing_checkbox.setChecked(self.settings.get("enable_preprocessing", False))

            # UI設定
            self.dark_mode_checkbox.setChecked(self.settings.get("dark_mode", False))

            # 自動起動設定（未実装）
            self.autostart_checkbox.setChecked(False)
            self.autostart_monitor_checkbox.setChecked(False)

            logger.info("Settings loaded to UI")
            self.status_message.emit("設定を読み込みました")

        except Exception as e:
            logger.error(f"Failed to load settings: {e}", exc_info=True)
            self.status_message.emit("設定の読み込みに失敗しました")
            QMessageBox.warning(self, "エラー", "設定の読み込みに失敗しました")

    def save_settings(self):
        """設定を保存"""
        try:
            # モデル設定（ConfigManager）
            display_name = self.model_combo.currentText()
            model_name = self.MODEL_MAPPING.get(display_name, "kotoba-tech/kotoba-whisper-v2.2")
            self.config.set("model.whisper.name", model_name)

            device = self.device_combo.currentText()
            self.config.set("model.whisper.device", device)

            # 処理オプション（AppSettings）
            self.settings.set("enable_diarization", self.diarization_checkbox.isChecked())
            self.settings.set("remove_fillers", self.filler_checkbox.isChecked())
            self.settings.set("enable_llm_correction", self.llm_checkbox.isChecked())
            self.settings.set("enable_preprocessing", self.preprocessing_checkbox.isChecked())

            # UI設定（AppSettings）
            dark_mode_changed = self.settings.get("dark_mode", False) != self.dark_mode_checkbox.isChecked()
            self.settings.set("dark_mode", self.dark_mode_checkbox.isChecked())

            # 設定を保存
            self.settings.save_immediate()

            # ConfigManagerの設定も保存（P0修正）
            if not self.config_manager.save():
                logger.warning("Failed to save ConfigManager settings")

            logger.info("Settings saved successfully")
            self.status_message.emit("設定を保存しました")

            # 設定適用
            self.apply_settings(dark_mode_changed)

            QMessageBox.information(self, "完了", "設定を保存しました。\n一部の設定は次回起動時に反映されます。")

        except Exception as e:
            logger.error(f"Failed to save settings: {e}", exc_info=True)
            self.status_message.emit("設定の保存に失敗しました")
            QMessageBox.critical(self, "エラー", "設定の保存に失敗しました")

    def apply_settings(self, dark_mode_changed: bool):
        """設定を即座に反映"""
        try:
            # ダークモード変更時のみシグナルを発行
            if dark_mode_changed:
                settings_dict = {"dark_mode": self.dark_mode_checkbox.isChecked()}
                self.settings_applied.emit(settings_dict)
                logger.info(f"Settings applied signal emitted: dark_mode={settings_dict['dark_mode']}")

        except Exception as e:
            logger.error(f"Failed to apply settings: {e}", exc_info=True)
