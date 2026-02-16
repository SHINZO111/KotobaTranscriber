# ffmpeg Path and Japanese Character Handling Fix Plan

## Problem Summary

All 10 unprocessed files failed with exit code -22 (EINVAL) due to:
1. **P0**: ffmpeg path does not exist (`C:\ffmpeg\ffmpeg-8.0-essentials_build\bin\ffmpeg.exe`)
2. **P1**: Video files with Japanese paths not converted to ShortPath before ffmpeg
3. **P1**: Insufficient error logging (stderr not captured)

## Root Cause Analysis

From 5-agent parallel review:

### Agent 1 (ffmpeg呼び出し分析):
- `transcription_engine.py:368-376` passes `video_path` directly to ffmpeg
- Audio files get ShortPath conversion, video files bypass it
- Japanese characters in OneDrive paths: `C:/Users/sawas/OneDrive - AGEC株式会社/レコーディング`

### Agent 2 (一時ファイル管理分析):
- Temp file creation is correct
- Input path handling for video files bypasses ShortPath conversion

### Agent 3 (バッチ処理フロー分析):
- BatchTranscriptionWorker correctly reports failures
- Cancellation/interruption causes discrepancy in counts

### Agent 4 (エラーログ詳細分析):
- All 10 files failed with two patterns:
  - `OSError [Errno 22] Invalid argument`
  - `ValueError: Soundfile format error`

### Agent 5 (設定とパス検証):
- config.yaml specifies non-existent path
- System falls back to PATH (ffmpeg found at system location)
- PATH fallback works but still fails on Japanese paths

## Implementation Tasks

### Task 1: Fix ffmpeg Path Configuration
**File**: `config/config.yaml`

**Current state**:
```yaml
audio:
  ffmpeg:
    path: "C:/ffmpeg/ffmpeg-8.0-essentials_build/bin"
```

**Change**:
- Remove hardcoded path (does not exist)
- Let system use PATH (ffmpeg.exe is available in system PATH)

**Expected outcome**:
- config.yaml uses empty string or removes path specification
- System finds ffmpeg via PATH
- No warnings about missing ffmpeg path

**Test**:
- Verify ffmpeg.exe can be found: `where ffmpeg`
- Check ConfigManager loads without warnings

---

### Task 2: Apply ShortPath Conversion to Video Files
**File**: `src/transcription_engine.py`

**Current state** (lines 360-380):
```python
# Video file handling
if file_extension in {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv'}:
    temp_wav_path = temp_dir / "temp_audio.wav"
    try:
        cmd = [
            'ffmpeg', '-i', video_path,  # ← Japanese path not converted
            '-vn', '-acodec', 'pcm_s16le',
            '-ar', '16000', '-ac', '1', '-y',
            str(temp_wav_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
```

**Change**:
1. Convert `video_path` to Windows 8.3 ShortPath before passing to ffmpeg
2. Use the same `_get_short_path_name()` helper already used for audio files
3. Capture stderr properly for logging

**Expected outcome**:
- Video files with Japanese characters converted to short paths (e.g., `C:\Users\sawas\ONEDRI~1\...`)
- ffmpeg receives ASCII-only paths
- Detailed error messages if ffmpeg still fails

**Test**:
- Process one of the failing video files
- Verify ShortPath appears in debug logs
- Confirm transcription completes successfully

---

### Task 3: Enhance ffmpeg Error Logging
**File**: `src/transcription_engine.py`

**Current state**:
- stderr captured but not logged before exception
- Generic error messages hide root cause

**Change**:
```python
result = subprocess.run(cmd, capture_output=True, text=True, check=True)
```
to:
```python
try:
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
except subprocess.CalledProcessError as e:
    logger.error(f"ffmpeg failed (exit {e.returncode}): {e.stderr}")
    raise AudioExtractionError(f"Video audio extraction failed") from e
```

**Expected outcome**:
- Full ffmpeg stderr in logs when extraction fails
- Better debugging information for future issues

**Test**:
- Trigger a known failure condition
- Verify logs contain ffmpeg stderr output

---

### Task 4: Integration Test with Failing File
**File**: Test manually with one failing file

**Steps**:
1. Clear logs: `del logs\monitor_debug*.log`
2. Start monitor: `python start_monitor_debug.py`
3. Wait for file detection and processing
4. Check logs for:
   - ShortPath conversion message
   - Successful transcription
   - No Errno 22 errors

**Expected outcome**:
- At least 1 file processes successfully
- Transcription output created
- File moved to completed folder (if auto_move enabled)

**Test**:
- Pick smallest failing file for fast turnaround
- Verify .txt file created in output folder
- Confirm file marked as processed

## Success Criteria

- ✅ config.yaml updated (ffmpeg path fixed)
- ✅ Video files use ShortPath conversion
- ✅ Enhanced error logging implemented
- ✅ At least 1 failing file processes successfully
- ✅ No Errno 22 errors in logs
- ✅ All tests pass

## Rollback Plan

If changes cause issues:
1. Revert `transcription_engine.py` from git
2. Restore `config.yaml` backup
3. Review logs to identify regression

## Files to Modify

1. `config/config.yaml` - Remove invalid ffmpeg path
2. `src/transcription_engine.py` - Apply ShortPath to video files, enhance logging
3. `logs/` - Monitor for test results

## Estimated Impact

- **Lines changed**: ~15-20 lines
- **Risk level**: Low (changes are localized, ShortPath logic already proven with audio files)
- **Test coverage**: Manual integration test + existing unit tests
- **Deployment**: No new dependencies, backward compatible
