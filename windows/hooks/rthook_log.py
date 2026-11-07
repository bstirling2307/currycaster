# Currycaster - podcast playout software
# Copyright (c) 2024 Adam Curry
# SPDX-License-Identifier: MIT
"""Capture startup errors from the windowed Windows executable."""
import os
import sys


def _redirect_stdio():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, "currycaster")
    try:
        os.makedirs(folder, exist_ok=True)
        handle = open(os.path.join(folder, "startup.log"), "a", buffering=1, encoding="utf-8")
    except OSError:
        return
    handle.write("\n--- Currycaster start: " + " ".join(sys.argv) + " ---\n")
    sys.stdout = handle
    sys.stderr = handle


_redirect_stdio()
