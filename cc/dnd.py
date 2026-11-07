# Currycaster - podcast playout software
# Copyright (c) 2024 Adam Curry
# SPDX-License-Identifier: MIT

def normalize_dropped_path(path):
    """Turn Qt's ``/C:/...`` form into a normal Windows path."""
    if path and len(path) >= 4 and path[0] == "/" and path[2] == ":" and path[1].isalpha():
        return path[1:]
    return path


def local_path_from_text(text):
    text = (text or "").strip()
    if not text:
        return ""
    if text.lower().startswith("file:"):
        from cc.qt_compat import QUrl
        local = QUrl(text).toLocalFile()
        if local:
            return normalize_dropped_path(local)
        if text.lower().startswith("file://"):
            return normalize_dropped_path(text[7:])
    return text


def get_filepath_from_drop(event):
    mime = event.mimeData()
    if mime.hasUrls():
        for url in mime.urls():
            if url.isLocalFile():
                local = normalize_dropped_path(url.toLocalFile())
                if local:
                    return local
    if mime.hasText():
        path = local_path_from_text(mime.text())
        return path or None
    return None
