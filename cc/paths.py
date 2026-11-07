# Currycaster - podcast playout software
# Copyright (c) 2024 Adam Curry
# SPDX-License-Identifier: MIT
"""Config locations.

Linux keeps the original ``~/.config/currycaster`` directory. Windows uses
``%APPDATA%\\currycaster``, which is the per-user equivalent.
"""
import logging
import os
import sys

LEGACY_LOG_FILE = "/home/adam/currycaster.log"
APP_DIR_NAME = "currycaster"


def user_config_dir(platform=None, environ=None, home=None):
    platform = platform or sys.platform
    environ = os.environ if environ is None else environ
    if home is None:
        home = os.path.expanduser("~")
    if platform == "win32":
        base = environ.get("APPDATA")
        if not base:
            base = os.path.join(home, "AppData", "Roaming")
        return os.path.join(base, APP_DIR_NAME)
    return os.path.join(home, ".config", APP_DIR_NAME)


def default_media_root(platform=None, home=None):
    """Library root used when no saved folder exists.

    The historical Linux default is Adam Curry's show drive. On Windows that
    path does not exist, so the user Music folder (or the profile) is used.
    """
    platform = platform or sys.platform
    if home is None:
        home = os.path.expanduser("~")
    if platform == "win32":
        music = os.path.join(home, "Music")
        if os.path.isdir(music):
            return music
        return home
    return "/run/media/adam/NO AGENDA"


def _can_append(path):
    parent = os.path.dirname(path)
    if not parent or not os.path.isdir(parent):
        return False
    try:
        with open(path, "a", encoding="utf-8"):
            return True
    except OSError:
        return False


def resolve_log_file(config_dir, platform=None, legacy_path=LEGACY_LOG_FILE):
    """Prefer the original log path when that directory is writable.

    ``/home/adam/currycaster.log`` is kept for the machine the Linux app was
    written on. Every other install logs inside the config directory.
    """
    platform = platform or sys.platform
    if platform != "win32" and legacy_path and _can_append(legacy_path):
        return legacy_path
    target = os.path.join(config_dir, "currycaster.log")
    if _can_append(target):
        return target
    return None


def configure_logging(config_dir=None):
    config_dir = config_dir or user_config_dir()
    try:
        os.makedirs(config_dir, exist_ok=True)
    except OSError:
        config_dir = None
    log_file = resolve_log_file(config_dir) if config_dir else None
    kwargs = {"level": logging.DEBUG, "format": "%(asctime)s %(message)s"}
    if log_file:
        kwargs["filename"] = log_file
        kwargs["encoding"] = "utf-8"
    logging.basicConfig(**kwargs)
    if log_file:
        logging.info("Log file: %s", log_file)
    return log_file


def merge_config(existing, updates):
    data = dict(existing) if isinstance(existing, dict) else {}
    data.update(updates)
    return data


def display_name(path):
    if not path:
        return "Library"
    short = os.path.basename(path.replace("\\", "/").rstrip("/"))
    return short or "Library"
