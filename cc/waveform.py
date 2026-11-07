# Currycaster - podcast playout software
# Copyright (c) 2024 Adam Curry
# SPDX-License-Identifier: MIT
"""Waveform peaks.

When ``ffmpeg`` is on PATH the original command is used, so Linux drawings stay
the same. A PyAV decoder is the fallback for a Windows install that does not
have ffmpeg.exe.
"""
import logging
import shutil
import struct
import subprocess


def find_ffmpeg():
    found = shutil.which("ffmpeg")
    if found:
        return found
    return None


def peaks_from_s16le(raw):
    if not raw:
        return []
    total_samples = len(raw) // 2
    if total_samples <= 0:
        return []
    samples = struct.unpack(f"<{total_samples}h", raw[: total_samples * 2])
    abs_values = [abs(sample) for sample in samples]
    max_val = max(abs_values) if abs_values else 0
    return [sample / max_val if max_val > 0 else 0 for sample in abs_values]


def waveform_peaks_ffmpeg(ffmpeg, file_path, timeout=120):
    cmd = [ffmpeg, "-i", file_path, "-f", "s16le", "-ac", "1", "-acodec", "pcm_s16le", "-ar", "200", "-vn", "-"]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout)
    if result.stdout:
        return peaks_from_s16le(result.stdout)
    raise RuntimeError(f"ffmpeg exited {result.returncode} with no audio")


def _as_frames(converted):
    if not converted:
        return []
    if not isinstance(converted, (list, tuple)):
        return [converted]
    return list(converted)


def waveform_peaks_pyav(file_path):
    import av
    import numpy as np

    container = av.open(file_path)
    try:
        if not container.streams.audio:
            return []
        stream = container.streams.audio[0]
        resampler = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=200)
        pieces = []
        for frame in container.decode(stream):
            for item in _as_frames(resampler.resample(frame)):
                pieces.append(item.to_ndarray().reshape(-1))
        for item in _as_frames(resampler.resample(None)):
            pieces.append(item.to_ndarray().reshape(-1))
    finally:
        container.close()
    if not pieces:
        return []
    joined = np.concatenate(pieces).astype(np.int32)
    max_val = int(np.max(np.abs(joined))) if joined.size else 0
    if max_val <= 0:
        return [0.0] * int(joined.size)
    return (np.abs(joined) / max_val).astype(float).tolist()


def load_waveform_peaks(file_path):
    ffmpeg = find_ffmpeg()
    if ffmpeg:
        try:
            return waveform_peaks_ffmpeg(ffmpeg, file_path)
        except Exception:
            logging.exception("ffmpeg waveform failed for %s", file_path)
    try:
        return waveform_peaks_pyav(file_path)
    except Exception:
        logging.exception("PyAV waveform failed for %s", file_path)
        return []
