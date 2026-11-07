# Currycaster - podcast playout software
# Copyright (c) 2024 Adam Curry
# SPDX-License-Identifier: MIT
"""Decoded-PCM playback used by the Windows port.

Files are decoded with PyAV (the FFmpeg libraries shipped in the ``av`` wheel)
and handed to an output callback as 48 kHz stereo float. The output object is
injected so tests can exercise seeking, duration, and gain without a device.
On Windows the output is a shared-mode WASAPI stream opened through PortAudio.
"""
import logging
import threading
import time
from collections import deque

import numpy as np

SAMPLE_RATE = 48000
CHANNELS = 2
MAX_BUFFER_FRAMES = SAMPLE_RATE * 2


def media_duration_ns(container, stream):
    if getattr(container, "duration", None):
        return int(container.duration * 1000)
    if stream is not None and stream.duration and stream.time_base:
        return int(float(stream.duration * stream.time_base) * 1_000_000_000)
    return 0


def _as_frames(converted):
    if not converted:
        return []
    if not isinstance(converted, (list, tuple)):
        return [converted]
    return list(converted)


def _drop_leading(chunks, frames):
    if frames <= 0:
        return chunks
    kept = []
    remaining = frames
    for chunk in chunks:
        count = int(chunk.shape[0])
        if remaining >= count:
            remaining -= count
            continue
        if remaining > 0:
            chunk = chunk[remaining:]
            remaining = 0
        if chunk.shape[0]:
            kept.append(chunk)
    return kept


class NullOutput:
    def start(self):
        return None

    def stop(self):
        return None

    def close(self):
        return None


