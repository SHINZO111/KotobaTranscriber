# KotobaTranscriber Architecture Consistency Review

**Review Date**: 2026-02-10
**Reviewer**: Architecture Consistency Expert
**Scope**: Dual architecture (Legacy PySide6 + New Tauri+FastAPI)

---

## Executive Summary

**Overall Assessment**: **GOOD** with several P1-P2 improvements needed.

The dual architecture is well-executed with proper separation between Qt-dependent legacy code and Qt-free API modules. Shared patterns are correctly abstracted. However, there are configuration drift issues and some inconsistencies in max_workers enforcement that should be addressed.

**Critical Findings**: 0 P0 issues
**Important Findings**: 3 P1 issues
**Suggestions**: 5 P2 issues

---

## P0 Issues (Critical - Must Fix Immediately)

**None identified.** The architecture is fundamentally sound.

---

## P1 Issues (Important - Should Fix Soon)

### P1-1: Configuration API Inconsistency in Documentation vs Implementation

**Location**: `src/api/routers/settings.py:58-59`, `MEMORY.md`, `CLAUDE.md`

**Issue**: Documentation states "`ConfigManager` has NO `get_all()` or `set()`", but the implementation pattern is correct. The confusion arises from accessing `config.config.data` (property on inner `Config` object) vs. direct methods.

**Details**:
- `ConfigManager` has `.config` property returning a `Config` object
- `Config` object has `.data` property (returns deep copy) and `.set(key, val)` method
- `AppSettings` has `.get_all()` method directly
- Current usage in `settings.py:59` is correct: `config.config.data`

**Impact**: Medium - Confusing for new developers, documentation drift

**Recommendation**:
```python
# Update MEMORY.md to clarify:
# ConfigManager.config.data — read-only deep copy of full config dict
# ConfigManager.config.set(key, val) — write config with dot notation
# AppSettings.get_all() — read-only deep copy of settings dict
```

**Files to Update**:
- `F:\KotobaTranscriber\MEMORY.md` (lines about ConfigManager API)
- `F:\KotobaTranscriber\CLAUDE.md` (if similar statements exist)

---

### P1-2: max_workers Enforcement Inconsistency Between Legacy and API

**Location**: `src/workers.py:86`, `src/api/workers.py:168`, `src/constants.py:18-19`

**Issue**: Both worker implementations hardcode `max_workers=1` to enforce engine exclusivity, but `SharedConstants` defines two different defaults that are never actually used.

**Details**:
```python
# constants.py
BATCH_WORKERS_DEFAULT = 1
MONITOR_BATCH_WORKERS = 2  # ← This is misleading, never enforced

# workers.py (legacy Qt)
self.max_workers = 1  # Always overridden regardless of constructor arg

# api/workers.py (API)
self.max_workers = 1  # Always overridden regardless of constructor arg

# Actual usage in main.py:
max_workers=UIConstants.BATCH_WORKERS_DEFAULT  # = 1, works

# Actual usage in monitor_app.py:
max_workers=SharedConstants.MONITOR_BATCH_WORKERS  # = 2, but gets overridden to 1!
```

**Impact**: High - Misleading constant value, caller expectations not met

**Recommendation**:
```python
# Option 1: Remove misleading constant, add comment
class SharedConstants:
    # Engine exclusion: max_workers is always forced to 1 internally
    # Callers cannot override this due to non-thread-safe engine design
    BATCH_MAX_WORKERS = 1  # Enforced in both legacy and API workers

# Option 2: Add runtime validation
def __init__(self, ..., max_workers: int = 1, ...):
    if max_workers != 1:
        logger.warning(f"max_workers={max_workers} ignored, forced to 1 (engine exclusion)")
    self.max_workers = 1
```

**Files to Update**:
- `F:\KotobaTranscriber\src\constants.py:18-19`
- `F:\KotobaTranscriber\src\workers.py:86`
- `F:\KotobaTranscriber\src\api\workers.py:168`
- `F:\KotobaTranscriber\src\monitor_app.py:509` (update constant reference)

---

### P1-3: Missing Error Response Schema Consistency Validation

**Location**: All routers in `src/api/routers/*.py`

**Issue**: All routers use `HTTPException` for errors, but there's no standardized error response schema or global exception handler.

