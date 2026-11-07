# Currycaster - podcast playout software
# Copyright (c) 2024 Adam Curry
# SPDX-License-Identifier: MIT
"""Linux playback: GStreamer playbin rendered through pulsesink.

Stream routing still belongs to pulsectl. The sink is created with the same
``application.name`` the original player used (``Currycaster_Player_N`` or the
cart id) so PulseAudio / PipeWire can move the stream between Program and Cue.
``set_device`` is intentionally a no-op after creation; moving an existing
stream is the router's job and is what keeps PFL switches glitch-free.
"""
import logging
from pathlib import Path

Gst = None
GstPbutils = None
_READY = False


def ensure_gst():
    global Gst, GstPbutils, _READY
    if _READY:
        return
    import gi
    gi.require_version("Gst", "1.0")
    gi.require_version("GstPbutils", "1.0")
    from gi.repository import Gst as _Gst
    from gi.repository import GstPbutils as _GstPbutils
    Gst = _Gst
    GstPbutils = _GstPbutils
    Gst.init(None)
    _READY = True


def discover_duration_ns(path):
    ensure_gst()
    discoverer = GstPbutils.Discoverer.new(10 * Gst.SECOND)
    info = discoverer.discover_uri(Path(path).as_uri())
    return int(info.get_duration() or 0)


class GstClip:
    def __init__(self, path, app_name, device, volume, on_eos=None, start_paused=True):
        ensure_gst()
        self.pipeline = Gst.ElementFactory.make("playbin", None)
        if self.pipeline is None:
            raise RuntimeError("GStreamer playbin is not available")
        self.pipeline.set_property("uri", Path(path).as_uri())
        sink = Gst.ElementFactory.make("pulsesink", None)
        if sink is None:
            raise RuntimeError("GStreamer pulsesink is not available")
        props = Gst.Structure.new_empty("props")
        props.set_value("application.name", app_name)
        sink.set_property("stream-properties", props)
        if device:
            sink.set_property("device", device)
        self.pipeline.set_property("audio-sink", sink)
        self.pipeline.set_property("volume", float(volume))
        self._cached_duration = 0
        try:
            self._cached_duration = discover_duration_ns(path)
        except Exception as exc:
            print(f"Discoverer error: {exc}")
            logging.warning("Discoverer error: %s", exc)
        self._on_eos = on_eos
        self._invoker = None
        if on_eos:
            from cc.mainthread import make_invoker
            self._invoker = make_invoker()
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message::eos", self._on_bus_eos)
        state = Gst.State.PAUSED if start_paused else Gst.State.PLAYING
        self.pipeline.set_state(state)
        logging.info("GStreamer clip %s device=%s", app_name, device)

    def _on_bus_eos(self, _bus, _message):
        callback = self._on_eos
        if callback is None:
            return
        if self._invoker is not None:
            self._invoker.call(callback)
            return
        callback()

    def set_volume(self, volume):
        if self.pipeline is not None:
            self.pipeline.set_property("volume", float(volume))

    def set_device(self, _device):
        return None

    def play(self):
        if self.pipeline is not None:
            self.pipeline.set_state(Gst.State.PLAYING)

    def pause(self):
        if self.pipeline is not None:
            self.pipeline.set_state(Gst.State.PAUSED)

    def seek_ns(self, ns):
        if self.pipeline is None:
            return False
        return bool(self.pipeline.seek_simple(
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            int(ns),
        ))

    def query_duration_ns(self):
        if self.pipeline is None:
            return self._cached_duration or None
        ok, duration = self.pipeline.query_duration(Gst.Format.TIME)
        if ok and duration:
            self._cached_duration = int(duration)
            return int(duration)
        return self._cached_duration or None

    def query_position_ns(self):
        if self.pipeline is None:
            return None
        ok, position = self.pipeline.query_position(Gst.Format.TIME)
        if ok:
            return int(position)
        return None

    def close(self):
        if self.pipeline is not None:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
