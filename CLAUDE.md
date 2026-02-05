# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KotobaTranscriber is a Japanese speech-to-text desktop application using Kotoba-Whisper v2.2 and Faster-Whisper models. Built with PySide6 (Qt6) for the GUI and PyTorch for ML inference. Targets Windows 10/11, Python 3.8-3.12.

## Commands

### Run the application
```bash
python src/main.py
```

### Testing
```bash
# Run all tests with coverage (65% minimum enforced, 300s timeout per test)
pytest

# Run by marker
pytest -m unit
pytest -m integration
pytest -m production
pytest -m performance
pytest -m gui

# Skip slow or GPU tests
pytest -m "not slow and not gpu"

# Run a single test file
pytest tests/test_enhancements.py -v

# Run a single test
pytest tests/test_enhancements.py::TestClassName::test_method -v
```

### Code quality
```bash
# Format (line length 127)
black src/ tests/

# Sort imports (black-compatible profile)
isort src/ tests/

# Lint (max complexity 15)
flake8 src/ tests/

# Type check
mypy src/

# Security scan
bandit -r src/
```

### Build
```bash
# PyInstaller executable
pyinstaller build.spec

# Full release package (exe + installer + checksums)
python build_release.py
```

## Architecture

### Entry point and main module
`src/main.py` (~1,900 lines) is the monolithic main module containing the PySide6 GUI, threading orchestration, and all tab/panel logic. It imports all other modules and manages the application lifecycle.

### Transcription engines (two-model strategy)
- `src/transcription_engine.py` — Primary engine using Kotoba-Whisper v2.2 via HuggingFace Transformers. Best accuracy for Japanese.
- `src/faster_whisper_engine.py` — Alternative engine optimized for real-time/low-latency use.

### Post-processing pipeline
Transcribed text flows through an optional chain: `text_formatter.py` (filler removal, punctuation, paragraphs) → `speaker_diarization_free.py` (SpeechBrain-based speaker separation) → `llm_corrector_standalone.py` (local LLM correction) or `api_corrector.py` (Claude/OpenAI API correction). Each step can be independently enabled/disabled.

### Domain-specific features (v2.2+)
- `construction_vocabulary.py` / `custom_dictionary.py` — Construction industry terminology support (AGEC-specific terms, labor costs, construction law)
- `meeting_minutes_generator.py` / `minutes_generator.py` — Auto-generates meeting minutes with speaker detection and auto-save
- `enhanced_export.py` / `enhanced_subtitle_exporter.py` — Extended export with segment merging and SRT/VTT formatting

### Processing modes
- **Single file**: Direct transcription from the main tab
- **Batch**: `batch_processor.py` / `enhanced_batch_processor.py` (with checkpointing and memory monitoring)
- **Folder monitor**: `folder_monitor.py` watches directories via QThread
- **Real-time**: `realtime_tab.py` captures live microphone input via PyAudio + WebRTC VAD

### Export formats
TXT, DOCX (`src/export/word_exporter.py`), XLSX (`src/export/excel_exporter.py`), SRT/VTT (`subtitle_exporter.py`), JSON with timestamps.

### Enhancement modules
- `dark_theme.py`, `ui_enhancements.py`, `ui_responsive.py` — UI customization and theming
- `memory_optimizer.py`, `device_manager.py`, `optimized_pipeline.py` — Performance optimization
- `error_recovery.py`, `enhanced_error_handling.py` — Robust error recovery and retry logic

### Configuration
- `config/config.yaml` — System defaults (model names, device settings, FFmpeg path, API config). Note: audio preprocessing is disabled by default to avoid meta tensor errors.
- `app_settings.json` — User preferences, persisted as JSON with thread-safe atomic writes and automatic backup rotation (max 5 generations in `.backups/`)
- API keys: use environment variables `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`

### Qt compatibility layer (legacy)
`src/qt_compat.py` provides PyQt5/PySide6 compatibility helpers (`exec_dialog()`, `exec_app()`), but most production code imports PySide6 directly.

### Threading model
Main GUI thread runs the PySide6 event loop. Transcription, batch processing, and folder monitoring each run on separate worker threads (QThread / ThreadPoolExecutor). All engine operations are off the main thread.

### Exception hierarchy
`src/exceptions.py` defines 27 typed exceptions under `KotobaTranscriberError`, organized by domain: `FileProcessingError`, `TranscriptionError`, `ConfigurationError`, `BatchProcessingError`, `ResourceError`, `RealtimeProcessingError`, `SecurityError`.

## Code Style

- Line length: 127 characters (black + flake8 aligned)
- Import sorting: isort with `profile = "black"`
- flake8 ignores: E203, E501, W503, W504, E402, F401
- Max cyclomatic complexity: 15
- GUI framework: PySide6 (direct imports in production code)
- All source code is in the `src/` package; tests in `tests/`
