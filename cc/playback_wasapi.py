# Currycaster - podcast playout software
# Copyright (c) 2024 Adam Curry
# SPDX-License-Identifier: MIT
"""Windows playback through shared-mode WASAPI.

Each player and cart opens its own stream. Program and Cue are two output
endpoints chosen in the existing device menus. A PFL toggle closes the current
stream and opens the other endpoint, which is the WASAPI equivalent of moving
a PulseAudio sink input. Shared mode (not exclusive) is required so several
players can use one interface together.
"""
import logging

from cc.devices import hostapi_for_index, resolve_output
from cc.mainthread import make_invoker
from cc.pcm_engine import CHANNELS, SAMPLE_RATE, PcmClip


class _SoundDeviceStream:
    def __init__(self, stream):
        self._stream = stream

    def start(self):
        self._stream.start()

    def stop(self):
        self._stream.stop()

    def close(self):
        self._stream.close()


def sounddevice_output_factory(callback, device_name):
    import sounddevice as sd

    device_index = resolve_output(device_name)
    kwargs = {
        "samplerate": SAMPLE_RATE,
        "channels": CHANNELS,
        "dtype": "float32",
        "callback": callback,
        "blocksize": 2048,
        "latency": "high",
    }
    if device_index is not None:
        kwargs["device"] = device_index
    hostapi = hostapi_for_index(device_index)
    if "WASAPI" in hostapi.upper():
        kwargs["extra_settings"] = sd.WasapiSettings(exclusive=False)
    logging.info("Opening WASAPI/PortAudio output name=%s index=%s hostapi=%s", device_name, device_index, hostapi or "default")
    return _SoundDeviceStream(sd.OutputStream(**kwargs))


class WasapiClip:
    def __init__(self, path, app_name, device, volume, on_eos=None, start_paused=True):
        self.app_name = app_name
        self._on_eos = on_eos
        self._invoker = make_invoker() if on_eos else None
        self._engine = PcmClip(
            path,
            volume=volume,
            device=device,
            on_eos=self._forward_eos if on_eos else None,
            output_factory=sounddevice_output_factory,
            start_paused=start_paused,
        )
        logging.info("WASAPI clip %s device=%s", app_name, device)

    def _forward_eos(self):
        callback = self._on_eos
        if callback is None:
            return
        if self._invoker is not None:
            self._invoker.call(callback)
            return
        callback()

    def set_volume(self, volume):
        self._engine.set_volume(volume)

    def set_device(self, device):
        self._engine.set_device(device)

    def play(self):
        self._engine.play()

    def pause(self):
        self._engine.pause()

    def seek_ns(self, ns):
        return self._engine.seek_ns(ns)

    def query_duration_ns(self):
        return self._engine.query_duration_ns()

    def query_position_ns(self):
        return self._engine.query_position_ns()

    def close(self):
        self._engine.close()
