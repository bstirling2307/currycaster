# -*- mode: python ; coding: utf-8 -*-
# Currycaster Windows build.
# Copyright (c) 2024 Adam Curry
# SPDX-License-Identifier: MIT
import os

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

spec_dir = SPECPATH
root = os.path.abspath(os.path.join(spec_dir, ".."))

datas = [
    (os.path.join(root, "LICENSE"), "."),
    (os.path.join(root, "README.md"), "."),
]
datas += collect_data_files("av")
try:
    datas += collect_data_files("_sounddevice_data")
except Exception:
    pass

# delvewheel looks for av.libs next to the av package. PyInstaller does not
# collect that sibling directory on its own.
try:
    import av as _av
    _av_libs = os.path.abspath(os.path.join(os.path.dirname(_av.__file__), os.pardir, "av.libs"))
    if os.path.isdir(_av_libs):
        datas.append((_av_libs, "av.libs"))
except Exception:
    pass

binaries = collect_dynamic_libs("av")

hiddenimports = [
    "mido.backends.rtmidi",
    "rtmidi",
    "numpy",
    "sounddevice",
    "_sounddevice",
    "_sounddevice_data",
    "av",
    "av.audio",
    "av.audio.resampler",
    "cc",
    "cc.paths",
    "cc.qt_compat",
    "cc.waveform",
    "cc.indexer",
    "cc.devices",
    "cc.volume",
    "cc.timecode",
    "cc.ipc",
    "cc.playback",
    "cc.playback_wasapi",
    "cc.pcm_engine",
    "cc.selfcheck",
    "cc.tone",
    "cc.dnd",
    "cc.mainthread",
]
a = Analysis(
    [os.path.join(root, "currycaster.py")],
    pathex=[root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[os.path.join(spec_dir, "hooks")],
    hooksconfig={},
    runtime_hooks=[os.path.join(spec_dir, "hooks", "rthook_log.py")],
    excludes=["gi", "gi.repository", "pulsectl", "PyQt6", "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Currycaster",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Currycaster",
)