class PcmClip:
    def __init__(self, path, volume=1.0, device=None, on_eos=None, output_factory=None, start_paused=True):
        import av

        self.path = path
        self.device = device
        self._on_eos = on_eos
        self._output_factory = output_factory
        self._container = av.open(path)
        if not self._container.streams.audio:
            self._container.close()
            raise RuntimeError(f"No audio stream in {path}")
        self._stream = self._container.streams.audio[0]
        self._duration_ns = media_duration_ns(self._container, self._stream)
        self._resampler = self._make_resampler()
        self._frame_iter = None
        self._queue = deque()
        self._audio_lock = threading.Lock()
        self._decode_lock = threading.Lock()
        self._buffered_frames = 0
        self._frames_played = 0
        self._origin_ns = 0
        self._volume = float(volume)
        self._playing = False
        self._eof = False
        self._decode_eof = False
        self._eos_sent = False
        self._closed = False
        self._output = None
        self._decoder_thread = None
        self._wake = threading.Event()
        self._stop = threading.Event()
        if not start_paused:
            self.play()

    def _make_resampler(self):
        import av
        return av.audio.resampler.AudioResampler(format="fltp", layout="stereo", rate=SAMPLE_RATE)

    @property
    def duration_ns(self):
        return self._duration_ns

    def query_duration_ns(self):
        return self._duration_ns or None

    def query_position_ns(self):
        with self._audio_lock:
            position = self._origin_ns + int(self._frames_played * 1_000_000_000 / SAMPLE_RATE)
        if self._duration_ns and position > self._duration_ns:
            return self._duration_ns
        return position

    def set_volume(self, volume):
        with self._audio_lock:
            self._volume = max(0.0, float(volume))

    def set_device(self, device):
        if device == self.device:
            return
        with self._audio_lock:
            was_playing = self._playing
        self.device = device
        self._shutdown_output()
        if was_playing:
            self._ensure_output()
            self._start_output()

    def play(self):
        if self._closed:
            return
        with self._audio_lock:
            self._playing = True
        self._ensure_decoder()
        self._wake.set()
        deadline = time.monotonic() + 0.2
        while time.monotonic() < deadline:
            with self._audio_lock:
                ready = self._buffered_frames > 0 or self._eof
            if ready:
                break
            time.sleep(0.01)
        self._ensure_output()
        self._start_output()

    def pause(self):
        with self._audio_lock:
            self._playing = False
        if self._output is not None:
            try:
                self._output.stop()
            except Exception:
                logging.exception("output stop failed")

    def seek_ns(self, ns):
        ns = max(0, int(ns))
        with self._decode_lock:
            with self._audio_lock:
                self._queue.clear()
                self._buffered_frames = 0
                self._frames_played = 0
                self._origin_ns = ns
                self._eof = False
                self._decode_eof = False
                self._eos_sent = False
            try:
                self._container.seek(int(ns / 1000), backward=True, any_frame=False)
            except Exception:
                logging.exception("seek failed")
                return False
            self._resampler = self._make_resampler()
            self._frame_iter = None
        self._wake.set()
        return True

    def close(self):
        self._closed = True
        with self._audio_lock:
            self._playing = False
        self._stop.set()
        self._wake.set()
        self._shutdown_output()
        thread = self._decoder_thread
        if thread is not None and thread.is_alive() and threading.current_thread() is not thread:
            thread.join(timeout=2.0)
        try:
            self._container.close()
        except Exception:
            logging.exception("container close failed")

    def decode_all(self):
        """Decode the rest of the file without opening an output device."""
        chunks = []
        while not self._decode_eof:
            produced = self._decode_some()
            with self._audio_lock:
                while self._queue:
                    chunks.append(self._queue.popleft())
                    self._buffered_frames = 0
            if not produced and self._decode_eof:
                break
        if not chunks:
            return np.zeros((0, CHANNELS), dtype=np.float32)
        return np.concatenate(chunks, axis=0)

    def mix(self, outdata, frames):
        with self._audio_lock:
            volume = self._volume
            if not self._playing:
                outdata[:frames].fill(0)
                return False
            filled = 0
            while filled < frames and self._queue:
                chunk = self._queue[0]
                count = min(frames - filled, int(chunk.shape[0]))
                dest = outdata[filled:filled + count]
                np.multiply(chunk[:count], volume, out=dest)
                np.clip(dest, -1.0, 1.0, out=dest)
                filled += count
                self._frames_played += count
                self._buffered_frames -= count
                if count == chunk.shape[0]:
                    self._queue.popleft()
                else:
                    self._queue[0] = chunk[count:]
            if filled < frames:
                outdata[filled:frames].fill(0)
                if self._eof and self._buffered_frames <= 0 and not self._eos_sent:
                    self._eos_sent = True
                    self._playing = False
                    return True
            return False

    def _audio_callback(self, outdata, frames, _time_info, status):
        if status:
            logging.debug("PortAudio status: %s", status)
        if self.mix(outdata, frames):
            self._fire_eos()

    def _fire_eos(self):
        callback = self._on_eos
        if callback is None:
            return
        try:
            callback()
        except Exception:
            logging.exception("end-of-stream callback failed")

    def _ensure_decoder(self):
        if self._decoder_thread is not None and self._decoder_thread.is_alive():
            return
        self._decoder_thread = threading.Thread(target=self._decoder_loop, name="currycaster-decode", daemon=True)
        self._decoder_thread.start()

    def _decoder_loop(self):
        while not self._stop.is_set() and not self._closed:
            with self._audio_lock:
                buffered = self._buffered_frames
                playing = self._playing
                decode_eof = self._decode_eof
            if decode_eof or not playing or buffered >= MAX_BUFFER_FRAMES:
                self._wake.wait(0.05)
                self._wake.clear()
                continue
            try:
                self._decode_some()
            except Exception:
                logging.exception("decode failed for %s", self.path)
                with self._audio_lock:
                    self._decode_eof = True
                    self._eof = True
                break

    def _next_frame(self):
        if self._frame_iter is None:
            self._frame_iter = self._container.decode(self._stream)
        return next(self._frame_iter)

    def _resample(self, frame):
        chunks = []
        for item in _as_frames(self._resampler.resample(frame)):
            array = item.to_ndarray()
            if array.ndim == 1:
                array = array.reshape(1, -1)
            if array.shape[0] == 1:
                stereo = np.repeat(array, CHANNELS, axis=0)
            elif array.shape[0] >= 2:
                stereo = array[:CHANNELS]
            else:
                continue
            chunks.append(np.ascontiguousarray(stereo.T, dtype=np.float32))
        return chunks

    def _align(self, chunks, frame):
        if not chunks or frame is None or frame.pts is None:
            return chunks
        pts_ns = int(float(frame.pts * self._stream.time_base) * 1_000_000_000)
        target = self._origin_ns
        if pts_ns >= target:
            return chunks
        frame_rate = float(frame.sample_rate or self._stream.sample_rate or SAMPLE_RATE)
        frame_end = pts_ns + int(frame.samples / frame_rate * 1_000_000_000)
        if frame_end <= target:
            return []
        drop = int((target - pts_ns) / 1e9 * SAMPLE_RATE)
        return _drop_leading(chunks, drop)

    def _enqueue(self, chunks, eof=False):
        with self._audio_lock:
            for chunk in chunks:
                if chunk is None or chunk.size == 0:
                    continue
                self._queue.append(np.ascontiguousarray(chunk, dtype=np.float32))
                self._buffered_frames += int(chunk.shape[0])
            if eof:
                self._eof = True
                self._decode_eof = True

    def _decode_some(self):
        with self._decode_lock:
            if self._decode_eof or self._closed:
                return False
            try:
                frame = self._next_frame()
            except StopIteration:
                self._enqueue(self._resample(None), eof=True)
                return False
            self._enqueue(self._align(self._resample(frame), frame))
            return True

    def _ensure_output(self):
        if self._output is not None or self._output_factory is None:
            return
        try:
            self._output = self._output_factory(self._audio_callback, self.device)
        except Exception:
            logging.exception("Failed to open output device %s", self.device)
            self._output = NullOutput()

    def _start_output(self):
        if self._output is None:
            return
        try:
            self._output.start()
        except Exception:
            logging.exception("Failed to start output device %s", self.device)

    def _shutdown_output(self):
        output = self._output
        self._output = None
        if output is None:
            return
        try:
            output.stop()
        except Exception:
            logging.exception("output stop failed")
        try:
            output.close()
        except Exception:
            logging.exception("output close failed")
