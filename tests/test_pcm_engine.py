import av
import numpy as np
import pytest

from cc.pcm_engine import PcmClip, SAMPLE_RATE
from cc.tone import write_sine_wav


@pytest.fixture
def tone(tmp_path):
    return str(write_sine_wav(tmp_path / "tone.wav", seconds=1.0))


def test_packaged_ffmpeg_can_decode_the_documented_formats():
    for name in ("mp3", "aac", "flac", "vorbis", "wmav2", "pcm_s16le"):
        codec = av.codec.Codec(name, "r")
        assert codec.name == name


def test_decode_duration_and_length(tone):
    clip = PcmClip(tone, start_paused=True, output_factory=None)
    try:
        assert clip.query_duration_ns() == 1_000_000_000
        samples = clip.decode_all()
    finally:
        clip.close()
    assert samples.shape[1] == 2
    assert samples.shape[0] == pytest.approx(SAMPLE_RATE, rel=0.02)
    assert float(np.max(np.abs(samples))) > 0.05


def test_seek_starts_at_the_requested_half(tone):
    clip = PcmClip(tone, start_paused=True, output_factory=None)
    try:
        assert clip.seek_ns(500_000_000)
        samples = clip.decode_all()
        assert clip.query_position_ns() == 500_000_000
    finally:
        clip.close()
    assert samples.shape[0] == pytest.approx(SAMPLE_RATE / 2, rel=0.05)


def test_mix_applies_gain_and_reports_end(tone):
    clip = PcmClip(tone, volume=0.5, start_paused=True, output_factory=None)
    try:
        chunk = np.ones((8, 2), dtype=np.float32)
        clip._queue.append(chunk)
        clip._buffered_frames = 8
        clip._playing = True
        output = np.zeros((8, 2), dtype=np.float32)
        assert clip.mix(output, 8) is False
        assert np.allclose(output, 0.5)
        clip._eof = True
        tail = np.zeros((4, 2), dtype=np.float32)
        assert clip.mix(tail, 4) is True
        assert np.all(tail == 0)
    finally:
        clip.close()
