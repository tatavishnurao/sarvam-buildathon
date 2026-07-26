from __future__ import annotations

import struct
import wave
from pathlib import Path

from shorts_fidelity_judge.audio import inspect_wav


def test_wav_metadata_and_pause_detection(tmp_path: Path) -> None:
    path = tmp_path / "short.wav"
    rate = 8_000
    samples = [1000] * (rate // 10) + [0] * rate
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(rate)
        output.writeframes(struct.pack("<" + "h" * len(samples), *samples))
    inspection = inspect_wav(path)
    assert inspection["duration_seconds"] == 1.1
    assert inspection["long_pauses"][0]["duration_seconds"] >= 0.95
