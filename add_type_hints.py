"""
Script to add complete type hints to all realtime transcription modules
"""

import re
import sys
from pathlib import Path

# File modifications
FILES_TO_MODIFY = [
    ("realtime_audio_capture.py", [
        # Add imports
        ("from typing import Optional, Callable",
         "from typing import Optional, Callable, List, Dict, Any, Tuple"),
        ("import numpy as np",
         "import numpy as np\nimport numpy.typing as npt"),

        # Add type hint to list_devices
        ("    def list_devices(self):",
         "    def list_devices(self) -> List[Dict[str, Any]]:"),

        # Add type hint to __enter__
        ("    def __enter__(self):",
         "    def __enter__(self) -> 'RealtimeAudioCapture':"),

        # Add type hint to __exit__
        ("    def __exit__(self, exc_type, exc_val, exc_tb):",
         "    def __exit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[Any]) -> bool:"),

        # Add type hint to _ensure_pyaudio_initialized
        ("    def _ensure_pyaudio_initialized(self):",
         "    def _ensure_pyaudio_initialized(self) -> None:"),

        # Add type hint to _audio_callback
        ("    def _audio_callback(self, in_data, frame_count, time_info, status):",
         "    def _audio_callback(self, in_data: bytes, frame_count: int, time_info: Dict[str, Any], status: int) -> Tuple[bytes, int]:"),

        # Add type hint to _capture_loop
        ("    def _capture_loop(self):",
         "    def _capture_loop(self) -> None:"),

        # Add type hint to clear_recording
        ("    def clear_recording(self):",
         "    def clear_recording(self) -> None:"),

        # Add type hint to cleanup
        ("    def cleanup(self):",
         "    def cleanup(self) -> None:"),
    ]),

    ("faster_whisper_engine.py", [
        # Add imports and type aliases
        ("from typing import Optional, Dict, List, Any",
         "from typing import Optional, Dict, List, Any, Literal"),
        ("import numpy as np",
         "import numpy as np\nimport numpy.typing as npt"),

        # Add type aliases after logger definition
        ("logger = logging.getLogger(__name__)",
         """logger = logging.getLogger(__name__)

# Type aliases for better type safety
ModelSize = Literal["tiny", "base", "small", "medium", "large-v2", "large-v3"]
ComputeType = Literal["int8", "int8_float16", "int16", "float16", "float32"]
DeviceType = Literal["auto", "cpu", "cuda"]"""),

        # Update method signatures to use type aliases
        ("    def __init__(self,\n                 model_size: str = \"base\",\n                 device: str = \"auto\",\n                 compute_type: str = \"auto\",",
         "    def __init__(self,\n                 model_size: ModelSize = \"base\",\n                 device: DeviceType = \"auto\",\n                 compute_type: ComputeType = \"auto\","),

        # Add type hint to transcribe method
        ("    def transcribe(self,\n                   audio: np.ndarray,",
         "    def transcribe(self,\n                   audio: npt.NDArray[np.float32],"),

        # Add type hint to transcribe_stream method
        ("    def transcribe_stream(self,\n                         audio_chunk: np.ndarray,",
         "    def transcribe_stream(self,\n                         audio_chunk: npt.NDArray[np.float32],"),

        # Add type hint to unload_model
        ("    def unload_model(self):",
         "    def unload_model(self) -> None:"),
    ]),

    ("simple_vad.py", [
        # Add imports
        ("from typing import Tuple",
         "from typing import Tuple, List"),
        ("import numpy as np",
         "import numpy as np\nimport numpy.typing as npt"),

        # Add type hint to calculate_energy
        ("    def calculate_energy(self, audio: np.ndarray) -> float:",
         "    def calculate_energy(self, audio: npt.NDArray[np.float32]) -> float:"),

        # Add type hint to is_speech_present
        ("    def is_speech_present(self, audio: np.ndarray) -> Tuple[bool, float]:",
         "    def is_speech_present(self, audio: npt.NDArray[np.float32]) -> Tuple[bool, float]:"),

        # Add type hint to reset
        ("    def reset(self):",
         "    def reset(self) -> None:"),

        # Add type hints to AdaptiveVAD instance variables
        ("        self.energy_history = []",
         "        self.energy_history: List[float] = []"),
    ]),

    ("realtime_transcriber.py", [
        # Type hints are already mostly complete, just add a few missing ones

        # Add type hint to run
        ("    def run(self):",
         "    def run(self) -> None:"),

        # Add type hint to _reset_error_counter
        ("    def _reset_error_counter(self):",
         "    def _reset_error_counter(self) -> None:"),

        # Add type hint to _on_audio_chunk
        ("    def _on_audio_chunk(self, audio_chunk: np.ndarray):",
         "    def _on_audio_chunk(self, audio_chunk: npt.NDArray[np.float32]) -> None:"),

        # Add type hint to clear_transcription
        ("    def clear_transcription(self):",
         "    def clear_transcription(self) -> None:"),

        # Add type hint to set_device
        ("    def set_device(self, device_index: int):",
         "    def set_device(self, device_index: int) -> bool:"),

        # Add type hint to cleanup
        ("    def cleanup(self):",
         "    def cleanup(self) -> None:"),

        # Add numpy.typing import
        ("import numpy as np",
         "import numpy as np\nimport numpy.typing as npt"),
    ]),
]


def apply_modifications(src_dir: Path):
    """Apply type hint modifications to all files"""
    modified_files = []

    for filename, modifications in FILES_TO_MODIFY:
        filepath = src_dir / filename

        if not filepath.exists():
            print(f"Warning: {filepath} not found, skipping")
            continue

        print(f"\nProcessing {filename}...")

        # Read file content
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Apply all modifications
        modified_count = 0
        for old_text, new_text in modifications:
            if old_text in content:
                content = content.replace(old_text, new_text, 1)  # Replace only first occurrence
                modified_count += 1
                print(f"  [OK] Applied: {old_text[:50]}...")
            else:
                print(f"  [SKIP] Not found: {old_text[:50]}...")

        # Write back modified content
        if modified_count > 0:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            modified_files.append(filename)
            print(f"  Saved {filename} with {modified_count} modifications")

    return modified_files


if __name__ == "__main__":
    # Determine src directory
    if len(sys.argv) > 1:
        src_dir = Path(sys.argv[1])
    else:
        src_dir = Path(__file__).parent / "src"

    print(f"Adding type hints to files in: {src_dir}")
    print("=" * 70)

    modified_files = apply_modifications(src_dir)

    print("\n" + "=" * 70)
    print(f"Complete! Modified {len(modified_files)} files:")
    for filename in modified_files:
        print(f"  - {filename}")
