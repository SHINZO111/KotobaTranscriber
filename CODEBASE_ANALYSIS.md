# KotobaTranscriber Codebase Analysis

## 1. PROJECT OVERVIEW
- **Language**: Python 3.8+
- **Framework**: PySide6 (Qt GUI framework)
- **Purpose**: Japanese speech-to-text transcription application
- **Platform**: Windows 10/11 (uses win32 API for multiple instance prevention)

## 2. MAIN ENTRY POINT AND CLI ARGUMENT PARSING

### Entry Point: /home/user/KotobaTranscriber/src/main.py
- **Lines**: ~1,907 lines
- **Type**: GUI Application (not CLI)
- **Main Function**: `main()` at line 1871
- **Key Implementation**:
  - Multi-instance prevention using Windows mutex (win32event, win32api)
  - Single QApplication instance enforced
  - System tray integration (QSystemTrayIcon)
  - Window geometry persistence

### CLI Argument Status
- **CURRENT STATE**: No CLI argument parsing implemented
- **MISSING COMPONENTS**:
  - No argparse module usage
  - No sys.argv processing
  - Entire app is GUI-based
  - No command-line flags currently exist

### Missing Modules (Referenced but Not Implemented)
1. `validators` module - for file path validation
   - Classes needed: `Validator`, `ValidationError`
   - Methods needed: `validate_file_path()`
   
2. `config_manager` module - for YAML configuration management
   - Function needed: `get_config()`
   - Should provide configuration management

## 3. PERMISSIONS AND SECURITY CHECKS

### Current Permissions Handling
Located in: /home/user/KotobaTranscriber/src/main.py

#### File Access Permissions
- **PermissionError** exceptions caught at:
  - Line 192: Audio file reading (single file transcription)
  - Line 286: Output file writing (batch processing)
  - Line 432: Audio file reading (transcription worker)
  - Line 950: Output file writing (auto-save feature)

#### Path Traversal Protection
- **Location**: main.py lines 947-962 (auto_save_text method)
- **Implementation**: 
  - Validates output file paths using Validator.validate_file_path()
  - Checks file extensions (only .txt allowed)
  - Verifies real paths don't escape parent directory
  - Uses os.path.realpath() for symlink resolution

#### FFmpeg Path Validation
- **Location**: /home/user/KotobaTranscriber/src/transcription_engine.py lines 36-90
- **Implementation**:
  - `_validate_ffmpeg_path()` function validates PATH injection
  - Whitelist of allowed directories:
    - Windows: C:\ffmpeg, C:\Program Files\ffmpeg
    - Linux: /usr/bin, /usr/local/bin, /opt/ffmpeg
  - Uses symlink resolution (os.path.realpath())
  - Verifies paths using Path.relative_to() for strict parent checking

### Permissions-Related Exception Handling
- **AudioCaptureError**: When microphone access is denied
- **FileProcessingError**: When file read/write fails
- **InsufficientMemoryError**: When system resources are insufficient
- **PathTraversalError**: When path traversal attack detected
- **UnsafePathError**: When accessing critical system directories

## 4. CONFIGURATION AND SETTINGS FILES

### Configuration Files
1. **YAML Configuration**: /home/user/KotobaTranscriber/config/
   - config.yaml - Active configuration
   - config.example.yaml - Template with all options

2. **Application Settings**: /home/user/KotobaTranscriber/app_settings.json
   - User preferences (monitored folder, UI settings, options)
   - Managed by AppSettings class

3. **Custom Vocabulary**: /home/user/KotobaTranscriber/custom_vocabulary.json
   - User-defined terms for better transcription accuracy

### AppSettings Module
- **File**: /home/user/KotobaTranscriber/src/app_settings.py (653 lines)
- **Key Features**:
  - JSON-based persistence
  - Thread-safe with RLock
  - Debounced save mechanism (2-second delay)
  - Automatic backup with rotation (max 5 backups)
  - Comprehensive input validation
  - Type checking and range validation
  - Atomic file writes using temporary files

### YAML Configuration Manager (Missing Implementation)
The code expects a `config_manager` module that should:
- Load YAML configuration files
- Provide get_config() function
- Support hierarchical config access (dot notation)
- Include settings for:
  - Model parameters (Whisper configuration)
  - Audio processing settings
  - Logging configuration
  - Performance tuning
  - GUI settings
  - Advanced features (speaker diarization, LLM correction)

## 5. LANGUAGE AND FRAMEWORK DETAILS

### Python Environment
- Minimum Version: Python 3.8
- Build System: setuptools, wheel
- Package Management: pyproject.toml

### Key Dependencies
- **GUI**: PySide6 (Qt for Python)
- **ML/AI**: 
  - transformers (4.30.0+)
  - torch (2.0.0+)
  - faster-whisper (1.0.0+)
  - speechbrain (0.5.0+) - speaker diarization
- **Audio Processing**:
  - librosa (0.10.0+)
  - soundfile (0.12.0+)
  - pydub (0.25.0+)
  - pyaudio (0.2.13+)
