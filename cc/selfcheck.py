# Currycaster - podcast playout software
# Copyright (c) 2024 Adam Curry
# SPDX-License-Identifier: MIT
"""Import and device-API check used by the frozen Windows build.

This does not open an audio stream and does not draw the broadcast windows.
``--smoke`` is the separate check that constructs the UI.
"""
import logging
import os
import sys

from cc.paths import user_config_dir
from cc.playback import backend_name
from cc.qt_compat import BINDING


def run_self_check():
    lines = [f"ok: binding={BINDING}", f"ok: backend={backend_name()}", f"ok: platform={sys.platform}"]
    ok = True
    try:
        import av
        lines.append(f"ok: av={av.__version__}")
    except Exception as exc:
        ok = False
        lines.append(f"fail: av={exc}")
    try:
        import sounddevice as sd
        sd.query_hostapis()
        lines.append(f"ok: sounddevice={sd.__version__}")
    except Exception as exc:
        ok = False
        lines.append(f"fail: sounddevice={exc}")
    from cc.midi_probe import probe_midi_input_names
    names, midi_error = probe_midi_input_names()
    if midi_error and sys.platform == "win32":
        ok = False
        lines.append(f"fail: midi={midi_error}")
    elif midi_error:
        lines.append(f"warn: midi={midi_error}")
    else:
        lines.append(f"ok: midi_ports={len(names)}")
    text = "\n".join(lines) + "\n"
    print(text, end="")
    try:
        folder = user_config_dir()
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "self-check.txt"), "w", encoding="utf-8") as handle:
            handle.write(text)
    except OSError:
        logging.exception("could not write self-check.txt")
    logging.info("self-check\n%s", text)
    return 0 if ok else 1
