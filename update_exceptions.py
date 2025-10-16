"""
Script to update files with custom exception imports and usage
"""

import re


def update_realtime_audio_capture():
    """Update realtime_audio_capture.py with custom exceptions"""
    file_path = r"F:\KotobaTranscriber\src\realtime_audio_capture.py"

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Add imports after the last import statement if not already present
    if 'from exceptions import' not in content:
        # Find the position after the last import
        import_lines = []
        lines = content.split('\n')
        last_import_idx = 0

        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                last_import_idx = i

        # Insert the new import after the last import
        exception_import = '''
from exceptions import (
    AudioDeviceNotFoundError,
    AudioStreamError,
    PyAudioInitializationError
)'''

        lines.insert(last_import_idx + 1, exception_import)
        content = '\n'.join(lines)

    # Replace error handling in __enter__
    content = re.sub(
        r'(def __enter__\(self\):.*?try:\s+self\.audio = pyaudio\.PyAudio\(\).*?)(except Exception as e:.*?)(return self)',
        r'\1except Exception as e:\n                raise PyAudioInitializationError(e)\n        \3',
        content,
        flags=re.DOTALL
    )

    # Replace error handling in _ensure_pyaudio_initialized
    content = re.sub(
        r'(def _ensure_pyaudio_initialized\(self\):.*?""".*?""".*?if self\.audio is None:\s+try:\s+self\.audio = pyaudio\.PyAudio\(\).*?)(except Exception as e:.*?$)',
        r'''\1except Exception as e:
                raise PyAudioInitializationError(e)''',
        content,
        flags=re.DOTALL | re.MULTILINE
    )

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Updated {file_path}")


def update_faster_whisper_engine():
    """Update faster_whisper_engine.py with custom exceptions"""
    file_path = r"F:\KotobaTranscriber\src\faster_whisper_engine.py"

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Add imports after the last import statement if not already present
    if 'from exceptions import' not in content:
        lines = content.split('\n')
        last_import_idx = 0

        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                if 'logger' not in line:  # Insert before logger line
                    last_import_idx = i

        exception_import = '''
from exceptions import (
    ModelLoadingError,
    TranscriptionFailedError,
    UnsupportedModelError
)'''

        lines.insert(last_import_idx + 1, exception_import)
        content = '\n'.join(lines)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Updated {file_path}")


def update_simple_vad():
    """Update simple_vad.py with custom exceptions"""
    file_path = r"F:\KotobaTranscriber\src\simple_vad.py"

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Add imports after the last import statement if not already present
    if 'from exceptions import' not in content:
        lines = content.split('\n')
        last_import_idx = 0

        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                if 'logger' not in line:
                    last_import_idx = i

        exception_import = '''
from exceptions import (
    InvalidVADThresholdError
)'''

        lines.insert(last_import_idx + 1, exception_import)
        content = '\n'.join(lines)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Updated {file_path}")


def update_realtime_transcriber():
    """Update realtime_transcriber.py with custom exceptions"""
    file_path = r"F:\KotobaTranscriber\src\realtime_transcriber.py"

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Add imports after the last import statement if not already present
    if 'from exceptions import' not in content:
        lines = content.split('\n')
        last_import_idx = 0

        for i, line in enumerate(lines):
            if (line.startswith('import ') or line.startswith('from ')) and 'logger' not in line:
                last_import_idx = i

        exception_import = '''
from exceptions import (
    AudioDeviceNotFoundError,
    AudioStreamError,
    ModelLoadingError,
    TranscriptionFailedError
)'''

        lines.insert(last_import_idx + 1, exception_import)
        content = '\n'.join(lines)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Updated {file_path}")


if __name__ == "__main__":
    print("Updating files with custom exceptions...")

    try:
        update_realtime_audio_capture()
        update_faster_whisper_engine()
        update_simple_vad()
        update_realtime_transcriber()

        print("\nAll files updated successfully!")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
