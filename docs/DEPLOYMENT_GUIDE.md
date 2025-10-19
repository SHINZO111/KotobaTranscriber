# KotobaTranscriber Deployment Guide

**Version:** 1.0.0
**Last Updated:** 2025-10-18
**Target Audience:** System Administrators, DevOps Engineers, Advanced Users

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Installation Steps](#2-installation-steps)
3. [Configuration](#3-configuration)
4. [Security Checklist](#4-security-checklist)
5. [Performance Tuning](#5-performance-tuning)
6. [Monitoring and Logging](#6-monitoring-and-logging)
7. [Troubleshooting](#7-troubleshooting)
8. [Upgrade Guide](#8-upgrade-guide)
9. [Production Deployment](#9-production-deployment)
10. [Post-Deployment Validation](#10-post-deployment-validation)

---

## 1. Prerequisites

### 1.1 Python Version Requirements

- **Minimum:** Python 3.8+
- **Recommended:** Python 3.10+ or 3.11+
- **Tested:** Python 3.13.7

**Check Python Version:**
```bash
python --version
# or
python3 --version
```

**Installation:**
- Windows: Download from [python.org](https://www.python.org/downloads/)
- macOS: `brew install python@3.11`
- Linux: `sudo apt-get install python3.11 python3.11-venv`

### 1.2 System Requirements

#### Minimum Requirements (CPU Mode)
- **CPU:** 4+ cores (x64 architecture)
- **RAM:** 8 GB
- **Storage:** 5 GB free space
- **OS:** Windows 10/11, macOS 10.15+, Ubuntu 20.04+

#### Recommended Requirements (GPU Mode)
- **CPU:** 6+ cores
- **RAM:** 16 GB
- **GPU:** NVIDIA GPU with 4GB+ VRAM (CUDA 11.8 or 12.x compatible)
- **Storage:** 10 GB free space (models + cache)
- **OS:** Windows 10/11 with latest GPU drivers

#### GPU Requirements
- **NVIDIA GPU** with compute capability 3.5+
- **CUDA Toolkit:** 11.8 or 12.x
- **cuDNN:** Compatible with CUDA version
- **Driver Version:** 450.80.02+ (Linux), 452.39+ (Windows)

**Check GPU:**
```bash
# Windows
nvidia-smi

# Linux/macOS
nvidia-smi
```

### 1.3 Dependencies

#### System Dependencies

**Windows:**
- [Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)
- [.NET Framework 4.7.2+](https://dotnet.microsoft.com/download/dotnet-framework)

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    portaudio19-dev \
    python3-pyaudio \
    libasound2-dev \
    libsndfile1
```

**macOS:**
```bash
brew install portaudio
brew install ffmpeg
```

#### Python Dependencies

Core dependencies are listed in `requirements.txt`:
- PyQt5 5.15.0+
- transformers 4.30.0+
- torch 2.0.0+
- librosa 0.10.0+
- faster-whisper 1.0.0+
- speechbrain 0.5.0+ (optional, for speaker diarization)

Development dependencies in `requirements-dev.txt`:
- pytest 7.4.0+
- black 23.12.0+
- ruff 0.1.9+
- mypy 1.8.0+

### 1.4 ffmpeg Installation

ffmpeg is **required** for audio format conversion.

#### Windows

**Option 1: Automated Script**
```powershell
# Download from https://www.gyan.dev/ffmpeg/builds/
# Extract to C:\ffmpeg\ffmpeg-8.0-essentials_build
```

**Option 2: Package Manager**
```powershell
# Using Chocolatey
choco install ffmpeg

# Using Scoop
scoop install ffmpeg
```

**Verify Installation:**
```cmd
ffmpeg -version
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

#### macOS
```bash
brew install ffmpeg
```

**Important:** Note the installation path - you'll need it for `config.yaml`.

---

## 2. Installation Steps

### 2.1 Clone Repository

```bash
# Clone the repository
git clone https://github.com/yourusername/KotobaTranscriber.git
cd KotobaTranscriber

# Or download and extract ZIP
# https://github.com/yourusername/KotobaTranscriber/archive/refs/heads/main.zip
```

### 2.2 Virtual Environment Setup

**Create Virtual Environment:**

```bash
# Windows
python -m venv venv

# Linux/macOS
python3 -m venv venv
```

**Activate Virtual Environment:**

```bash
# Windows (Command Prompt)
venv\Scripts\activate

# Windows (PowerShell)
venv\Scripts\Activate.ps1

# Linux/macOS
source venv/bin/activate
```

**Verify Activation:**
```bash
which python  # Linux/macOS
where python  # Windows
# Should show path inside venv folder
```

### 2.3 Dependency Installation

#### Option 1: GPU Installation (CUDA 11.8)

```bash
# Install PyTorch with CUDA 11.8
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Install remaining dependencies
pip install -r requirements.txt

# Verify CUDA availability
python -c "import torch; print(f'CUDA Available: {torch.cuda.is_available()}')"
```

#### Option 2: GPU Installation (CUDA 12.x)

**Windows - Automated CUDA Installation:**
```powershell
# Run as Administrator
powershell -ExecutionPolicy Bypass -File install-cuda.ps1
```

**Manual CUDA Installation:**
```bash
# Install PyTorch with CUDA 12.1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install remaining dependencies
pip install -r requirements.txt
```

#### Option 3: CPU Installation

```bash
# Install CPU-only PyTorch
pip install torch torchvision torchaudio

# Install remaining dependencies
pip install -r requirements.txt
```

#### Development Installation

```bash
# Install all dependencies including dev tools
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### 2.4 Configuration Setup

**Create Configuration File:**

```bash
# Copy example configuration
cp config/config.example.yaml config/config.yaml

# Edit configuration (see section 3 for details)
# Windows: notepad config/config.yaml
# Linux/macOS: nano config/config.yaml
```

**Key Configuration Items:**
1. ffmpeg path (`audio.ffmpeg.path`)
2. Device selection (`model.whisper.device`)
3. Logging level (`logging.level`)
4. Output directory (`output.save_directory`)

### 2.5 First-Time Model Download

The kotoba-whisper model (~1.5 GB) will be automatically downloaded on first run.

**Pre-download Model (Optional):**

```python
# Download model ahead of time
python -c "
from transformers import pipeline
pipe = pipeline('automatic-speech-recognition',
                model='kotoba-tech/kotoba-whisper-v2.2')
print('Model downloaded successfully')
"
```

**Model Cache Location:**
- Windows: `C:\Users\<username>\.cache\huggingface\hub`
- Linux: `~/.cache/huggingface/hub`
- macOS: `~/.cache/huggingface/hub`

### 2.6 Directory Structure Setup

**Create Required Directories:**

```bash
# Create output and log directories
mkdir -p logs
mkdir -p results
mkdir -p models
mkdir -p config

# Verify structure
ls -la
```

**Expected Structure:**
```
KotobaTranscriber/
├── config/
│   ├── config.yaml           # Main configuration
│   ├── config.example.yaml   # Configuration template
│   └── logging.yaml          # Logging configuration
├── src/                      # Source code
├── tests/                    # Test files
├── logs/                     # Application logs
├── results/                  # Transcription outputs
├── models/                   # Local model cache (optional)
├── venv/                     # Virtual environment
├── requirements.txt          # Dependencies
└── requirements-dev.txt      # Dev dependencies
```

---

## 3. Configuration

### 3.1 Main Configuration (config.yaml)

The main configuration file controls all application behavior.

**Location:** `config/config.yaml`

#### 3.1.1 Application Settings

```yaml
app:
  name: "KotobaTranscriber"
  version: "1.0.0"
  language: "ja"  # ja (Japanese), en (English)
  encoding: "utf-8"
```

#### 3.1.2 Model Settings

```yaml
model:
  whisper:
    name: "kotoba-tech/kotoba-whisper-v2.2"
    device: "auto"  # Options: auto, cuda, cpu
    chunk_length_s: 15  # Audio chunk size in seconds
    task: "transcribe"  # transcribe or translate
    language: "ja"
    return_timestamps: true

  faster_whisper:
    model_size: "base"  # tiny, base, small, medium, large-v2, large-v3
    compute_type: "auto"  # int8, int8_float16, float16, float32, auto
    beam_size: 5
    device: "auto"
    download_root: null
    local_files_only: false
```

**Model Size Comparison:**

| Model Size | Parameters | VRAM (GPU) | RAM (CPU) | Speed | Accuracy |
|------------|------------|------------|-----------|-------|----------|
| tiny       | 39M        | ~1 GB      | ~1 GB     | 6x    | Good     |
| base       | 74M        | ~1 GB      | ~1 GB     | 5x    | Better   |
| small      | 244M       | ~2 GB      | ~2 GB     | 3x    | Very Good|
| medium     | 769M       | ~5 GB      | ~5 GB     | 2x    | Excellent|
| large-v2   | 1550M      | ~10 GB     | ~10 GB    | 1x    | Best     |

#### 3.1.3 Audio Processing

```yaml
audio:
  ffmpeg:
    path: "C:\\ffmpeg\\ffmpeg-8.0-essentials_build\\bin"  # Windows
    # path: "/usr/local/bin"  # macOS/Linux
    auto_configure: true

  preprocessing:
    enabled: false  # Recommended: false (avoids meta tensor errors)
    noise_reduction: false
    normalize: false
    remove_silence: false
```

> **Warning:** Audio preprocessing (`enabled: true`) may cause "meta tensor" errors in some environments. Keep it disabled unless specifically needed.

#### 3.1.4 Text Formatting

```yaml
formatting:
  remove_fillers: true  # Remove filler words (あー, えー, etc.)
  add_punctuation: true  # Add Japanese punctuation
  format_paragraphs: true  # Structure into paragraphs
  clean_repeated_words: true  # Remove word repetitions
  format_numbers: false  # Convert numbers to Japanese
  sentences_per_paragraph: 3  # Sentences per paragraph
```

#### 3.1.5 Error Handling

```yaml
error_handling:
  max_retries: 3  # Maximum retry attempts
  retry_delay: 1.0  # Delay between retries (seconds)
  backoff_multiplier: 2.0  # Exponential backoff multiplier
  max_consecutive_errors: 5  # Max errors before stopping
  error_cooldown_time: 2.0  # Cooldown after error (seconds)
  fallback_to_cpu: true  # Auto-fallback to CPU on GPU error
  continue_on_error: true  # Continue batch processing on errors
```

#### 3.1.6 Performance Settings

```yaml
performance:
  thread_pool_size: 4  # Worker threads for parallel processing
  max_queue_size: 100  # Max items in processing queue
  cache_size: 1000  # Pattern cache size
  cache_ttl: 3600  # Cache time-to-live (seconds)
  max_memory_usage_mb: 4096  # Max memory usage limit
  gc_threshold: 0.8  # Garbage collection threshold (0.0-1.0)
  batch_size: 10  # Batch processing size
  max_concurrent_transcriptions: 2  # Max simultaneous transcriptions
```

#### 3.1.7 Logging Configuration

```yaml
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  format: "text"  # text, json

  file:
    enabled: true
    path: "logs/app.log"
    rotation: "1 day"  # 1 day, 1 week, 100 MB
    retention: "30 days"  # Log retention period
    encoding: "utf-8"

  console:
    enabled: true
    colored: true

  format_template: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### 3.2 Logging Configuration (logging.yaml)

Advanced logging configuration for structured logging.

**Location:** `config/logging.yaml`

```yaml
version: 1
disable_existing_loggers: false

default_level: INFO

# File configuration
file:
  path: logs/app.log
  max_size: 10485760  # 10MB
  backup_count: 5
  level: INFO

# Console configuration
console:
  enabled: true
  level: INFO
  colorize: true

# Module-specific log levels
loggers:
  __main__:
    level: INFO
  transcription_engine:
    level: INFO
  realtime_transcriber:
    level: INFO

# External library log levels
external_loggers:
  transformers:
    level: WARNING
  torch:
    level: WARNING
  urllib3:
    level: WARNING

# Security settings
security:
  mask_sensitive: true
  sensitive_keywords:
    - password
    - token
    - secret
    - api_key
```

### 3.3 ffmpeg Path Configuration

#### Finding ffmpeg Path

**Windows:**
```cmd
where ffmpeg
# Output: C:\ffmpeg\ffmpeg-8.0-essentials_build\bin\ffmpeg.exe
```

**Linux/macOS:**
```bash
which ffmpeg
# Output: /usr/local/bin/ffmpeg
```

#### Configuring ffmpeg Path

**Edit config.yaml:**
```yaml
audio:
  ffmpeg:
    # Windows - use double backslashes or forward slashes
    path: "C:\\ffmpeg\\ffmpeg-8.0-essentials_build\\bin"
    # or
    path: "C:/ffmpeg/ffmpeg-8.0-essentials_build/bin"

    # Linux/macOS
    # path: "/usr/local/bin"

    auto_configure: true  # Automatically add to PATH
```

### 3.4 Device Selection (CUDA/CPU)

#### Auto-Detection (Recommended)

```yaml
model:
  whisper:
    device: "auto"  # Automatically selects best available device
```

#### Manual Selection

```yaml
model:
  whisper:
    device: "cuda"  # Force GPU
    # device: "cuda:0"  # Specific GPU (multi-GPU systems)
    # device: "cpu"  # Force CPU
```

#### Verify Device Selection

```python
python -c "
import torch
print(f'CUDA Available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)}')
    print(f'VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB')
"
```

### 3.5 Custom Vocabulary Configuration

Enable custom vocabulary for domain-specific terms.

**Create custom_vocabulary.json:**
```json
{
  "enabled": true,
  "replacements": {
    "かたかな": "カタカナ",
    "ひらがな": "ひらがな",
    "かんじ": "漢字"
  }
}
```

**Enable in config.yaml:**
```yaml
vocabulary:
  enabled: true
  file: "custom_vocabulary.json"
```

### 3.6 Environment Variables (Optional)

For sensitive configuration, use environment variables.

**Create .env file:**
```bash
# .env (root directory)
KOTOBA_DEVICE=cuda
KOTOBA_LOG_LEVEL=INFO
KOTOBA_FFMPEG_PATH=C:/ffmpeg/bin
KOTOBA_MODEL_CACHE=/path/to/model/cache

# LLM API Keys (if using correction feature)
OPENAI_API_KEY=sk-your-api-key-here
ANTHROPIC_API_KEY=your-anthropic-key
```

**Load in application:**
```python
# Already implemented in config_manager.py
import os
device = os.getenv('KOTOBA_DEVICE', 'auto')
```

---

## 4. Security Checklist

### 4.1 Path Validation

Verify path validation is enabled to prevent directory traversal attacks.

**Check validators.py:**
```python
# Verify this function exists and is called
def validate_file_path(
    path: str,
    must_exist: bool = False,
    allowed_extensions: Optional[List[str]] = None,
    base_directory: Optional[str] = None
) -> Path:
    """
    Validates file path with security checks:
    - Path traversal prevention (.., symlinks)
    - Extension whitelist
    - Base directory restriction
    """
    # Implementation should include:
    # 1. Path.resolve() to resolve symlinks
    # 2. Check for '..' in path
    # 3. Verify within base_directory
    # 4. Check file extension
```

**Verify Usage:**
```bash
# Search for validation usage
grep -r "validate_file_path" src/

# Expected locations:
# - src/main.py (file selection)
# - src/transcription_engine.py (audio file validation)
# - src/batch_processor.py (batch file validation)
```

### 4.2 ffmpeg Whitelist Paths

Ensure ffmpeg only operates on validated audio files.

**Check ffmpeg Configuration:**
```yaml
# config/config.yaml
audio:
  ffmpeg:
    path: "C:\\ffmpeg\\bin"  # Fixed, trusted path
    auto_configure: true

    # Additional security (if implemented)
    whitelist_paths:
      - "C:\\Users\\*\\Documents"
      - "D:\\AudioFiles"

    # Forbidden paths (example)
    blacklist_paths:
      - "C:\\Windows"
      - "C:\\Program Files"
```

**Verify ffmpeg Invocation:**
```python
# Check transcription_engine.py or audio_preprocessor.py
# Should use absolute paths only
import subprocess

def process_audio(audio_path: str):
    # GOOD - Validated path
    validated_path = Validator.validate_file_path(audio_path, must_exist=True)
    result = subprocess.run([ffmpeg_path, '-i', str(validated_path), ...])

    # BAD - User input directly
    # result = subprocess.run([ffmpeg_path, '-i', audio_path, ...])  # Vulnerable!
```

### 4.3 File Permissions

Set appropriate file permissions for logs and output files.

**Windows (PowerShell):**
```powershell
# Restrict log directory to current user
icacls logs /inheritance:r
icacls logs /grant:r "$env:USERNAME:(OI)(CI)F"

# Restrict config directory
icacls config /inheritance:r
icacls config /grant:r "$env:USERNAME:(OI)(CI)F"
```

**Linux/macOS:**
```bash
# Restrict log directory
chmod 700 logs
chmod 600 logs/*.log

# Restrict config files
chmod 600 config/config.yaml
chmod 600 config/logging.yaml

# Make executable scripts read-only
chmod 500 start.bat install.bat
```

### 4.4 Configuration File Security

Protect sensitive configuration data.

**Check config.yaml Permissions:**
```bash
# Should not be world-readable
ls -la config/config.yaml

# Expected (Linux/macOS): -rw------- (600)
# Expected (Windows): Only owner has full control
```

**Sensitive Data Protection:**
```yaml
# DON'T store API keys in config files
advanced:
  llm_correction:
    api_key: null  # Use environment variable instead

# DO use environment variables
# In .env or system environment
OPENAI_API_KEY=sk-your-key
```

**Verify .gitignore:**
```bash
# Check .gitignore includes sensitive files
cat .gitignore | grep -E '(\.env|config\.yaml|\.log|api_key)'

# Should include:
# .env
# config/config.yaml
# logs/*.log
# *.key
```

### 4.5 Dependency Security Scan

Run security scans on dependencies.

**Install Security Tools:**
```bash
pip install safety bandit
```

**Scan Dependencies:**
```bash
# Check for known vulnerabilities
safety check --json

# Expected output: No known security vulnerabilities
```

**Scan Code for Security Issues:**
```bash
# Run Bandit security linter
bandit -r src/ -f json -o security-report.json

# Review report for:
# - Hardcoded passwords
# - SQL injection (not applicable)
# - Command injection
# - Path traversal
```

### 4.6 Model Cache Security

Protect downloaded model files from tampering.

**Set Model Cache Permissions:**
```bash
# Windows (PowerShell)
$cachePath = "$env:USERPROFILE\.cache\huggingface\hub"
icacls $cachePath /inheritance:r
icacls $cachePath /grant:r "$env:USERNAME:(OI)(CI)F"

# Linux/macOS
chmod -R 700 ~/.cache/huggingface/hub
```

**Verify Model Integrity (Optional):**
```python
# Check model SHA256 hash
import hashlib

def verify_model_file(file_path, expected_hash):
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest() == expected_hash
```

### 4.7 Network Security

Configure firewall rules if network access is needed.

**Windows Firewall:**
```powershell
# Allow Python for model downloads (if needed)
New-NetFirewallRule -DisplayName "Python - KotobaTranscriber" `
    -Direction Outbound `
    -Program "C:\path\to\venv\Scripts\python.exe" `
    -Action Allow
```

**Linux (UFW):**
```bash
# Allow HTTPS for model downloads
sudo ufw allow out 443/tcp comment 'HuggingFace model downloads'
```

### 4.8 Security Validation Checklist

- [ ] Path validation enabled in all file operations
- [ ] ffmpeg uses whitelisted paths only
- [ ] File permissions set correctly (logs, config)
- [ ] No API keys in version control
- [ ] .gitignore includes sensitive files
- [ ] Dependency security scan passed
- [ ] Model cache protected
- [ ] No hardcoded credentials in code
- [ ] Input validation on all user inputs
- [ ] Error messages don't expose system paths

**Run Complete Security Audit:**
```bash
# Run all security checks
python -m pytest tests/test_security.py -v

# Expected: All tests pass
```

---

## 5. Performance Tuning

### 5.1 GPU vs CPU Selection

#### GPU Mode (Recommended for Production)

**Advantages:**
- 5-10x faster transcription
- Better for real-time processing
- Handles long audio files efficiently

**Configuration:**
```yaml
model:
  whisper:
    device: "cuda"
  faster_whisper:
    device: "cuda"
    compute_type: "float16"  # Best GPU performance
```

**Verify GPU Usage:**
```bash
# Monitor GPU usage during transcription
nvidia-smi -l 1

# Expected: GPU utilization 80-100%
# Expected: Memory usage 2-4 GB (base model)
```

#### CPU Mode (Development/Low-Resource)

**Advantages:**
- Works without GPU
- Lower power consumption
- No CUDA dependencies

**Configuration:**
```yaml
model:
  whisper:
    device: "cpu"
  faster_whisper:
    device: "cpu"
    compute_type: "int8"  # Best CPU performance
```

#### Mixed Mode (Optimal)

Use faster-whisper on GPU for real-time, standard whisper on CPU for batch.

```yaml
model:
  whisper:
    device: "cpu"  # Batch processing
  faster_whisper:
    device: "cuda"  # Real-time processing
    compute_type: "float16"
```

### 5.2 Memory Optimization

#### Configure Memory Limits

```yaml
performance:
  max_memory_usage_mb: 4096  # 4 GB limit
  gc_threshold: 0.8  # Trigger GC at 80% usage

  # Clear GPU cache aggressively
  clear_gpu_cache_frequency: 10  # Every 10 files
```

#### Enable Memory Monitoring

```python
# Check if memory_optimizer.py is being used
from memory_optimizer import MemoryOptimizer

optimizer = MemoryOptimizer(
    max_memory_mb=4096,
    check_interval=10.0,
    gpu_memory_fraction=0.8
)
optimizer.start_monitoring()
```

#### Manual Memory Management

```bash
# Monitor memory usage
# Windows
tasklist | findstr python

# Linux
ps aux | grep python
top -p $(pgrep python)

# macOS
ps aux | grep python
top -pid $(pgrep python)
```

### 5.3 Batch Processing Settings

Optimize batch processing for throughput.

**Configuration:**
```yaml
performance:
  batch_size: 10  # Process 10 files at a time
  max_concurrent_transcriptions: 2  # Parallel workers
  thread_pool_size: 4  # Thread pool for I/O
```

**Recommended Settings by Hardware:**

| Hardware Config | batch_size | max_concurrent | thread_pool_size |
|-----------------|------------|----------------|------------------|
| CPU only        | 5          | 1              | 2                |
| Low-end GPU     | 10         | 2              | 4                |
| Mid-range GPU   | 20         | 4              | 8                |
| High-end GPU    | 50         | 8              | 16               |

### 5.4 Chunk Size Optimization

Adjust audio chunk size for performance vs accuracy.

```yaml
model:
  whisper:
    chunk_length_s: 15  # Default: 15 seconds
```

**Chunk Size Guidelines:**

| Chunk Size | Speed | Accuracy | Memory | Use Case |
|------------|-------|----------|--------|----------|
| 5s         | Fast  | Lower    | Low    | Real-time, noisy audio |
| 15s        | Balanced | Good | Medium | General purpose |
| 30s        | Slower | Best | High   | High-quality, clear audio |

### 5.5 Regular Expression Cache Warming

Pre-compile regex patterns for text formatting.

**Check text_formatter.py:**
```python
# Should have pattern caching
import re
from functools import lru_cache

@lru_cache(maxsize=128)
def _compile_pattern(pattern: str) -> re.Pattern:
    return re.compile(pattern)

class TextFormatter:
    def __init__(self):
        # Pre-warm cache with common patterns
        self._warm_pattern_cache()

    def _warm_pattern_cache(self):
        """Pre-compile frequently used patterns"""
        common_patterns = [
            r'[、。]',
            r'\s+',
            r'[あー|えー|その]',
            # ... more patterns
        ]
        for pattern in common_patterns:
            _compile_pattern(pattern)
```

**Verify Cache Usage:**
```python
# Test pattern cache performance
from text_formatter import TextFormatter
import time

formatter = TextFormatter()

# Warm cache
text = "テスト文章です。あー、それで、えー、その..."
_ = formatter.format_all(text)

# Time with cache
start = time.time()
for _ in range(1000):
    _ = formatter.format_all(text)
duration = time.time() - start

print(f"1000 iterations: {duration:.2f}s")
# Expected: < 1 second with cache, > 5 seconds without
```

### 5.6 Model Selection Optimization

Choose the right model size for your use case.

**Performance Comparison:**

| Model | Speed (RTF) | VRAM | Accuracy | Latency | Best For |
|-------|-------------|------|----------|---------|----------|
| tiny  | 0.15x       | 1GB  | 80%      | 100ms   | Real-time preview |
| base  | 0.20x       | 1GB  | 85%      | 150ms   | Real-time production |
| small | 0.35x       | 2GB  | 90%      | 300ms   | Batch processing |
| medium| 0.50x       | 5GB  | 95%      | 500ms   | High-accuracy batch |
| large | 1.00x       | 10GB | 98%      | 1000ms  | Maximum accuracy |

RTF = Real-Time Factor (0.20x = 5x faster than real-time)

**Switch Models Based on Mode:**

```yaml
# Real-time mode: faster-whisper base
realtime:
  model_size: "base"
  compute_type: "float16"

# Batch mode: standard whisper small
batch:
  model_size: "small"
  compute_type: "float32"
```

### 5.7 I/O Optimization

Optimize file I/O for large audio files.

```yaml
performance:
  # Use memory-mapped file reading
  use_mmap: true

  # Increase read buffer size
  read_buffer_size: 8192  # 8 KB

  # Enable async I/O
  async_io: true
```

### 5.8 Network Optimization (Model Downloads)

Speed up model downloads on first run.

```bash
# Use mirror for faster downloads (China)
export HF_ENDPOINT=https://hf-mirror.com

# Or set in code
import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
```

### 5.9 Performance Benchmarking

Run performance benchmarks to measure improvements.

```bash
# Run performance tests
pytest tests/test_performance.py --benchmark-only

# Generate performance report
pytest tests/test_performance.py --benchmark-autosave
```

**Expected Benchmarks (Base Model, GPU):**

| Test | Expected Time | Threshold |
|------|---------------|-----------|
| Model Load | < 5s | 10s |
| Transcribe 1min audio | < 10s | 20s |
| Batch 10 files | < 60s | 120s |
| Format 1000 chars | < 0.1s | 0.5s |

### 5.10 Optimization Checklist

- [ ] GPU mode enabled for production
- [ ] Memory limits configured appropriately
- [ ] Batch size optimized for hardware
- [ ] Chunk size set for use case
- [ ] Pattern cache warmed on startup
- [ ] Correct model size selected
- [ ] I/O buffering enabled
- [ ] Performance benchmarks passing
- [ ] GPU utilization > 80% during transcription
- [ ] CPU usage < 50% during idle

---

## 6. Monitoring and Logging

### 6.1 Log File Locations

Default log file locations:

**Application Logs:**
- Location: `logs/app.log`
- Rotation: Daily or 10 MB
- Retention: 30 days (5 backups)

**Log File Structure:**
```
logs/
├── app.log               # Current log
├── app.log.1             # Yesterday's log
├── app.log.2             # 2 days ago
├── app.log.3
├── app.log.4
└── app.log.5             # Oldest (30 days ago)
```

### 6.2 Log Levels Configuration

Configure appropriate log levels for different environments.

#### Development Environment
```yaml
logging:
  level: "DEBUG"  # Show all logs

  console:
    enabled: true
    colored: true
    level: "DEBUG"

  file:
    enabled: true
    level: "DEBUG"
```

#### Production Environment
```yaml
logging:
  level: "INFO"  # Hide debug messages

  console:
    enabled: false  # Disable console in production

  file:
    enabled: true
    level: "INFO"
```

#### Error Investigation
```yaml
logging:
  level: "ERROR"  # Only errors

  file:
    level: "ERROR"
    path: "logs/errors.log"
```

### 6.3 Structured Logging (JSON Format)

Enable JSON logging for log aggregation tools.

**Enable JSON Logging:**
```yaml
logging:
  format: "json"  # Instead of "text"

  format_template: null  # Not used in JSON mode
```

**JSON Log Example:**
```json
{
  "timestamp": "2025-10-18T07:00:00.123Z",
  "level": "INFO",
  "logger": "transcription_engine",
  "message": "Transcription completed successfully",
  "file_path": "/path/to/audio.wav",
  "processing_time": 8.45,
  "model": "kotoba-whisper-v2.2",
  "device": "cuda:0",
  "correlation_id": "tx-12345"
}
```

### 6.4 Performance Metrics

Monitor application performance metrics.

**Built-in Metrics:**
```python
# Check performance_monitor.py usage
from performance_monitor import PerformanceMonitor

monitor = PerformanceMonitor()
monitor.start_monitoring()

# Metrics collected:
# - Transcription time per file
# - Average processing speed (RTF)
# - Memory usage (CPU and GPU)
# - Error rate
# - Queue depth
```

**Metrics Log Location:** `logs/metrics.log`

**Metrics Format:**
```
2025-10-18 07:00:00 | file_processed | audio1.wav | 8.45s | success
2025-10-18 07:00:10 | file_processed | audio2.wav | 7.23s | success
2025-10-18 07:00:20 | batch_complete | 10 files | 82.3s | 9 success, 1 failed
```

### 6.5 Error Tracking

Configure error tracking for production monitoring.

**Error Log Configuration:**
```yaml
logging:
  error_file:
    enabled: true
    path: "logs/errors.log"
    level: "ERROR"
    include_traceback: true
```

**Error Categories:**
- **Critical:** Application crash, model load failure
- **Error:** File processing failure, transcription error
- **Warning:** Diarization failure, formatting issue

**Example Error Log Entry:**
```
2025-10-18 07:00:00 - ERROR - transcription_engine - Transcription failed: /path/to/audio.wav
Traceback (most recent call last):
  File "transcription_engine.py", line 123, in transcribe
    result = self.pipe(audio_path)
  ...
TranscriptionFailedError: CUDA out of memory
```

### 6.6 Real-time Monitoring

Monitor application in real-time during operation.

**Watch Logs (Linux/macOS):**
```bash
# Follow application log
tail -f logs/app.log

# Follow errors only
tail -f logs/app.log | grep ERROR

# Follow with highlighting
tail -f logs/app.log | grep --color=auto -E 'ERROR|WARNING|$'
```

**Watch Logs (Windows PowerShell):**
```powershell
# Follow application log
Get-Content logs\app.log -Wait -Tail 50

# Follow errors only
Get-Content logs\app.log -Wait | Select-String "ERROR"
```

**Monitor GPU Usage:**
```bash
# Continuous GPU monitoring
nvidia-smi -l 1

# Watch specific GPU
watch -n 1 nvidia-smi

# Log GPU usage to file
nvidia-smi --query-gpu=timestamp,name,utilization.gpu,utilization.memory,memory.used --format=csv -l 5 > logs/gpu_usage.log
```

**Monitor System Resources:**
```bash
# Linux
htop
# or
top -p $(pgrep python)

# Windows
# Task Manager > Details > Find python.exe

# macOS
top -pid $(pgrep python)
```

### 6.7 Log Analysis Tools

Tools for analyzing application logs.

#### Log Aggregation (ELK Stack)

```bash
# Install Filebeat for log forwarding
# /etc/filebeat/filebeat.yml
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - F:\KotobaTranscriber\logs\*.log
  json.keys_under_root: true
  json.add_error_key: true

output.elasticsearch:
  hosts: ["localhost:9200"]
```

#### Log Parsing (Python)

```python
# analyze_logs.py
import re
from collections import Counter

def analyze_logs(log_file):
    errors = []
    warnings = []
    processing_times = []

    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            if 'ERROR' in line:
                errors.append(line)
            elif 'WARNING' in line:
                warnings.append(line)

            # Extract processing time
            match = re.search(r'processing_time["\s:]+(\d+\.\d+)', line)
            if match:
                processing_times.append(float(match.group(1)))

    print(f"Errors: {len(errors)}")
    print(f"Warnings: {len(warnings)}")
    print(f"Avg Processing Time: {sum(processing_times)/len(processing_times):.2f}s")

    return errors, warnings, processing_times

# Usage
errors, warnings, times = analyze_logs('logs/app.log')
```

#### Log Rotation Management

```bash
# Linux - logrotate configuration
# /etc/logrotate.d/kotobaトランスcriber
/path/to/KotobaTranscriber/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 user group
}
```

### 6.8 Alert Configuration

Set up alerts for critical errors.

**Email Alerts (Python):**
```python
# logger.py - Add email handler
import logging
from logging.handlers import SMTPHandler

def setup_email_alerts():
    mail_handler = SMTPHandler(
        mailhost=('smtp.gmail.com', 587),
        fromaddr='alerts@kotobaTranscriber.com',
        toaddrs=['admin@example.com'],
        subject='KotobaTranscriber Critical Error',
        credentials=('user', 'password'),
        secure=()
    )
    mail_handler.setLevel(logging.ERROR)

    logger = logging.getLogger()
    logger.addHandler(mail_handler)
```

**Webhook Alerts (Slack):**
```python
# logger.py - Add Slack webhook
import requests
import logging

class SlackHandler(logging.Handler):
    def __init__(self, webhook_url):
        super().__init__()
        self.webhook_url = webhook_url

    def emit(self, record):
        log_entry = self.format(record)
        requests.post(self.webhook_url, json={
            'text': f':rotating_light: KotobaTranscriber Error\n```{log_entry}```'
        })

# Usage
slack_handler = SlackHandler('https://hooks.slack.com/services/YOUR/WEBHOOK/URL')
slack_handler.setLevel(logging.ERROR)
logger.addHandler(slack_handler)
```

### 6.9 Monitoring Checklist

- [ ] Log files rotating correctly
- [ ] Log retention policy configured
- [ ] JSON logging enabled (if using log aggregation)
- [ ] Error tracking configured
- [ ] Performance metrics being collected
- [ ] Real-time monitoring tools set up
- [ ] Log analysis scripts prepared
- [ ] Alerts configured for critical errors
- [ ] GPU monitoring active (if using GPU)
- [ ] Disk space monitoring for logs

---

## 7. Troubleshooting

### 7.1 Common Issues and Solutions

#### Issue 1: CUDA Loading Errors

**Symptoms:**
```
RuntimeError: CUDA error: no kernel image is available for execution on the device
```

**Solutions:**

**Solution A: Update NVIDIA Drivers**
```bash
# Check current driver version
nvidia-smi

# Update drivers:
# Windows: Download from https://www.nvidia.com/drivers
# Linux: sudo ubuntu-drivers autoinstall
```

**Solution B: Reinstall PyTorch with Correct CUDA Version**
```bash
# Uninstall current PyTorch
pip uninstall torch torchvision torchaudio

# Check CUDA version
nvcc --version

# Install matching PyTorch
# For CUDA 11.8:
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# For CUDA 12.1:
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

**Solution C: Force CPU Mode**
```yaml
# config/config.yaml
model:
  whisper:
    device: "cpu"  # Temporary workaround
```

#### Issue 2: ffmpeg Not Found

**Symptoms:**
```
FileNotFoundError: [WinError 2] The system cannot find the file specified
```
or
```
RuntimeError: ffmpeg was not found but is required to load audio files from filename
```

**Solutions:**

**Solution A: Install ffmpeg**
```bash
# Windows - Download and extract
# https://www.gyan.dev/ffmpeg/builds/
# Extract to C:\ffmpeg

# Linux
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg
```

**Solution B: Configure ffmpeg Path**
```yaml
# config/config.yaml
audio:
  ffmpeg:
    path: "C:\\ffmpeg\\ffmpeg-8.0-essentials_build\\bin"  # Update this
    auto_configure: true
```

**Solution C: Add ffmpeg to System PATH**
```bash
# Windows (PowerShell - Run as Administrator)
$ffmpegPath = "C:\ffmpeg\ffmpeg-8.0-essentials_build\bin"
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";$ffmpegPath", "Machine")

# Linux/macOS
export PATH="/usr/local/bin:$PATH"
# Add to ~/.bashrc or ~/.zshrc for persistence
```

**Verify ffmpeg:**
```bash
ffmpeg -version
# Should show version information
```

#### Issue 3: Memory Errors

**Symptoms:**
```
RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB
```
or
```
MemoryError: Unable to allocate array with shape ...
```

**Solutions:**

**Solution A: Reduce Batch Size**
```yaml
# config/config.yaml
performance:
  batch_size: 5  # Reduce from 10
  max_concurrent_transcriptions: 1  # Reduce from 2
```

**Solution B: Use Smaller Model**
```yaml
model:
  faster_whisper:
    model_size: "tiny"  # Instead of "base" or "small"
    compute_type: "int8"  # Instead of "float16"
```

**Solution C: Enable Memory Optimization**
```yaml
performance:
  max_memory_usage_mb: 2048  # Reduce limit
  gc_threshold: 0.6  # More aggressive garbage collection
```

**Solution D: Clear GPU Cache**
```python
# Add to transcription_engine.py
import torch

def clear_gpu_cache():
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()

# Call after each transcription
def transcribe(self, audio_path):
    result = self.pipe(audio_path)
    clear_gpu_cache()  # Add this
    return result
```

**Solution E: Switch to CPU Mode**
```yaml
model:
  whisper:
    device: "cpu"
```

#### Issue 4: Permission Errors

**Symptoms:**
```
PermissionError: [Errno 13] Permission denied: 'logs/app.log'
```

**Solutions:**

**Solution A: Fix Directory Permissions**
```bash
# Windows (PowerShell - Run as Administrator)
icacls logs /grant "$env:USERNAME:(OI)(CI)F"
icacls results /grant "$env:USERNAME:(OI)(CI)F"

# Linux/macOS
chmod -R 755 logs
chmod -R 755 results
```

**Solution B: Run as Administrator (Windows)**
```bash
# Right-click start.bat > Run as Administrator
```

**Solution C: Change Output Directory**
```yaml
# config/config.yaml
output:
  save_directory: "C:\\Users\\YourUsername\\Documents\\KotobaResults"
```

#### Issue 5: Model Download Slow/Fails

**Symptoms:**
```
ConnectionError: Max retries exceeded with url: ...
```
or very slow download speed.

**Solutions:**

**Solution A: Use Mirror (China Users)**
```bash
# Set environment variable before running
export HF_ENDPOINT=https://hf-mirror.com

# Or in Python
import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
```

**Solution B: Pre-download Model**
```python
# Download model separately with retry
from transformers import pipeline
import time

def download_model_with_retry(max_retries=5):
    for attempt in range(max_retries):
        try:
            print(f"Download attempt {attempt + 1}/{max_retries}")
            pipe = pipeline('automatic-speech-recognition',
                          model='kotoba-tech/kotoba-whisper-v2.2')
            print("Model downloaded successfully!")
            return
        except Exception as e:
            print(f"Failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(10)
            else:
                raise

download_model_with_retry()
```

**Solution C: Manual Download**
```bash
# Download model files manually from HuggingFace
# https://huggingface.co/kotoba-tech/kotoba-whisper-v2.2/tree/main

# Place in: ~/.cache/huggingface/hub/models--kotoba-tech--kotoba-whisper-v2.2/
```

**Solution D: Use Local Model**
```yaml
model:
  whisper:
    name: "/path/to/local/model"
  faster_whisper:
    local_files_only: true
    download_root: "/path/to/models"
```

#### Issue 6: Audio Preprocessing Errors

**Symptoms:**
```
RuntimeError: meta tensor cannot be converted to Python
```

**Solution:**

**Disable Audio Preprocessing (Recommended)**
```yaml
# config/config.yaml
audio:
  preprocessing:
    enabled: false  # Set to false
    noise_reduction: false
    normalize: false
    remove_silence: false
```

This is a known issue with some PyTorch versions. Audio preprocessing is optional.

#### Issue 7: Japanese Text Display Issues

**Symptoms:**
- Garbled text in output files
- Question marks (?) instead of Japanese characters

**Solutions:**

**Solution A: Verify Encoding in Config**
```yaml
app:
  encoding: "utf-8"

output:
  encoding: "utf-8"
```

**Solution B: Open Files with Correct Encoding**
```python
# In code
with open('output.txt', 'w', encoding='utf-8') as f:
    f.write(text)

# When reading
with open('output.txt', 'r', encoding='utf-8') as f:
    text = f.read()
```

**Solution C: Set System Locale**
```bash
# Windows (Control Panel)
# Region > Administrative > Change system locale > Japanese

# Linux
export LANG=ja_JP.UTF-8
export LC_ALL=ja_JP.UTF-8

# macOS
export LANG=ja_JP.UTF-8
```

#### Issue 8: GUI Not Opening

**Symptoms:**
- No window appears when running `start.bat`
- Silent failure

**Solutions:**

**Solution A: Check Python Environment**
```bash
# Activate virtual environment first
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/macOS

# Then run
python src/main.py
```

**Solution B: Check PyQt5 Installation**
```bash
# Test PyQt5
python -c "from PyQt5.QtWidgets import QApplication; print('PyQt5 OK')"

# Reinstall if needed
pip uninstall PyQt5
pip install PyQt5
```

**Solution C: Run from Command Line for Error Messages**
```bash
# Instead of double-clicking start.bat
cd F:\KotobaTranscriber
python src/main.py

# Check for error messages
```

**Solution D: Check Display Environment (Linux)**
```bash
# Set DISPLAY variable
export DISPLAY=:0

# Or use virtual display
Xvfb :1 -screen 0 1024x768x24 &
export DISPLAY=:1
python src/main.py
```

### 7.2 Error Log Analysis

**Locate Error Logs:**
```bash
# Find recent errors
grep -r "ERROR" logs/*.log

# Find specific error types
grep -r "TranscriptionFailedError" logs/*.log
grep -r "ModelLoadingError" logs/*.log
```

**Common Error Patterns:**

| Error Pattern | Likely Cause | Solution Section |
|---------------|--------------|------------------|
| `CUDA` | GPU/CUDA issue | 7.1 Issue 1 |
| `ffmpeg` | ffmpeg missing | 7.1 Issue 2 |
| `MemoryError` | Out of memory | 7.1 Issue 3 |
| `PermissionError` | File access | 7.1 Issue 4 |
| `ConnectionError` | Network/download | 7.1 Issue 5 |
| `RuntimeError: meta tensor` | Preprocessing | 7.1 Issue 6 |

### 7.3 Diagnostic Commands

**System Information:**
```bash
# Python version
python --version

# Installed packages
pip list

# CUDA version
nvcc --version
nvidia-smi

# ffmpeg version
ffmpeg -version

# Disk space
df -h  # Linux/macOS
wmic logicaldisk get size,freespace,caption  # Windows

# Memory
free -h  # Linux
vm_stat  # macOS
wmic OS get FreePhysicalMemory,TotalVisibleMemorySize  # Windows
```

**Application Diagnostics:**
```python
# Run diagnostic script
python src/diagnostics.py

# Expected output:
# - Python version
# - PyTorch version
# - CUDA availability
# - Model cache location
# - Configuration status
# - Log file locations
```

### 7.4 Debug Mode

Enable debug mode for detailed logging.

**Enable Debug Logging:**
```yaml
# config/config.yaml
logging:
  level: "DEBUG"

  console:
    enabled: true
    colored: true
    level: "DEBUG"
```

**Run in Debug Mode:**
```bash
# Set debug environment variable
export KOTOBA_DEBUG=1  # Linux/macOS
set KOTOBA_DEBUG=1     # Windows

python src/main.py
```

### 7.5 Getting Help

**Before Reporting Issues:**

1. Check this troubleshooting section
2. Review logs for error messages
3. Run diagnostic commands
4. Try suggested solutions

**When Reporting Issues:**

Include:
- OS and version
- Python version
- GPU model (if using CUDA)
- Error messages from logs
- Steps to reproduce
- Configuration file (remove sensitive data)

**Report Issues:**
- GitHub Issues: [project URL]/issues
- Email: support@example.com
- Documentation: See docs/README.md

---

## 8. Upgrade Guide

### 8.1 Backup Procedure

Before upgrading, back up important data.

**What to Back Up:**

```bash
# Create backup directory
mkdir backup_$(date +%Y%m%d)

# Back up configuration
cp config/config.yaml backup_$(date +%Y%m%d)/
cp config/logging.yaml backup_$(date +%Y%m%d)/
cp custom_vocabulary.json backup_$(date +%Y%m%d)/

# Back up logs (optional)
cp -r logs backup_$(date +%Y%m%d)/

# Back up results (optional)
cp -r results backup_$(date +%Y%m%d)/

# Back up database (if applicable)
# cp database.db backup_$(date +%Y%m%d)/
```

**Automated Backup Script:**

```bash
# backup.sh (Linux/macOS) or backup.bat (Windows)
#!/bin/bash
BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "Creating backup in $BACKUP_DIR..."

cp config/config.yaml "$BACKUP_DIR/"
cp config/logging.yaml "$BACKUP_DIR/"
cp custom_vocabulary.json "$BACKUP_DIR/" 2>/dev/null || :

tar -czf "$BACKUP_DIR/logs.tar.gz" logs/ 2>/dev/null || :

echo "Backup complete: $BACKUP_DIR"
```

### 8.2 Migration Steps

#### Step 1: Check Current Version

```bash
# Check installed version
python -c "from src import __version__; print(__version__)"

# Or check git tag
git describe --tags
```

#### Step 2: Read Release Notes

Review CHANGELOG.md or release notes for breaking changes.

```bash
# View changes since your version
git log v1.0.0..v1.1.0 --oneline

# Or read CHANGELOG.md
cat CHANGELOG.md
```

#### Step 3: Update Code

```bash
# Pull latest changes
git fetch origin
git pull origin main

# Or download new release
# wget https://github.com/user/repo/archive/v1.1.0.zip
# unzip v1.1.0.zip
```

#### Step 4: Update Dependencies

```bash
# Activate virtual environment
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Update dependencies
pip install --upgrade -r requirements.txt

# Verify no conflicts
pip check
```

#### Step 5: Update Configuration

Check for new configuration options.

```bash
# Compare configurations
diff config/config.yaml config/config.example.yaml

# Add new options to your config.yaml
```

#### Step 6: Run Database Migrations (If Applicable)

```bash
# If database schema changed
python manage.py migrate

# Or run migration script
python scripts/migrate_v1_to_v2.py
```

#### Step 7: Test Upgrade

```bash
# Run tests to verify upgrade
pytest tests/

# Test basic functionality
python src/main.py --test-mode
```

### 8.3 Configuration Changes

#### Version 1.0.0 to 1.1.0 Example

**New Configuration Options:**
```yaml
# config/config.yaml - Add these new options

# New in v1.1.0
audio:
  preprocessing:
    enabled: false  # NEW: Audio preprocessing toggle

performance:
  clear_gpu_cache_frequency: 10  # NEW: GPU cache clearing

error_handling:
  max_consecutive_errors: 5  # NEW: Error threshold
```

**Deprecated Options:**
```yaml
# DEPRECATED in v1.1.0 - Remove these
model:
  cache_dir: "./cache"  # Now auto-detected

# REPLACED in v1.1.0
logging:
  log_file: "app.log"  # Now: logging.file.path
```

**Configuration Migration Script:**

```python
# migrate_config.py
import yaml

def migrate_config_v1_to_v2(old_config_path, new_config_path):
    with open(old_config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Add new options with defaults
    if 'audio' not in config:
        config['audio'] = {}
    config['audio']['preprocessing'] = {'enabled': False}

    # Migrate deprecated options
    if 'model' in config and 'cache_dir' in config['model']:
        del config['model']['cache_dir']

    # Save migrated config
    with open(new_config_path, 'w') as f:
        yaml.dump(config, f)

    print(f"Config migrated: {old_config_path} -> {new_config_path}")

# Usage
migrate_config_v1_to_v2('config/config.yaml', 'config/config_v2.yaml')
```

### 8.4 Testing After Upgrade

**Smoke Tests:**

```bash
# Test 1: Application starts
python src/main.py --version

# Test 2: Model loads
python -c "
from src.transcription_engine import TranscriptionEngine
engine = TranscriptionEngine()
engine.load_model()
print('Model loaded successfully')
"

# Test 3: Process sample file
python src/main.py --test-file tests/fixtures/sample.wav

# Test 4: Run test suite
pytest tests/test_smoke.py -v
```

**Regression Tests:**

```bash
# Run full test suite
pytest tests/ -v

# Run specific test categories
pytest tests/test_transcription.py -v
pytest tests/test_formatting.py -v
pytest tests/test_batch.py -v
```

**Performance Tests:**

```bash
# Compare performance before/after upgrade
pytest tests/test_performance.py --benchmark-compare

# Expected: No significant regression (< 10% slower)
```

### 8.5 Rollback Procedure

If upgrade fails, roll back to previous version.

**Rollback Steps:**

```bash
# Step 1: Deactivate current environment
deactivate

# Step 2: Restore from backup
cp backup_20251018/config.yaml config/
cp backup_20251018/logging.yaml config/

# Step 3: Revert code
git checkout v1.0.0  # Or previous version tag

# Step 4: Reinstall old dependencies
pip install -r requirements.txt

# Step 5: Verify rollback
python src/main.py --version
# Should show old version

# Step 6: Test basic functionality
python src/main.py
```

**Automated Rollback Script:**

```bash
# rollback.sh
#!/bin/bash
VERSION=$1

if [ -z "$VERSION" ]; then
    echo "Usage: ./rollback.sh <version>"
    echo "Example: ./rollback.sh v1.0.0"
    exit 1
fi

echo "Rolling back to $VERSION..."

git checkout "$VERSION"
pip install -r requirements.txt

echo "Rollback complete. Please test the application."
```

### 8.6 Upgrade Checklist

- [ ] Current version documented
- [ ] Backup created and verified
- [ ] Release notes reviewed
- [ ] Breaking changes identified
- [ ] Code updated (git pull or download)
- [ ] Dependencies updated (pip install)
- [ ] Configuration migrated
- [ ] Database migrated (if applicable)
- [ ] Smoke tests passing
- [ ] Regression tests passing
- [ ] Performance tests passing
- [ ] Rollback procedure tested
- [ ] Documentation updated

---

## 9. Production Deployment

### 9.1 System Service Setup

Run KotobaTranscriber as a system service for always-on operation.

#### Windows Service

**Option A: NSSM (Non-Sucking Service Manager)**

```powershell
# Download NSSM
# https://nssm.cc/download

# Install service
nssm install KotobaTranscriber "C:\path\to\venv\Scripts\python.exe" "C:\path\to\src\main.py"

# Configure service
nssm set KotobaTranscriber AppDirectory "C:\path\to\KotobaTranscriber"
nssm set KotobaTranscriber DisplayName "KotobaTranscriber Service"
nssm set KotobaTranscriber Description "Japanese Speech-to-Text Transcription Service"
nssm set KotobaTranscriber Start SERVICE_AUTO_START

# Set log files
nssm set KotobaTranscriber AppStdout "C:\path\to\logs\service-stdout.log"
nssm set KotobaTranscriber AppStderr "C:\path\to\logs\service-stderr.log"

# Start service
nssm start KotobaTranscriber

# Check status
nssm status KotobaTranscriber
```

**Option B: Task Scheduler**

```powershell
# Create scheduled task that runs on startup
$Action = New-ScheduledTaskAction -Execute "C:\path\to\venv\Scripts\python.exe" `
    -Argument "C:\path\to\src\main.py" `
    -WorkingDirectory "C:\path\to\KotobaTranscriber"

$Trigger = New-ScheduledTaskTrigger -AtStartup

$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount

Register-ScheduledTask -TaskName "KotobaTranscriber" `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Description "KotobaTranscriber Auto-Start"
```

#### Linux Service (systemd)

**Create Service File:**

```bash
# /etc/systemd/system/kotoba-transcriber.service
[Unit]
Description=KotobaTranscriber Service
After=network.target

[Service]
Type=simple
User=kotoba
Group=kotoba
WorkingDirectory=/opt/KotobaTranscriber
Environment="PATH=/opt/KotobaTranscriber/venv/bin"
ExecStart=/opt/KotobaTranscriber/venv/bin/python /opt/KotobaTranscriber/src/main.py
Restart=always
RestartSec=10

# Logging
StandardOutput=append:/var/log/kotoba/service.log
StandardError=append:/var/log/kotoba/service-error.log

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/KotobaTranscriber/logs /opt/KotobaTranscriber/results

[Install]
WantedBy=multi-user.target
```

**Enable and Start Service:**

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (auto-start on boot)
sudo systemctl enable kotoba-transcriber

# Start service
sudo systemctl start kotoba-transcriber

# Check status
sudo systemctl status kotoba-transcriber

# View logs
sudo journalctl -u kotoba-transcriber -f
```

#### macOS Service (launchd)

**Create Launch Agent:**

```bash
# ~/Library/LaunchAgents/com.kotoba.transcriber.plist
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.kotoba.transcriber</string>

    <key>ProgramArguments</key>
    <array>
        <string>/path/to/venv/bin/python</string>
        <string>/path/to/src/main.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/path/to/KotobaTranscriber</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>/path/to/logs/service.log</string>

    <key>StandardErrorPath</key>
    <string>/path/to/logs/service-error.log</string>
</dict>
</plist>
```

**Load and Start:**

```bash
# Load launch agent
launchctl load ~/Library/LaunchAgents/com.kotoba.transcriber.plist

# Start service
launchctl start com.kotoba.transcriber

# Check status
launchctl list | grep kotoba

# View logs
tail -f /path/to/logs/service.log
```

### 9.2 Auto-start Configuration

Configure application to start automatically on system boot.

**Windows - Startup Folder:**

```powershell
# Add shortcut to Startup folder
$StartupFolder = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
$ShortcutPath = "$StartupFolder\KotobaTranscriber.lnk"

$WScriptShell = New-Object -ComObject WScript.Shell
$Shortcut = $WScriptShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "C:\path\to\start.bat"
$Shortcut.WorkingDirectory = "C:\path\to\KotobaTranscriber"
$Shortcut.Save()
```

**Linux - Desktop Entry:**

```bash
# ~/.config/autostart/kotoba-transcriber.desktop
[Desktop Entry]
Type=Application
Name=KotobaTranscriber
Exec=/opt/KotobaTranscriber/start.sh
Path=/opt/KotobaTranscriber
Terminal=false
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
```

### 9.3 Health Checks

Implement health checks to monitor service status.

**Health Check Endpoint:**

```python
# src/health_check.py
from flask import Flask, jsonify
import torch
from transcription_engine import TranscriptionEngine

app = Flask(__name__)

@app.route('/health')
def health_check():
    """Health check endpoint"""
    checks = {
        'status': 'healthy',
        'cuda_available': torch.cuda.is_available(),
        'model_loaded': False,
        'disk_space_mb': get_disk_space(),
        'memory_available_mb': get_available_memory()
    }

    try:
        engine = TranscriptionEngine()
        engine.load_model()
        checks['model_loaded'] = True
    except Exception as e:
        checks['status'] = 'unhealthy'
        checks['error'] = str(e)

    status_code = 200 if checks['status'] == 'healthy' else 503
    return jsonify(checks), status_code

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

**Health Check Script:**

```bash
# health_check.sh
#!/bin/bash

HEALTH_URL="http://localhost:5000/health"
RESPONSE=$(curl -s $HEALTH_URL)
STATUS=$(echo $RESPONSE | jq -r '.status')

if [ "$STATUS" == "healthy" ]; then
    echo "Service healthy"
    exit 0
else
    echo "Service unhealthy: $RESPONSE"
    # Send alert
    ./alert.sh "KotobaTranscriber unhealthy"
    exit 1
fi
```

**Monitor with Cron:**

```bash
# crontab -e
# Check health every 5 minutes
*/5 * * * * /path/to/health_check.sh >> /var/log/kotoba/health.log 2>&1
```

### 9.4 Backup Strategy

Implement automated backup strategy for production data.

**Backup Script:**

```bash
# backup_production.sh
#!/bin/bash

BACKUP_ROOT="/backup/kotoba"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_ROOT/$TIMESTAMP"

mkdir -p "$BACKUP_DIR"

echo "Starting backup to $BACKUP_DIR..."

# Back up configuration
cp -r /opt/KotobaTranscriber/config "$BACKUP_DIR/"

# Back up custom vocabulary
cp /opt/KotobaTranscriber/custom_vocabulary.json "$BACKUP_DIR/" 2>/dev/null || :

# Back up logs (last 7 days)
find /opt/KotobaTranscriber/logs -name "*.log" -mtime -7 -exec cp {} "$BACKUP_DIR/" \;

# Back up results (optional - can be very large)
# tar -czf "$BACKUP_DIR/results.tar.gz" /opt/KotobaTranscriber/results/

# Back up database (if applicable)
# cp /opt/KotobaTranscriber/database.db "$BACKUP_DIR/"

# Remove backups older than 30 days
find "$BACKUP_ROOT" -type d -mtime +30 -exec rm -rf {} \;

echo "Backup complete: $BACKUP_DIR"
```

**Automated Backup with Cron:**

```bash
# crontab -e
# Daily backup at 2 AM
0 2 * * * /opt/KotobaTranscriber/backup_production.sh >> /var/log/kotoba/backup.log 2>&1

# Weekly backup to remote storage
0 3 * * 0 rsync -avz /backup/kotoba user@backup-server:/backups/kotoba/
```

**Verify Backups:**

```bash
# verify_backup.sh
#!/bin/bash

BACKUP_DIR=$1

if [ -z "$BACKUP_DIR" ]; then
    echo "Usage: ./verify_backup.sh <backup_directory>"
    exit 1
fi

echo "Verifying backup: $BACKUP_DIR"

# Check required files exist
REQUIRED_FILES=(
    "config/config.yaml"
    "config/logging.yaml"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$BACKUP_DIR/$file" ]; then
        echo "ERROR: Missing required file: $file"
        exit 1
    fi
done

echo "Backup verification passed"
```

### 9.5 Load Balancing (Advanced)

For high-volume deployments, set up multiple instances with load balancing.

**NGINX Load Balancer Configuration:**

```nginx
# /etc/nginx/nginx.conf
upstream kotoba_backend {
    least_conn;
    server localhost:5001 weight=1 max_fails=3 fail_timeout=30s;
    server localhost:5002 weight=1 max_fails=3 fail_timeout=30s;
    server localhost:5003 weight=1 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name transcriber.example.com;

    location / {
        proxy_pass http://kotoba_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # Increase timeout for long transcriptions
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    location /health {
        proxy_pass http://kotoba_backend/health;
        access_log off;
    }
}
```

### 9.6 Monitoring Dashboard

Set up monitoring dashboard for production visibility.

**Grafana + Prometheus Setup:**

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'kotoba-transcriber'
    static_configs:
      - targets: ['localhost:5000']
```

**Metrics Exporter:**

```python
# src/metrics_exporter.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Metrics
transcriptions_total = Counter('transcriptions_total', 'Total transcriptions')
transcription_duration = Histogram('transcription_duration_seconds', 'Transcription duration')
transcription_errors = Counter('transcription_errors_total', 'Total errors')
gpu_memory_usage = Gauge('gpu_memory_usage_bytes', 'GPU memory usage')

def start_metrics_server(port=9090):
    start_http_server(port)
```

### 9.7 Production Checklist

- [ ] System service configured and tested
- [ ] Auto-start enabled
- [ ] Health checks implemented
- [ ] Automated backup configured
- [ ] Backup verification tested
- [ ] Log rotation configured
- [ ] Monitoring dashboard set up
- [ ] Alerts configured (email/Slack)
- [ ] Performance benchmarks established
- [ ] Disaster recovery plan documented
- [ ] Security hardening completed
- [ ] Documentation updated for production

---

## 10. Post-Deployment Validation

### 10.1 Smoke Tests

Verify basic functionality after deployment.

**Test Checklist:**

```bash
# Test 1: Application starts
python src/main.py --version
# Expected: Version number displayed

# Test 2: Configuration loads
python -c "from src.config_manager import ConfigManager; cm = ConfigManager(); print('Config OK')"
# Expected: "Config OK"

# Test 3: CUDA available (if using GPU)
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
# Expected: "CUDA: True" (GPU mode)

# Test 4: Model loads
python -c "
from src.transcription_engine import TranscriptionEngine
engine = TranscriptionEngine()
engine.load_model()
print('Model loaded')
"
# Expected: "Model loaded" (may take 5-10 seconds)

# Test 5: Process test file
python src/main.py --input tests/fixtures/sample.wav --output /tmp/test_output.txt
# Expected: Transcription completes, output file created

# Test 6: Verify output file
cat /tmp/test_output.txt
# Expected: Japanese text content
```

**Automated Smoke Test Script:**

```python
# tests/test_smoke.py
import pytest
import torch
from src.transcription_engine import TranscriptionEngine
from src.config_manager import ConfigManager

def test_python_version():
    """Verify Python version"""
    import sys
    assert sys.version_info >= (3, 8), "Python 3.8+ required"

def test_config_loads():
    """Verify configuration loads"""
    config = ConfigManager()
    assert config is not None
    assert config.get('app.name') == 'KotobaTranscriber'

def test_cuda_available():
    """Verify CUDA availability (GPU mode only)"""
    # Skip if not using GPU
    if torch.cuda.is_available():
        assert torch.cuda.device_count() > 0

def test_model_loads():
    """Verify model loads successfully"""
    engine = TranscriptionEngine()
    engine.load_model()
    assert engine.is_available()

def test_basic_transcription(tmp_path):
    """Verify basic transcription works"""
    engine = TranscriptionEngine()
    engine.load_model()

    # Use test fixture
    test_audio = "tests/fixtures/sample.wav"
    result = engine.transcribe(test_audio)

    assert result is not None
    assert 'text' in result
    assert len(result['text']) > 0

# Run smoke tests
# pytest tests/test_smoke.py -v
```

### 10.2 Security Validation

Verify security configurations.

**Security Test Checklist:**

```bash
# Test 1: Path validation prevents traversal
python -c "
from src.validators import Validator
try:
    Validator.validate_file_path('../../../etc/passwd')
    print('FAIL: Path traversal not blocked')
except Exception:
    print('PASS: Path traversal blocked')
"

# Test 2: File permissions correct
ls -la config/config.yaml
# Expected: -rw------- or -rw-r----- (not world-readable)

ls -la logs/
# Expected: drwx------ or drwxr-x--- (not world-writable)

# Test 3: No sensitive data in logs
grep -i "password\|api_key\|secret" logs/*.log
# Expected: No matches (or masked values)

# Test 4: Dependencies have no known vulnerabilities
safety check
# Expected: No known security vulnerabilities found

# Test 5: Code has no security issues
bandit -r src/ -ll
# Expected: No issues found (or only low severity)

# Test 6: Configuration files not in version control
git ls-files | grep -E "config\.yaml|\.env|\.key"
# Expected: No matches (files should be gitignored)
```

**Automated Security Tests:**

```python
# tests/test_security.py
import pytest
from pathlib import Path
from src.validators import Validator, ValidationError

def test_path_traversal_blocked():
    """Verify path traversal attacks are blocked"""
    malicious_paths = [
        "../../../etc/passwd",
        "..\\..\\..\\Windows\\System32\\config\\sam",
        "/etc/shadow",
        "C:\\Windows\\System32\\config\\SAM"
    ]

    for path in malicious_paths:
        with pytest.raises(ValidationError):
            Validator.validate_file_path(path, must_exist=False)

def test_symlink_attack_blocked():
    """Verify symlink attacks are blocked"""
    # Create symlink to sensitive file
    sensitive_file = Path("/etc/passwd")
    if sensitive_file.exists():
        symlink = Path("/tmp/test_symlink")
        symlink.symlink_to(sensitive_file)

        try:
            with pytest.raises(ValidationError):
                Validator.validate_file_path(str(symlink))
        finally:
            symlink.unlink()

def test_config_file_permissions():
    """Verify config files have correct permissions"""
    config_file = Path("config/config.yaml")
    if config_file.exists():
        import stat
        mode = config_file.stat().st_mode
        # Check not world-readable
        assert not (mode & stat.S_IROTH), "Config file is world-readable"

# Run security tests
# pytest tests/test_security.py -v
```

### 10.3 Performance Benchmarks

Establish baseline performance metrics.

**Benchmark Test:**

```python
# tests/test_performance.py
import pytest
import time
from src.transcription_engine import TranscriptionEngine

@pytest.fixture
def engine():
    engine = TranscriptionEngine()
    engine.load_model()
    return engine

def test_model_load_time():
    """Model should load within 10 seconds"""
    start = time.time()
    engine = TranscriptionEngine()
    engine.load_model()
    duration = time.time() - start

    assert duration < 10.0, f"Model load took {duration:.2f}s (>10s)"
    print(f"Model load time: {duration:.2f}s")

def test_transcription_speed(engine, benchmark_audio):
    """Transcription should be faster than 2x real-time (GPU)"""
    audio_duration = get_audio_duration(benchmark_audio)

    start = time.time()
    result = engine.transcribe(benchmark_audio)
    transcription_time = time.time() - start

    rtf = transcription_time / audio_duration  # Real-time factor

    # GPU: should be < 0.5 (2x faster than real-time)
    # CPU: should be < 2.0 (0.5x real-time)
    threshold = 0.5 if torch.cuda.is_available() else 2.0

    assert rtf < threshold, f"RTF {rtf:.2f} (threshold: {threshold})"
    print(f"Transcription RTF: {rtf:.2f}x")

def test_batch_throughput(engine):
    """Batch processing should handle 10 files in reasonable time"""
    test_files = [f"tests/fixtures/sample_{i}.wav" for i in range(10)]

    start = time.time()
    for file in test_files:
        engine.transcribe(file)
    total_time = time.time() - start

    # Should process 10 files in < 2 minutes (GPU)
    threshold = 120 if torch.cuda.is_available() else 600
    assert total_time < threshold, f"Batch took {total_time:.2f}s"
    print(f"Batch throughput: {len(test_files)/total_time:.2f} files/sec")

# Run performance tests
# pytest tests/test_performance.py -v --benchmark-only
```

**Expected Performance Benchmarks:**

| Metric | GPU (Expected) | CPU (Expected) | Threshold |
|--------|----------------|----------------|-----------|
| Model Load Time | 3-5s | 5-10s | 15s |
| Transcription RTF (1min audio) | 0.15-0.30x | 0.8-1.5x | 2.0x |
| Batch 10 files (1min each) | 30-60s | 150-300s | 600s |
| Memory Usage (GPU) | 2-4 GB | N/A | 8 GB |
| Memory Usage (CPU) | N/A | 3-5 GB | 10 GB |

### 10.4 User Acceptance Testing

Validate application meets user requirements.

**UAT Test Cases:**

1. **File Selection**
   - [ ] User can select audio file via GUI
   - [ ] Supported formats are filterable
   - [ ] Invalid files show error message

2. **Transcription**
   - [ ] Progress bar shows during transcription
   - [ ] Results display in text area
   - [ ] Japanese text displays correctly

3. **Text Formatting**
   - [ ] Filler word removal works
   - [ ] Punctuation added correctly
   - [ ] Paragraph formatting applied

4. **Save Output**
   - [ ] Save dialog appears
   - [ ] File saves with correct encoding (UTF-8)
   - [ ] Saved file can be opened in text editor

5. **Batch Processing**
   - [ ] Multiple files can be queued
   - [ ] Progress shows for each file
   - [ ] Results saved to output directory

6. **Error Handling**
   - [ ] Clear error messages for common issues
   - [ ] Application doesn't crash on error
   - [ ] Logs contain error details

**UAT Execution:**

```bash
# Run manual UAT checklist
# Have end users test each scenario
# Document any issues found

# Example UAT report:
# Test Case 1: File Selection - PASS
# Test Case 2: Transcription - PASS
# Test Case 3: Formatting - FAIL (punctuation incorrect for questions)
# ...
```

### 10.5 Load Testing (Optional)

For production deployments, test under load.

**Load Test Script:**

```python
# tests/test_load.py
import concurrent.futures
import time
from src.transcription_engine import TranscriptionEngine

def transcribe_file(file_path):
    """Transcribe single file"""
    engine = TranscriptionEngine()
    engine.load_model()
    start = time.time()
    result = engine.transcribe(file_path)
    duration = time.time() - start
    return {
        'file': file_path,
        'duration': duration,
        'success': result is not None
    }

def load_test(num_concurrent=5, num_files=20):
    """Simulate concurrent transcription requests"""
    test_file = "tests/fixtures/sample.wav"
    files = [test_file] * num_files

    start = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
        results = list(executor.map(transcribe_file, files))

    total_time = time.time() - start

    success_count = sum(1 for r in results if r['success'])
    avg_duration = sum(r['duration'] for r in results) / len(results)

    print(f"\nLoad Test Results:")
    print(f"  Total files: {num_files}")
    print(f"  Concurrent: {num_concurrent}")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Success rate: {success_count}/{num_files} ({success_count/num_files*100:.1f}%)")
    print(f"  Avg duration: {avg_duration:.2f}s")
    print(f"  Throughput: {num_files/total_time:.2f} files/sec")

if __name__ == '__main__':
    load_test(num_concurrent=5, num_files=20)
```

### 10.6 Documentation Verification

Ensure documentation is accurate and complete.

**Documentation Checklist:**

- [ ] README.md up to date
- [ ] Installation instructions tested
- [ ] Configuration examples correct
- [ ] API documentation matches code
- [ ] Troubleshooting guide complete
- [ ] Release notes published
- [ ] User manual available
- [ ] Developer guide available

**Test Documentation:**

```bash
# Follow installation guide step-by-step
# On a fresh machine/VM
# Document any missing steps or unclear instructions
```

### 10.7 Rollback Readiness

Verify rollback procedure works if needed.

**Rollback Test:**

```bash
# Test rollback procedure (on test environment)
# 1. Note current version
python src/main.py --version

# 2. Trigger rollback
./rollback.sh v1.0.0

# 3. Verify old version running
python src/main.py --version
# Expected: v1.0.0

# 4. Test basic functionality
python src/main.py --test-file tests/fixtures/sample.wav
# Expected: Works correctly

# 5. Restore to new version
git checkout main
pip install -r requirements.txt
```

### 10.8 Deployment Sign-off

Final sign-off before declaring deployment complete.

**Sign-off Checklist:**

- [ ] All smoke tests passing
- [ ] Security validation complete
- [ ] Performance benchmarks met
- [ ] UAT completed and approved
- [ ] Load testing completed (if applicable)
- [ ] Documentation verified
- [ ] Rollback procedure tested
- [ ] Monitoring active and alerts configured
- [ ] Backup system operational
- [ ] Team trained on new features
- [ ] Support contacts documented
- [ ] Incident response plan ready

**Sign-off Document Template:**

```markdown
# Deployment Sign-off - KotobaTranscriber v1.0.0

**Date:** 2025-10-18
**Environment:** Production
**Deployed By:** [Name]
**Reviewed By:** [Name]

## Test Results
- Smoke Tests: PASS ✓
- Security Tests: PASS ✓
- Performance Tests: PASS ✓
- UAT: PASS ✓

## Performance Metrics
- Model Load Time: 4.2s (Target: <10s)
- Transcription RTF: 0.25x (Target: <0.5x)
- Batch Throughput: 1.8 files/sec (Target: >1.0)

## Known Issues
- None critical
- Minor: [List any minor issues]

## Rollback Plan
- Rollback script tested: YES
- Backup verified: YES
- RTO: < 15 minutes

## Sign-off
- [ ] Technical Lead: ________________
- [ ] DevOps: ________________
- [ ] Product Owner: ________________

**Status: APPROVED FOR PRODUCTION**
```

---

## Appendix

### A. Quick Reference Commands

**Start Application:**
```bash
# Windows
start.bat

# Linux/macOS
./start.sh
```

**Check Status:**
```bash
# Check if running
ps aux | grep "python.*main.py"  # Linux/macOS
tasklist | findstr python  # Windows

# Check logs
tail -f logs/app.log  # Linux/macOS
Get-Content logs\app.log -Wait -Tail 50  # Windows
```

**Stop Application:**
```bash
# GUI: Close window
# Service:
systemctl stop kotoba-transcriber  # Linux
nssm stop KotobaTranscriber  # Windows
```

### B. Configuration Templates

**Minimal Configuration (config.yaml):**
```yaml
model:
  whisper:
    device: "auto"
audio:
  ffmpeg:
    path: "/usr/local/bin"  # Adjust for your system
logging:
  level: "INFO"
```

**Production Configuration (config.yaml):**
```yaml
model:
  whisper:
    device: "cuda"
    chunk_length_s: 15
  faster_whisper:
    model_size: "base"
    compute_type: "float16"

audio:
  ffmpeg:
    path: "C:\\ffmpeg\\bin"
  preprocessing:
    enabled: false

performance:
  max_concurrent_transcriptions: 4
  thread_pool_size: 8
  max_memory_usage_mb: 8192

logging:
  level: "INFO"
  file:
    enabled: true
    rotation: "1 day"
    retention: "30 days"

error_handling:
  max_retries: 3
  fallback_to_cpu: true
```

### C. Troubleshooting Flowchart

```
Application won't start
    |
    ├─ Check Python version (3.8+)
    ├─ Activate virtual environment
    ├─ Check dependencies installed
    └─ Check config.yaml exists

Transcription fails
    |
    ├─ Check ffmpeg installed
    ├─ Check GPU available (if using CUDA)
    ├─ Check model downloaded
    └─ Check audio file format supported

Slow performance
    |
    ├─ Check device setting (CPU vs GPU)
    ├─ Check model size
    ├─ Check batch size
    └─ Monitor GPU/CPU usage
```

### D. Support Contacts

**Technical Support:**
- Email: support@example.com
- GitHub Issues: [repository URL]/issues
- Documentation: [repository URL]/docs

**Emergency Contacts:**
- On-call: [phone number]
- Slack: #kotoba-support

### E. Related Documentation

- [README.md](../README.md) - User guide
- [CI_CD_GUIDE.md](CI_CD_GUIDE.md) - CI/CD setup
- [SECURITY_IMPLEMENTATION.md](SECURITY_IMPLEMENTATION.md) - Security details
- [CLAUDE.md](../CLAUDE.md) - Developer guide
- [EXCEPTION_HANDLING_IMPROVEMENTS.md](../EXCEPTION_HANDLING_IMPROVEMENTS.md) - Error handling

---

**Document Version:** 1.0.0
**Last Updated:** 2025-10-18
**Maintained By:** DevOps Team

For questions or corrections, please contact: support@example.com
