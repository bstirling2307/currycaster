# Currycaster - podcast playout software
# Copyright (c) 2024 Adam Curry
# SPDX-License-Identifier: MIT
"""Output-device list for Windows.

PulseAudio sinks stay on Linux. Here each entry exposes ``name`` and
``description`` so the existing Program/Cue menus can list WASAPI endpoints.
PortAudio also reports legacy MME and DirectSound aliases of the same
endpoint; those are hidden when WASAPI is present.
"""
import logging


class AudioDevice:
    def __init__(self, name, description, index, hostapi):
        self.name = name
        self.description = description
        self.index = index
        self.hostapi = hostapi


def _enumerate_sounddevice():
    import sounddevice as sd
    devices = []
    queried = sd.query_devices()
    for index, dev in enumerate(queried):
        devices.append({
            "index": index,
            "name": dev["name"],
            "max_output_channels": dev["max_output_channels"],
            "hostapi": dev["hostapi"],
        })
    hostapis = [{"name": api["name"]} for api in sd.query_hostapis()]
    return devices, hostapis


def list_output_devices(enumerated=None):
    if enumerated is None:
        try:
            devices, hostapis = _enumerate_sounddevice()
        except Exception as exc:
            logging.warning("WASAPI enumeration failed: %s", exc)
            return []
    else:
        devices, hostapis = enumerated
    host_names = []
    for api in hostapis:
        host_names.append(api.get("name", "") if isinstance(api, dict) else str(api))
    wasapi_ids = [index for index, name in enumerate(host_names) if "WASAPI" in name.upper()]
    outputs = []
    for fallback_index, dev in enumerate(devices):
        if dev.get("max_output_channels", 0) < 1:
            continue
        host_index = dev.get("hostapi", -1)
        if wasapi_ids and host_index not in wasapi_ids:
            continue
        index = dev.get("index", fallback_index)
        host_name = host_names[host_index] if 0 <= host_index < len(host_names) else ""
        outputs.append((index, dev.get("name") or f"Output {index}", host_name))
    counts = {}
    for _index, name, _host in outputs:
        counts[name] = counts.get(name, 0) + 1
    listed = []
    for index, name, host_name in outputs:
        if counts[name] > 1:
            identity = f"{name} [{host_name} #{index}]"
        else:
            identity = name
        description = f"{name} ({host_name})" if host_name else name
        listed.append(AudioDevice(identity, description, index, host_name))
    return listed


def resolve_output(device_name, devices=None):
    """Return a PortAudio index for a saved device name, or None for the default."""
    if not device_name:
        return None
    choices = devices if devices is not None else list_output_devices()
    for dev in choices:
        if dev.name == device_name:
            return dev.index
    return None


def hostapi_for_index(device_index, devices=None):
    if device_index is None:
        return ""
    choices = devices if devices is not None else list_output_devices()
    for dev in choices:
        if dev.index == device_index:
            return dev.hostapi or ""
    return ""
