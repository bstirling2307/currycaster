import sys
import time

import pytest

from cc.tone import write_sine_wav


def test_backend_names():
    from cc.playback import backend_name
    assert backend_name("win32") == "wasapi"
    assert backend_name("linux") == "gstreamer"


def test_linux_contract_still_uses_pulsesink():
    text = open("cc/playback_gst.py", encoding="utf-8").read()
    for required in ("playbin", "pulsesink", "application.name", "KEY_UNIT", "Discoverer"):
        assert required in text


def test_gst_clip_plays_on_the_null_sink(tmp_path):
    if sys.platform == "win32":
        pytest.skip("GStreamer playback is the Linux backend")
    pulsectl = pytest.importorskip("pulsectl")
    try:
        pulse = pulsectl.Pulse("currycaster-test")
        sinks = pulse.sink_list()
    except Exception as exc:
        pytest.skip(f"PulseAudio is not available: {exc}")
    if not sinks:
        pytest.skip("PulseAudio has no sinks")
    pytest.importorskip("gi")
    from cc.playback_gst import GstClip
    path = write_sine_wav(tmp_path / "tone.wav", seconds=3.0)
    clip = GstClip(str(path), app_name="Currycaster_Test", device=sinks[0].name, volume=0.2, start_paused=True)
    try:
        duration = clip.query_duration_ns()
        assert duration == pytest.approx(3_000_000_000, rel=0.05)
        clip.play()
        position = 0
        named = False
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            position = clip.query_position_ns() or 0
            named = any(
                item.proplist.get("application.name") == "Currycaster_Test"
                for item in pulse.sink_input_list()
            )
            if position > 50_000_000 and named:
                break
            time.sleep(0.1)
        assert named
        assert position > 50_000_000
        clip.seek_ns(0)
    finally:
        clip.close()
        pulse.close()