**Details**:
- Each router independently raises `HTTPException` with custom detail messages
- No centralized error format (e.g., `{"error": {"code": "...", "message": "...", "details": {...}}`)
- Auth middleware returns `JSONResponse` directly (bypasses FastAPI's exception handling)
- Client code must parse `detail` strings inconsistently

**Impact**: Medium - Harder for frontend to handle errors consistently

**Recommendation**:
```python
# Add to api/schemas.py
class ErrorDetail(BaseModel):
    code: str  # e.g., "FILE_NOT_FOUND", "INVALID_PATH"
    message: str
    details: Optional[Dict[str, Any]] = None

class ErrorResponse(BaseModel):
    error: ErrorDetail

# Add global exception handler in api/main.py
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.headers.get("X-Error-Code", "UNKNOWN_ERROR"),
                "message": exc.detail,
                "details": exc.headers.get("X-Error-Details"),
            }
        }
    )
```

**Files to Update**:
- `F:\KotobaTranscriber\src\api\schemas.py` (add ErrorResponse models)
- `F:\KotobaTranscriber\src\api\main.py` (add exception handler)
- Optionally: Update routers to use custom headers for error codes

---

## P2 Issues (Suggestions - Nice to Have)

### P2-1: Shared Pattern Not Actually Shared - normalize_segments

**Location**: `src/constants.py:60-79`, `src/workers.py:26,31`, `src/api/workers.py:13,30`, `src/api/routers/transcription.py:21`

**Issue**: `normalize_segments` is defined in `constants.py` and imported correctly everywhere, but each module also creates a module-level alias `_normalize_segments` for backward compatibility. This creates unnecessary duplication.

**Details**:
```python
# constants.py — single source of truth
def normalize_segments(result: dict) -> list: ...

# workers.py (legacy)
from constants import SharedConstants, normalize_segments
_normalize_segments = normalize_segments  # ← Backward compat alias

# api/workers.py
from constants import SharedConstants, normalize_segments
_normalize_segments = normalize_segments  # ← Same alias

# api/routers/transcription.py
from constants import normalize_segments as _normalize_segments  # ← Import alias
```

**Impact**: Low - Code duplication, but doesn't affect functionality

**Recommendation**:
```python
# Option 1: Remove all aliases, use normalize_segments directly
from constants import normalize_segments
segments = normalize_segments(result)

# Option 2: Document that _normalize_segments is deprecated
# Mark with deprecation warning if anyone imports it
import warnings
def _normalize_segments(*args, **kwargs):
    warnings.warn("_normalize_segments is deprecated, use normalize_segments", DeprecationWarning)
    return normalize_segments(*args, **kwargs)
```

**Files to Review**:
- `F:\KotobaTranscriber\src\workers.py:26,31,181,467`
- `F:\KotobaTranscriber\src\api\workers.py:13,30,132,231`
- `F:\KotobaTranscriber\src\api\routers\transcription.py:21,56`

---

### P2-2: Qt Isolation - BUTTON_STYLE Constants in SharedConstants

**Location**: `src/constants.py:29-32`

**Issue**: `SharedConstants` includes Qt UI-specific button styles, but the API modules import `SharedConstants` and have no use for these Qt constants.

**Details**:
```python
# constants.py (supposed to be Qt-free)
class SharedConstants:
    BUTTON_STYLE_NORMAL = "font-size: 12px; ..."  # ← Qt-only
    BUTTON_STYLE_MONITOR = "..."  # ← Qt-only
    BUTTON_STYLE_STOP = "..."  # ← Qt-only

# api/workers.py imports SharedConstants but doesn't use button styles
from constants import SharedConstants  # Only needs progress values
```

**Impact**: Low - Doesn't break API, just pollutes namespace

**Recommendation**:
```python
# Option 1: Move UI constants to UIConstants in main.py/monitor_app.py
class SharedConstants:
    # Only truly shared constants (progress, timeouts, extensions)
    pass

class UIConstants(SharedConstants):
    BUTTON_STYLE_NORMAL = "..."  # Qt-specific

# Option 2: Add comment documenting Qt-specific constants
class SharedConstants:
    # Qt UI constants (unused in API modules)
    BUTTON_STYLE_NORMAL = "..."
```

**Files to Consider**:
- `F:\KotobaTranscriber\src\constants.py:29-32`
- `F:\KotobaTranscriber\src\main.py` (UIConstants)
- `F:\KotobaTranscriber\src\monitor_app.py` (MonitorUIConstants)

---

### P2-3: AUDIO_FILE_FILTER String in Qt-Free Module

**Location**: `src/constants.py:52-57`

**Issue**: Similar to P2-2, `AUDIO_FILE_FILTER` is a Qt `QFileDialog` filter string stored in the supposedly Qt-free `constants.py`.

**Details**:
```python
# constants.py:52-57
AUDIO_FILE_FILTER = (
    "Audio Files ("
    + " ".join(f"*{ext}" for ext in SUPPORTED_EXTENSIONS)
    + ");;All Files (*)"
)  # ← QFileDialog-specific format, unused in API
```

**Impact**: Low - API modules don't use it, but it's conceptually misplaced

**Recommendation**:
```python
# Move to UIConstants or document as legacy
class SharedConstants:
    SUPPORTED_EXTENSIONS = (...)  # Shared
    AUDIO_EXTENSIONS = set(SUPPORTED_EXTENSIONS)  # Shared

    # QFileDialog filter (Qt UI only, unused in API)
    AUDIO_FILE_FILTER = "..."
```

**Files to Consider**:
- `F:\KotobaTranscriber\src\constants.py:52-57`

---

### P2-4: Import Chain Validation - Missing __all__ Exports

**Location**: `src/__init__.py`, `src/api/__init__.py`, `src/api/routers/__init__.py`

**Issue**: Package `__init__.py` files exist but are mostly empty or minimal. No `__all__` declarations to control exports.

**Details**:
```python
# src/__init__.py — has version, but no __all__
__version__ = "0.1.0"

# src/api/__init__.py — minimal docstring, no __all__
"""KotobaTranscriber API パッケージ"""

# src/api/routers/__init__.py — not checked yet
```

**Impact**: Low - Doesn't affect functionality, but makes package structure less explicit

**Recommendation**:
```python
# src/api/__init__.py
"""KotobaTranscriber API パッケージ"""
from api.event_bus import EventBus, get_event_bus
from api.dependencies import get_worker_state, get_transcription_engine

__all__ = ["EventBus", "get_event_bus", "get_worker_state", "get_transcription_engine"]
```

**Files to Consider**:
- `F:\KotobaTranscriber\src\api\__init__.py`
- `F:\KotobaTranscriber\src\api\routers\__init__.py`

---

### P2-5: CoW Snapshot Pattern Documentation

**Location**: `src/api/event_bus.py:32-48`

**Issue**: The Copy-on-Write snapshot pattern is implemented correctly but lacks inline documentation explaining the performance trade-off.

**Details**:
```python
# event_bus.py:32-48
self._snapshot: Optional[list] = None  # ← No comment explaining CoW strategy

def _get_snapshot(self) -> list:
    with self._lock:
        if self._snapshot is None:
            self._snapshot = list(self._subscribers.items())
        return self._snapshot
```

**Impact**: Very Low - Code works correctly, just needs documentation

**Recommendation**:
```python
# Add docstring explaining CoW pattern
class EventBus:
    """
    Copy-on-Write (CoW) optimization:
    - Snapshot is rebuilt only on subscribe/unsubscribe (rare)
    - emit() reads cached snapshot without lock contention (frequent)
    - Trade-off: Memory (1 list copy) for speed (no lock on emit)
    """
    self._snapshot: Optional[list] = None  # CoW cache, invalidated on sub/unsub
```

**Files to Update**:
- `F:\KotobaTranscriber\src\api\event_bus.py:16-34`

---

## Configuration Drift Analysis

### Config Sources Verified

✅ **No drift detected** between legacy and API architectures:

1. **System Config** (`config/config.yaml`):
   - Both architectures use `config_manager.py` → same source
   - API uses `get_config_manager()` dependency injection
   - Legacy uses direct import

2. **User Settings**:
   - Legacy: `app_settings.json` (main.py), `monitor_settings.json` (monitor_app.py)
   - API: `app_settings.json` via `get_app_settings()`
   - **Correctly isolated** - API uses same file as main.py

3. **API Keys**:
   - Both use environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`)
   - No hardcoded keys found

---

## Import Chain Validation

### Circular Import Check: ✅ PASS

No circular imports detected. All imports follow clean dependency graph:

```
constants.py (no dependencies)
  ↑
  ├─ workers.py (imports constants)
  ├─ api/workers.py (imports constants)
  └─ api/routers/*.py (imports constants via routers)

transcription_engine.py
  ↑
  ├─ workers.py
  └─ api/workers.py

api/event_bus.py (no Qt dependencies)
  ↑
  ├─ api/workers.py
  ├─ api/main.py
  └─ api/routers/*.py
```

### Qt Isolation Check: ✅ PASS

Verified zero Qt imports in API modules:
```bash
# grep -r "from PySide6|from QtCore|from QtWidgets" src/api/
# Result: No matches found
```

API modules are correctly Qt-free.

---

## Dead Code Analysis

### Unused Imports: ✅ MINIMAL

No significant dead imports found. All imports in reviewed files are actively used.

### Unused Code Patterns: None Found

- No commented-out code blocks
- No `# TODO`, `# FIXME`, or `# HACK` markers in API modules
- Recent cleanup commits reduced codebase by 2,004 lines (per git log)

---

## API Contract Completeness

### Error Response Formats

**Issue Identified**: Inconsistent error formats across routers (see P1-3)

Current patterns:
```python
# Pattern 1: HTTPException with string detail
raise HTTPException(status_code=404, detail=f"ファイルが見つかりません: {file_path}")

# Pattern 2: JSONResponse from middleware
return JSONResponse(status_code=401, content={"detail": "認証トークンが必要です"})

# Pattern 3: Success with MessageResponse
return MessageResponse(message="処理を開始しました")
```

**Recommendation**: See P1-3 for standardization plan.

### Response Schema Coverage

✅ All endpoints have response models:
- `TranscribeResponse`, `BatchTranscribeResponse`
- `RealtimeStatusResponse`
- `ModelInfoResponse`
- `ExportResponse`
- `MonitorStatusResponse`
- `HealthResponse`
- `MessageResponse` (generic)

### Missing Schemas

None critical, but consider:
- `ErrorResponse` (see P1-3)
- `WebSocketEvent` schema for WS messages (currently untyped dict)

---

## Performance & Scalability Checks

### Engine Exclusion Lock

✅ Correctly implemented in `api/routers/transcription.py:28`:
```python
_engine_lock = threading.Lock()  # Prevents concurrent transcriptions

# Usage in _do_transcribe:
if not _engine_lock.acquire(timeout=1):
    raise HTTPException(status_code=409, detail="別の文字起こし処理が実行中です")
```

### EventBus Queue Sizing

✅ Reasonable defaults:
```python
# event_bus.py:25
def __init__(self, maxsize: int = 1000):  # 1000 events per subscriber
```

### Worker State Management

✅ Thread-safe via `WorkerState` class with locks.

---

## Security Review

### Path Traversal Protection

✅ All file paths validated via `Validator.validate_file_path()`:
```python
# Example from transcription.py:36-41
Validator.validate_file_path(
    file_path,
    must_exist=True,
    allowed_extensions=Validator.ALLOWED_AUDIO_EXTENSIONS
)
```

### API Authentication

✅ Bearer token auth middleware active:
```python
# api/main.py:90
app.add_middleware(TokenAuthMiddleware)

# Random token generated on startup:
API_TOKEN: str = secrets.token_urlsafe(32)
```

### Sensitive Data Masking

✅ Config endpoint masks secrets:
```python
# api/routers/settings.py:42-51
def _mask_sensitive_keys(data, sensitive_keys=("api_key", "secret", "password", "token")):
    ...
```

---

## Testing Coverage

### API Module Coverage

From test output:
```
src/constants.py: 60.98% coverage
src/api/event_bus.py: 0.00% (omitted from coverage requirements)
src/api/schemas.py: 0.00% (omitted from coverage requirements)
```

**Note**: API modules are intentionally omitted from coverage per `.coveragerc` (integration-level testing).

### Test Pass Rate

✅ **7/7 API constant tests passing**:
```
tests/test_api/test_constants.py::TestSharedConstants::test_progress_values PASSED
tests/test_api/test_constants.py::TestSharedConstants::test_supported_extensions PASSED
tests/test_api/test_constants.py::TestSharedConstants::test_audio_extensions_is_set PASSED
tests/test_api/test_constants.py::TestSharedConstants::test_audio_file_filter PASSED
tests/test_api/test_constants.py::TestSharedConstants::test_batch_workers_default PASSED
tests/test_api/test_constants.py::TestSharedConstants::test_timeout_values PASSED
tests/test_api/test_constants.py::TestSharedConstants::test_backward_compat_with_workers PASSED
```

---

## Recommendations Summary

### Immediate Actions (P1)

1. **Update documentation** to clarify `ConfigManager.config.data` vs `AppSettings.get_all()` API
2. **Fix max_workers constant** to reflect actual enforcement (always 1)
3. **Add standardized error response schema** and global exception handler

### Future Improvements (P2)

4. Remove or deprecate `_normalize_segments` aliases
5. Move Qt-specific constants to `UIConstants` subclass
6. Add `__all__` exports to package `__init__.py` files
7. Document CoW pattern in EventBus

### Architecture Strengths to Preserve

✅ Clean Qt isolation in API modules
✅ Shared constants in single source of truth (`constants.py`)
✅ No circular imports
✅ Thread-safe singleton pattern in dependencies
✅ Proper security validation (path traversal, auth)
✅ EventBus pattern successfully replaces Qt Signals

---

## Conclusion

The dual architecture is **well-implemented** with proper separation of concerns. The legacy PySide6 apps coexist cleanly with the new Tauri+FastAPI backend without coupling or duplication.

**Key Wins**:
- Zero Qt leakage into API modules
- Shared business logic correctly abstracted
- No circular dependencies
- Security properly implemented

**Areas for Improvement**:
- Configuration API documentation clarity (P1-1)
- max_workers enforcement transparency (P1-2)
- Error response standardization (P1-3)

**Recommended Priority**: Address all P1 issues before release, consider P2 items for future refactoring cycles.

---

**Review Completed**: 2026-02-10
**Next Review**: After P1 fixes are implemented
