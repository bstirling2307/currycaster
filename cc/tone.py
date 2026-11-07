# Currycaster - podcast playout software
# Copyright (c) 2024 Adam Curry
# SPDX-License-Identifier: MIT
"""Tiny PCM fixture writer used by tests and the Windows smoke check."""
import math
import os
import struct
import wave


def write_sine_wav(path, seconds=1.0, rate=8000, freq=440.0, amplitude=10000):
    path = os.fspath(path)
    count = int(seconds * rate)
    with wave.open(path, "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        frames = bytearray()
        for index in range(count):
            sample = int(amplitude * math.sin(2 * math.pi * freq * index / rate))
            frames += struct.pack("<h", sample)
        handle.writeframes(frames)
    return path
