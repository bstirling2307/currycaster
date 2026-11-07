# Currycaster - podcast playout software
# Copyright (c) 2024 Adam Curry
# SPDX-License-Identifier: MIT
"""Select the playback backend.

Linux and other non-Windows systems keep the original GStreamer ``playbin``
plus ``pulsesink`` graph. Windows uses a WASAPI stream fed by PyAV. Callers
see the same clip methods either way.
"""
import sys


def backend_name(platform=None):
    platform = platform or sys.platform
    if platform == "win32":
        return "wasapi"
    return "gstreamer"


def open_clip(path, app_name, device, volume, on_eos=None, start_paused=True):
    if backend_name() == "wasapi":
        from cc.playback_wasapi import WasapiClip
        return WasapiClip(path, app_name=app_name, device=device, volume=volume, on_eos=on_eos, start_paused=start_paused)
    from cc.playback_gst import GstClip
    return GstClip(path, app_name=app_name, device=device, volume=volume, on_eos=on_eos, start_paused=start_paused)
