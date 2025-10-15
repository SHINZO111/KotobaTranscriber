# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KotobaTranscriber is a Japanese speech-to-text transcription application built with Python and PyQt5. It uses kotoba-whisper v2.2 (a Japanese-optimized Whisper model from Hugging Face) for high-accuracy offline transcription. The application features a modern GUI with text post-processing capabilities including filler word removal, punctuation formatting, and paragraph structuring.

## Architecture

### Technology Stack
- **Python**: 3.8+ (developed with 3.13.7)
- **GUI Framework**: PyQt5 5.15.0+
- **Speech Recognition**: kotoba-whisper v2.2 via Hugging Face Transformers
- **ML Framework**: PyTorch 2.0+ with CUDA 11.8/12.1 support
- **Audio Processing**: librosa, soundfile, pydub, ffmpeg
- **Speaker Diarization**: pyannote.audio 3.0+ (planned feature)

### Project Structure
```
KotobaTranscriber/
├── src/
│   ├── main.py                    # Main PyQt5 application
│   ├── transcription_engine.py    # Whisper transcription engine
│   ├── text_formatter.py          # Text post-processing module
│   └── __init__.py
├── tests/                         # Test files (to be added)
├── docs/                          # Documentation
├── models/                        # Whisper models (auto-downloaded)
├── venv/                          # Virtual environment
├── requirements.txt               # Python dependencies
├── README.md                      # User documentation
└── CLAUDE.md                      # This file
```

### Key Components

#### 1. Main Application (main.py)
- **MainWindow**: QMainWindow-based GUI with MVVM-like pattern
- **TranscriptionWorker**: QThread for non-blocking transcription
- **UI Components**:
  - File selection dialog (15 audio/video formats)
  - Text formatting options (checkboxes)
  - Progress bar with real-time updates
  - Result display (QTextEdit)
  - Save functionality

#### 2. Transcription Engine (transcription_engine.py)
- **TranscriptionEngine**: Wrapper for kotoba-whisper v2.2
- **Model Management**: Automatic download from Hugging Face
- **Device Selection**: Auto-detects CUDA GPU or falls back to CPU
- **ffmpeg Integration**: Auto-configures PATH for audio processing
- **Pipeline API**: Uses transformers.pipeline for ASR

#### 3. Text Formatter (text_formatter.py)
- **TextFormatter**: Post-processing for transcription results
- **Features**:
  - Filler word removal (あー, えー, その, etc. - 19 words)
  - Punctuation formatting with Japanese grammar rules
  - Paragraph structuring (3 sentences per paragraph)
  - Repeated word cleaning
  - Number formatting

## Development Commands

### Setup and Installation

```bash
# Navigate to project directory
cd F:\VoiceToText\KotobaTranscriber

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install PyTorch with CUDA 11.8
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Install PyTorch with CUDA 12.1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# CPU-only PyTorch
pip install torch torchvision torchaudio

# Install ffmpeg (Windows)
# Run from F:\VoiceToText directory:
powershell -ExecutionPolicy Bypass -File install-ffmpeg.ps1
```

### Running the Application

```bash
# Make sure virtual environment is activated
cd src
python main.py
```

### Testing

```bash
# Test transcription engine
cd src
python transcription_engine.py

# Test text formatter
python text_formatter.py
```

### Model Management

Whisper models are automatically downloaded on first run:
- Model: kotoba-tech/kotoba-whisper-v2.2
- Size: ~1.5GB
- Location: Cached in Hugging Face cache directory
- GPU Memory: Requires ~2-4GB VRAM for optimal performance

## Supported Formats

### Audio Files (9 formats)
- MP3 (`.mp3`) - Standard compressed audio
- WAV (`.wav`) - Uncompressed audio
- M4A (`.m4a`) - Apple audio format
- FLAC (`.flac`) - Lossless compression
- OGG (`.ogg`) - Vorbis audio
- AAC (`.aac`) - High-quality compression
- WMA (`.wma`) - Windows Media Audio
- OPUS (`.opus`) - High-efficiency codec
- AMR (`.amr`) - Mobile phone recording

### Video Files (6 formats - audio extraction)
- MP4 (`.mp4`) - Standard video
- AVI (`.avi`) - Windows video
- MOV (`.mov`) - QuickTime video
- MKV (`.mkv`) - Matroska video
- 3GP (`.3gp`) - Mobile phone video
- WEBM (`.webm`) - Web video

## Key Services and Interfaces

### TranscriptionEngine
```python
class TranscriptionEngine:
    def __init__(self, model_name: str = "kotoba-tech/kotoba-whisper-v2.2")
    def load_model(self) -> None
    def transcribe(self, audio_path: str, chunk_length_s: int = 15,
                   add_punctuation: bool = True,
                   return_timestamps: bool = True) -> Dict[str, Any]
    def is_available(self) -> bool
```

