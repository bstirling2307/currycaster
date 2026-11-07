# Currycaster - podcast playout software
# Copyright (c) 2024 Adam Curry
# SPDX-License-Identifier: MIT
"""List MIDI inputs in a child process.

Some PortMidi / RtMidi builds abort the process when the platform MIDI service
is missing. Probing out of process keeps the playout UI up; a failed probe just
means no controller.
"""
import logging
import subprocess
import sys

_PROBE = r"""
import sys
try:
    import mido
    if sys.platform == "win32":
        mido.set_backend("mido.backends.rtmidi")
    for name in mido.get_input_names():
        print(name)
except Exception as exc:
    sys.stderr.write(str(exc))
    sys.exit(1)
"""


def _probe_in_process():
    try:
        import mido
        if sys.platform == "win32":
            mido.set_backend("mido.backends.rtmidi")
        return list(mido.get_input_names()), ""
    except Exception as exc:
        logging.warning("MIDI probe failed: %s", exc)
        return [], str(exc)


def probe_midi_input_names(timeout=5):
    # A frozen executable cannot run ``python -c``. Windows MIDI enumeration
    # stays in-process. Linux source builds probe in a child so a broken
    # ALSA/RtMidi library cannot take down the playout process.
    if getattr(sys, "frozen", False) or sys.platform == "win32":
        return _probe_in_process()
    try:
        result = subprocess.run(
            [sys.executable, "-c", _PROBE],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logging.warning("MIDI probe failed: %s", exc)
        return [], str(exc)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or f"exit {result.returncode}").strip()
        logging.warning("MIDI probe exited %s: %s", result.returncode, detail)
        return [], detail
    names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return names, ""