- **Data Processing**:
  - numpy (1.24.0+)
  - pandas (2.0.0+)
  - scikit-learn (1.0.0+)
- **Windows Integration**: pywin32 (win32event, win32api, winreg)

### Architecture Pattern
- **Multi-threaded GUI**: 
  - Main UI thread (QMainWindow)
  - Worker threads (QThread) for long operations
  - ThreadPoolExecutor for batch processing
  - Thread-safe data structures with locks

## 6. EXISTING CLI FLAG IMPLEMENTATIONS

### Current Status: NO CLI FLAGS IMPLEMENTED
The application is entirely GUI-based with no command-line interface.

### UI-Based Settings (Equivalent to Flags)
Instead of CLI flags, the application uses GUI checkboxes and buttons:

1. **Text Formatting Options** (Format Tab):
   - ☐ Remove fillers (delete "uh", "um", "like")
   - ☐ Speaker diarization (identify different speakers)
   - ☐ Audio preprocessing (noise reduction)
   - ☐ Custom vocabulary (use domain-specific terms)
   - ☐ Advanced LLM correction (AI-based text refinement)

2. **Advanced Settings**:
   - Monitor interval slider (5-60 seconds)
   - ☐ Windows auto-startup
   - ☐ Auto-move completed files
   - Folder selection for monitoring and file destinations

3. **Processing Buttons**:
   - Single file transcription
   - Batch file processing (multiple files)
   - Folder monitoring (auto-process new files)

### How Settings Are Persisted
- Saved to app_settings.json on application exit
- Debounced saves during runtime
- Automatic backup with timestamp

## 7. PROJECT STRUCTURE

### Main Source Files
```
/home/user/KotobaTranscriber/src/
├── main.py (1,907 lines) - Main GUI application
├── app_settings.py (653 lines) - Settings management
├── exceptions.py (777 lines) - Custom exception hierarchy
├── transcription_engine.py (491 lines) - Whisper integration
├── faster_whisper_engine.py (387 lines) - FasterWhisper wrapper
├── text_formatter.py (523 lines) - Text post-processing
├── llm_corrector_standalone.py (386 lines) - LLM-based text correction
├── speaker_diarization_free.py (231 lines) - Speaker separation
├── folder_monitor.py (264 lines) - Directory watching for auto-processing
├── batch_processor.py (414 lines) - Batch file processing
├── custom_vocabulary.py (313 lines) - Custom vocabulary management
├── vocabulary_dialog.py (384 lines) - Vocabulary UI dialog
├── advanced_features.py (159 lines) - StartupManager, FileOrganizer
└── __init__.py (7 lines)
```

### Configuration Files
```
/home/user/KotobaTranscriber/
├── config/
│   ├── config.yaml - Active configuration
│   ├── config.example.yaml - Template
│   └── logging.yaml - Logging configuration
├── app_settings.json - User preferences
├── custom_vocabulary.json - Custom terms
└── pyproject.toml - Python project metadata
```

## 8. KEY OBSERVATIONS FOR PERMISSIONS/CLI WORK

### Missing But Required Modules
1. **validators.py** - MUST CREATE
   - Validator class with validate_file_path() method
   - ValidationError exception class
   - Input validation and sanitization

2. **config_manager.py** - MUST CREATE
   - get_config() function
   - YAML configuration loading
   - Configuration object with hierarchical access

### Permissions Architecture Needed
The codebase already has:
- Error handling for PermissionError
- Path traversal protection logic
- FFmpeg path whitelisting

Missing:
- Formalized validator module
- Consistent permission checking API
- Centralized permission policy

### For CLI Flag Implementation
Would need:
- argparse integration in main()
- Command-line argument parser
- Flag definitions (--skip-permissions, etc.)
- Mode switching between GUI and CLI
- Non-interactive output handling

## 9. WINDOWS-SPECIFIC FEATURES

### Multi-Instance Prevention
- Uses win32event.CreateMutex() for system-wide mutex
- Named mutex: "Global\\KotobaTranscriber_SingleInstance_Mutex"
- Prevents multiple instances from running

### Windows Startup Integration
- Registry modification via winreg module
- Reads/writes: HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
- StartupManager class in advanced_features.py

### System Tray Integration
- QSystemTrayIcon for taskbar tray
- Context menu with Show/Hide/Quit options
- Tray notifications for status updates
- Window minimize-to-tray behavior

## 10. SECURITY MEASURES IMPLEMENTED

✓ Path traversal protection (realpath validation)
✓ File extension whitelisting (.txt, audio formats)
✓ FFmpeg path whitelisting
✓ Symlink resolution (os.path.realpath)
✓ Permission error handling
✓ Exception hierarchy for security errors
✓ Settings file backup with rotation
✓ Atomic file writes (temp file + rename)
✓ Thread-safe data structures

⚠ MISSING:
- Central validator module (referenced but not created)
- Configuration manager module (referenced but not created)
- Input validation framework (partially in place)