### TextFormatter
```python
class TextFormatter:
    def remove_fillers(self, text: str, aggressive: bool = False) -> str
    def add_punctuation(self, text: str) -> str
    def format_paragraphs(self, text: str, sentences_per_paragraph: int = 3) -> str
    def clean_repeated_words(self, text: str) -> str
    def format_numbers(self, text: str) -> str
    def format_all(self, text: str, remove_fillers: bool = True,
                   add_punctuation: bool = True,
                   format_paragraphs: bool = True,
                   clean_repeated: bool = True) -> str
```

### TranscriptionWorker (QThread)
```python
class TranscriptionWorker(QThread):
    # Signals
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, audio_path: str)
    def run(self) -> None
```

## Configuration

### ffmpeg Path Configuration
The application automatically configures ffmpeg PATH in `transcription_engine.py`:
```python
ffmpeg_path = r"C:\ffmpeg\ffmpeg-8.0-essentials_build\bin"
```
Modify this path if ffmpeg is installed in a different location.

### Transcription Parameters
In `transcription_engine.py`:
- `chunk_length_s`: Audio chunk size (default: 15 seconds)
- `language`: "ja" (Japanese)
- `task`: "transcribe"
- `device`: Auto-detected (CUDA 0 or CPU)

### Text Formatting Options
In `text_formatter.py`:
- `FILLER_WORDS`: List of 19 Japanese filler words
- `sentences_per_paragraph`: 3 sentences per paragraph (default)
- Punctuation rules for Japanese grammar

## Special Considerations

### Performance
- **CPU Mode**: Slower but works without GPU (~5-10x real-time)
- **GPU Mode**: Fast transcription (~1-2x real-time with CUDA)
- **Memory Usage**:
  - CPU: 2-4GB RAM
  - GPU: 2-4GB VRAM + 2GB RAM
- **Chunk Processing**: Handles long audio files via chunking

### Japanese Language Optimization
- kotoba-whisper v2.2 is specifically trained for Japanese
- Better accuracy than standard Whisper for Japanese audio
- Handles multiple Japanese dialects
- Text formatting follows Japanese grammar rules

### Threading and UI Responsiveness
- Transcription runs in separate QThread (TranscriptionWorker)
- Progress updates via pyqtSignal (20%, 50%, 90%, 100%)
- Non-blocking UI during processing
- Error handling with user-friendly messages

### Text Post-Processing Pipeline
Order of operations in `format_all()`:
1. Remove filler words
2. Clean repeated words
3. Add punctuation
4. Format numbers
5. Format paragraphs

## Development Notes

### Adding New Features
When adding features, follow these patterns:
1. **New services**: Create separate module in `src/`
2. **UI changes**: Modify `main.py` MainWindow class
3. **Worker threads**: Extend TranscriptionWorker or create new QThread
4. **Text processing**: Add methods to TextFormatter class

### Error Handling
- All errors logged via Python logging module
- User-facing errors shown via QMessageBox
- Transcription errors caught in TranscriptionWorker.run()
- GUI errors handled in MainWindow methods

### Logging Configuration
```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## Common Issues and Solutions

### Issue: ffmpeg not found
**Error**: "ffmpeg was not found but is required to load audio files from filename"
**Solution**: Run `install-ffmpeg.ps1` script or manually install ffmpeg and add to PATH

### Issue: CUDA not detected
**Check**: `python -c "import torch; print(torch.cuda.is_available())"`
**Solution**: Reinstall PyTorch with correct CUDA version

### Issue: Model download slow
**Cause**: kotoba-whisper v2.2 is ~1.5GB
**Solution**: Wait for initial download, subsequent runs use cached model

### Issue: Memory error
**Solutions**:
- Use CPU mode instead of GPU
- Split long audio files into shorter segments
- Reduce `chunk_length_s` parameter

### Issue: Poor transcription quality
**Solutions**:
- Ensure audio quality is good (clear speech, low background noise)
- Use WAV or FLAC format instead of compressed formats
- Check audio file is in Japanese language

## Future Development Plans

### Planned Features
- Speaker diarization (pyannote.audio integration)
- Batch processing multiple files
- Export to DOCX/Excel formats
- Real-time transcription from microphone
- Custom vocabulary support
- Timestamp export

### Technical Debt
- Add comprehensive test suite (pytest)
- Implement configuration file (YAML/JSON)
- Add CLI interface alongside GUI
- Implement model switching (different Whisper variants)
- Add progress estimation for long files

## References

- [kotoba-whisper v2.2 - Hugging Face](https://huggingface.co/kotoba-tech/kotoba-whisper-v2.2)
- [PyQt5 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt5/)
- [Transformers Documentation](https://huggingface.co/docs/transformers)
- [PyTorch Documentation](https://pytorch.org/docs/)
- [ffmpeg Documentation](https://ffmpeg.org/documentation.html)

## Support

For issues specific to this application, check:
1. Application logs in console output
2. README.md for user-facing documentation
3. GitHub Issues (if repository is public)

For dependency issues, consult official documentation:
- PyQt5: Qt and PyQt5 forums
- Whisper/Transformers: Hugging Face forums
- PyTorch: PyTorch forums
