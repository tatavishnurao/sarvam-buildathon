from __future__ import annotations

import json
import logging
import math
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Any

LOG = logging.getLogger(__name__)


def inspect_wav(path: Path, pause_threshold_seconds: float = 0.6) -> dict[str, Any]:
    """Inspect PCM WAV locally; loudness is enriched only if ffmpeg exists."""
    if not path.exists():
        return {"available": False, "reason": f"WAV not found: {path}"}
    with wave.open(str(path), "rb") as handle:
        channels, width, rate, frames = handle.getnchannels(), handle.getsampwidth(), handle.getframerate(), handle.getnframes()
        raw = handle.readframes(frames)
    mono = _mono_pcm_samples(raw, width, channels)
    peak = max((abs(sample) for sample in mono), default=0)
    full_scale = float((1 << (width * 8 - 1)) - 1)
    rms = _rms(mono)
    pauses = _detect_pauses(mono, rate, pause_threshold_seconds)
    result: dict[str, Any] = {
        "available": True, "path": str(path), "channels": channels, "sample_width_bytes": width,
        "sample_rate_hz": rate, "frames": frames, "duration_seconds": frames / rate,
        "peak_dbfs": _dbfs(peak, full_scale), "rms_dbfs": _dbfs(rms, full_scale), "long_pauses": pauses,
    }
    result["integrated_loudness_lufs"] = _ffmpeg_loudness(path)
    return result


def write_audio_inspection(path: Path, output: Path) -> dict[str, Any]:
    result = inspect_wav(path)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _dbfs(value: int, full_scale: float) -> float | None:
    return round(20 * math.log10(value / full_scale), 2) if value else None


def _mono_pcm_samples(raw: bytes, width: int, channels: int) -> list[int]:
    """Decode uncompressed WAV PCM without ``audioop`` (removed in Python 3.13)."""
    if width not in (1, 2, 3, 4):
        raise ValueError(f"Unsupported PCM sample width: {width} bytes")
    frame_size = width * channels
    samples: list[int] = []
    for frame_offset in range(0, len(raw) - frame_size + 1, frame_size):
        channels_in_frame: list[int] = []
        for channel in range(channels):
            offset = frame_offset + channel * width
            data = raw[offset:offset + width]
            if width == 1:
                channels_in_frame.append(data[0] - 128)  # WAV 8-bit PCM is unsigned.
            elif width == 3:
                value = int.from_bytes(data, byteorder="little", signed=False)
                channels_in_frame.append(value - (1 << 24) if value & (1 << 23) else value)
            else:
                channels_in_frame.append(int.from_bytes(data, byteorder="little", signed=True))
        samples.append(round(sum(channels_in_frame) / channels))
    return samples


def _rms(samples: list[int]) -> int:
    return round(math.sqrt(sum(sample * sample for sample in samples) / len(samples))) if samples else 0


def _detect_pauses(samples: list[int], rate: int, minimum: float) -> list[dict[str, float]]:
    chunk_frames = max(1, rate // 20)  # 50 ms
    threshold = max(abs(sample) for sample in samples) * 0.01 if samples else 0
    runs: list[dict[str, float]] = []
    start: float | None = None
    for offset in range(0, len(samples), chunk_frames):
        silent = _rms(samples[offset:offset + chunk_frames]) <= threshold
        time = offset / rate
        if silent and start is None:
            start = time
        if not silent and start is not None:
            if time - start >= minimum:
                runs.append({"start_seconds": round(start, 3), "end_seconds": round(time, 3), "duration_seconds": round(time - start, 3)})
            start = None
    end = len(samples) / rate
    if start is not None and end - start >= minimum:
        runs.append({"start_seconds": round(start, 3), "end_seconds": round(end, 3), "duration_seconds": round(end - start, 3)})
    return runs


def _ffmpeg_loudness(path: Path) -> float | None:
    if shutil.which("ffmpeg") is None:
        return None
    process = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-filter_complex", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True, check=False)
    for line in reversed(process.stderr.splitlines()):
        if "I:" in line and "LUFS" in line:
            try:
                return float(line.split("I:", 1)[1].split("LUFS", 1)[0].strip())
            except ValueError:
                LOG.warning("Could not parse ffmpeg loudness line: %s", line)
    return None
