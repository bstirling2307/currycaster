# Currycaster - podcast playout software
# Copyright (c) 2024 Adam Curry
# SPDX-License-Identifier: MIT
"""Library scan. Hidden folders and recycle-bin paths are ignored on every OS."""
import os

VALID_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma"}
_WINDOWS_SKIP_DIRS = {"SYSTEM VOLUME INFORMATION"}


def should_skip_directory(root):
    norm = root.replace("\\", "/")
    if "/." in norm or "/found." in norm or "$RECYCLE" in norm:
        return True
    base = os.path.basename(norm.rstrip("/"))
    if base.startswith(".") or base.startswith("found."):
        return True
    if base.upper() in _WINDOWS_SKIP_DIRS:
        return True
    return False


def index_audio_files(root_path):
    db = []
    try:
        for root, _dirs, files in os.walk(root_path):
            if should_skip_directory(root):
                continue
            for file in files:
                if file.startswith(".") or os.path.splitext(file)[1].lower() not in VALID_EXTENSIONS:
                    continue
                try:
                    fp = os.path.join(root, file)
                    db.append((file, fp, os.path.getmtime(fp)))
                except OSError:
                    pass
    except OSError:
        pass
    db.sort(key=lambda item: item[2], reverse=True)
    return db
