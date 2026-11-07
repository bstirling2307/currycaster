import struct

import pytest

from cc.tone import write_sine_wav
from cc.waveform import find_ffmpeg, load_waveform_peaks, peaks_from_s16le, waveform_peaks_pyav


def test_s16le_normalization_matches_the_original_math():
    raw = struct.pack("<4h", 0, 100, -50, 25)
    assert peaks_from_s16le(raw) == [0, 1, 0.5, 0.25]
    assert peaks_from_s16le(b"") == []


def test_ffmpeg_waveform_when_available(tmp_path):
    if not find_ffmpeg():
        pytest.skip("ffmpeg is not installed")
    path = write_sine_wav(tmp_path / "tone.wav", seconds=1.0)
    peaks = load_waveform_peaks(str(path))
    assert len(peaks) == 200
    assert max(peaks) == 1


def test_pyav_waveform_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr("cc.waveform.find_ffmpeg", lambda: None)
    path = write_sine_wav(tmp_path / "tone.wav", seconds=1.0)
    peaks = load_waveform_peaks(str(path))
    assert peaks == waveform_peaks_pyav(str(path))
    assert len(peaks) == 200
    assert max(peaks) == pytest.approx(1)
