#!/usr/bin/env python3
# Currycaster - podcast playout software
# Copyright (c) 2024 Adam Curry
# SPDX-License-Identifier: MIT
import logging
import os
import sys

from cc import __version__
from cc.paths import configure_logging, default_media_root, display_name, merge_config, user_config_dir

configure_logging()
print(f"DEBUG: Starting Broadcast System (v{__version__} - Windows WASAPI playout)...")
logging.info("Starting currycaster %s", __version__)

import json
from cc.dnd import get_filepath_from_drop
from cc.indexer import index_audio_files
from cc.ipc import IpcServer
from cc.qt_compat import (
    QAction, QApplication, QColor, QColorDialog, QDrag, QFileDialog, QFileSystemModel,
    QFont, QFontDialog, QFrame, QGridLayout, QHBoxLayout, QInputDialog, QKeySequence,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMimeData,
    QObject, QPainter, QPen, QProgressBar, QPushButton, QShortcut, QSlider,
    QSortFilterProxyModel, QTabWidget, QThread, QTime, QTimer, QTreeView, QUrl,
    QVBoxLayout, QWidget, Qt, pyqtSignal,
)
from cc.timecode import format_player_time, reached_cue_out
from cc.volume import get_log_volume

# --- CONFIGURATION PATHS ---
USER_CONFIG_DIR = user_config_dir()
os.makedirs(USER_CONFIG_DIR, exist_ok=True)
MIDI_CONFIG_FILE = os.path.join(USER_CONFIG_DIR, "midi_config.json")
AUDIO_CONFIG_FILE = os.path.join(USER_CONFIG_DIR, "audio_config.json")
LIBRARY_INDEX_FILE = os.path.join(USER_CONFIG_DIR, "library_index.json")
CART_CONFIG_FILE = os.path.join(USER_CONFIG_DIR, "cart_config.json")
WINDOW_LAYOUT_FILE = os.path.join(USER_CONFIG_DIR, "window_layout.json")
EXPLORER_CONFIG_FILE = os.path.join(USER_CONFIG_DIR, "explorer_config.json")
AUDIO_FILE_FILTER = "Audio (*.mp3 *.wav *.ogg *.flac *.m4a *.aac *.wma)"

# --- Window State Manager ---
class WindowStateManager:
    def __init__(self):
        self.data = {}
        self.load()
    def load(self):
        if os.path.exists(WINDOW_LAYOUT_FILE):
            try:
                with open(WINDOW_LAYOUT_FILE, "r", encoding="utf-8") as f: self.data = json.load(f)
            except Exception: pass
    def save(self):
        try:
            with open(WINDOW_LAYOUT_FILE, "w", encoding="utf-8") as f: json.dump(self.data, f, indent=4)
        except Exception: pass
    def apply(self, widget, name):
        if name in self.data:
            g = self.data[name]
            widget.move(g["x"], g["y"]); widget.resize(g["w"], g["h"])
    def record(self, widget, name):
        self.data[name] = {"x": widget.x(), "y": widget.y(), "w": widget.width(), "h": widget.height()}
        self.save()

window_manager = WindowStateManager()

# --- 1. SEARCH INDEXER WORKER ---
class FileIndexerWorker(QThread):
    index_finished = pyqtSignal(list)
    def __init__(self, root_path):
        super().__init__(); self.root_path = root_path
    def run(self):
        self.index_finished.emit(index_audio_files(self.root_path))

# --- 2. AUDIO ROUTER ---
class AudioRouter:
    def __init__(self):
        self.pulse = None
        self.active_players, self.active_cart_ids, self.active_carts = [], [], []
        self._windows = sys.platform == "win32"
        self.sinks = []
        self.global_pgm_sink = None
        self.global_cue_sink = None
        if not self._windows:
            try:
                import pulsectl
            except ImportError as exc:
                raise RuntimeError("pulsectl is required on this platform. Install it with: pip install pulsectl") from exc
            self.pulse = pulsectl.Pulse("currycaster-router")
        self.sinks = self.refresh_devices()
        self.global_pgm_sink = self.sinks[0].name if self.sinks else None
        self.global_cue_sink = self.sinks[0].name if self.sinks else None
        self.load_config()
        self.heartbeat = QTimer(); self.heartbeat.timeout.connect(self._heartbeat_check); self.heartbeat.start(30000)
    def _reconnect_pulse(self):
        if self._windows: return
        try: self.pulse.close()
        except Exception: pass
        try:
            import pulsectl
            self.pulse = pulsectl.Pulse("currycaster-router")
            logging.info("AudioRouter: reconnected to PulseAudio")
        except Exception as e:
            logging.error(f"AudioRouter: reconnect failed: {e}")
    def _heartbeat_check(self):
        if self._windows:
            try: self.sinks = self.refresh_devices()
            except Exception as e: logging.warning(f"AudioRouter: device refresh failed: {e}")
            return
        try:
            self.pulse.sink_list()
        except Exception as e:
            logging.warning(f"AudioRouter: heartbeat failed ({e}), reconnecting...")
            self._reconnect_pulse()
    def refresh_devices(self):
        if self._windows:
            try:
                from cc.devices import list_output_devices
                self.sinks = list_output_devices()
            except Exception as e:
                logging.warning(f"AudioRouter: refresh_devices failed ({e})")
                self.sinks = []
            return self.sinks
        try:
            self.sinks = self.pulse.sink_list()
        except Exception as e:
            logging.warning(f"AudioRouter: refresh_devices failed ({e}), reconnecting...")
            self._reconnect_pulse()
            try: self.sinks = self.pulse.sink_list()
            except Exception: self.sinks = []
        return self.sinks
    def load_config(self):
        if not os.path.exists(AUDIO_CONFIG_FILE): return
        try:
            with open(AUDIO_CONFIG_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                an = [s.name for s in self.sinks]
                if d.get("program_sink") in an: self.global_pgm_sink = d["program_sink"]
                if d.get("cue_sink") in an: self.global_cue_sink = d["cue_sink"]
        except Exception as e: logging.warning(f"AudioRouter: load_config failed: {e}")
    def save_config(self):
        try:
            with open(AUDIO_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"program_sink": self.global_pgm_sink, "cue_sink": self.global_cue_sink}, f, indent=4)
        except Exception as e: logging.warning(f"AudioRouter: save_config failed: {e}")
    def set_program_device(self, name): self.global_pgm_sink = name; self.save_config(); self.move_all_streams()
    def set_cue_device(self, name): self.global_cue_sink = name; self.save_config(); self.move_all_streams()
    def register_player(self, p):
        if p not in self.active_players: self.active_players.append(p)
    def register_cart_id(self, cid):
        if cid not in self.active_cart_ids: self.active_cart_ids.append(cid)
    def register_cart(self, cart):
        self.register_cart_id(cart.uid)
        if cart not in self.active_carts: self.active_carts.append(cart)
    def move_all_streams(self):
        for p in self.active_players: self.route_stream(f"Currycaster_Player_{p.player_id}", p.pfl)
        for cid in self.active_cart_ids: self.route_stream(cid, False)
    def _route_wasapi(self, app_id, is_cue):
        target = self.global_cue_sink if is_cue else self.global_pgm_sink
        for player in self.active_players:
            if f"Currycaster_Player_{player.player_id}" == app_id:
                player.apply_output_device(target)
                return
        for cart in self.active_carts:
            if getattr(cart, "uid", None) == app_id:
                cart.apply_output_device(target)
                return
    def route_stream(self, app_id, is_cue, retries=8):
        if self._windows:
            self._route_wasapi(app_id, is_cue)
            return
        target = self.global_cue_sink if is_cue else self.global_pgm_sink
        def attempt(rem, reconnected=False):
            try:
                t_snk = next((s for s in self.pulse.sink_list() if s.name == target), None)
                t_str = next((i for i in self.pulse.sink_input_list() if i.proplist.get("application.name") == app_id), None)
                if t_str and t_snk and t_str.sink != t_snk.index:
                    self.pulse.sink_input_move(t_str.index, t_snk.index)
                elif rem > 0: QTimer.singleShot(150, lambda: attempt(rem - 1))
            except Exception as e:
                if not reconnected:
                    logging.warning(f"AudioRouter: route_stream({app_id}) failed ({e}), reconnecting...")
                    self._reconnect_pulse()
                    QTimer.singleShot(200, lambda: attempt(rem, reconnected=True))
                elif rem > 0:
                    logging.warning(f"AudioRouter: route_stream({app_id}) retry failed ({e}), {rem} retries left")
                    QTimer.singleShot(150, lambda: attempt(rem - 1, reconnected=True))
                else:
                    logging.error(f"AudioRouter: route_stream({app_id}) gave up after all retries: {e}")
        attempt(retries)
    def route_player(self, pid, is_cue): self.route_stream(f"Currycaster_Player_{pid}", is_cue)

# --- 3. MIDI ENGINE ---
class MidiWorker(QThread):
    midi_signal = pyqtSignal(str, int, int, int)
    def __init__(self):
        super().__init__(); self.running = True; self.port_name = None
    def run(self):
        try:
            import mido
            from cc.midi_probe import probe_midi_input_names
            if sys.platform == "win32":
                try: mido.set_backend("mido.backends.rtmidi")
                except Exception as exc: logging.warning("MIDI backend: %s", exc)
            av, _error = probe_midi_input_names()
            self.port_name = next((n for n in av if any(x in n.lower() for x in ["nano", "kontrol"])), av[0] if av else None)
            if not self.port_name: return
            with mido.open_input(self.port_name) as port:
                while self.running:
                    for m in port.iter_pending():
                        if m.type == "control_change": self.midi_signal.emit("cc", m.channel, m.control, m.value)
                        elif m.type == "note_on": self.midi_signal.emit("note", m.channel, m.note, m.velocity)
                    self.msleep(5)
        except Exception: pass
    def stop(self): self.running = False; self.wait()

class MidiMapper(QObject):
    def __init__(self):
        super().__init__(); self.l_map, self.r_map, self.registry = {}, {}, {}
        self.learning_uid = None; self.load()
    def load(self):
        if os.path.exists(MIDI_CONFIG_FILE):
            try:
                with open(MIDI_CONFIG_FILE, "r", encoding="utf-8") as f: self.l_map = json.load(f)
            except Exception: pass
    def save(self):
        try:
            with open(MIDI_CONFIG_FILE, "w", encoding="utf-8") as f: json.dump(self.l_map, f, indent=4)
        except Exception: pass
    def register(self, uid, cb):
        self.registry[uid] = cb
        if uid in self.l_map: self.r_map[self.l_map[uid]] = cb
    def handle(self, mt, ch, idx, val):
        uk = f"{mt}:{ch}:{idx}"
        if self.learning_uid and val > 0:
            self.l_map[self.learning_uid] = uk; self.save()
            self.r_map[uk] = self.registry[self.learning_uid]; self.learning_uid = None
            return
        if uk in self.r_map:
            try: self.r_map[uk](val)
            except Exception: pass
    def start_learning(self, uid): self.learning_uid = uid

# --- 4. UI COMPONENTS ---
class MidiButton(QPushButton):
    def __init__(self, t, uid, mm, cb): super().__init__(t); self.uid = uid; self.mm = mm; mm.register(uid, lambda v: cb() if v > 0 else None)
    def contextMenuEvent(self, e):
        m = QMenu(self); m.addAction(f"MIDI Learn ({self.uid})", lambda: self.mm.start_learning(self.uid)); m.exec(e.globalPos())

class MidiSlider(QSlider):
    def __init__(self, o, uid, mm, cb): super().__init__(o); self.uid = uid; self.mm = mm; mm.register(uid, lambda v: cb(int((v/127.0)*100)))
    def contextMenuEvent(self, e):
        m = QMenu(self); m.addAction(f"MIDI Learn ({self.uid})", lambda: self.mm.start_learning(self.uid)); m.exec(e.globalPos())

class ClickableLabel(QLabel):
    clicked = pyqtSignal(); right_clicked = pyqtSignal()
    def mousePressEvent(self, e): (e.button()==Qt.MouseButton.LeftButton and self.clicked.emit()) or (e.button()==Qt.MouseButton.RightButton and self.right_clicked.emit())

class DraggableListWidget(QListWidget):
    def startDrag(self, a):
        i = self.currentItem()
        if i:
            m = QMimeData(); m.setText(i.data(Qt.ItemDataRole.UserRole)); m.setUrls([QUrl.fromLocalFile(i.data(Qt.ItemDataRole.UserRole))])
            d = QDrag(self); d.setMimeData(m); d.exec(Qt.DropAction.CopyAction)

# --- 5. WAVEFORM WIDGET ---
class WaveformWidget(QFrame):
    seek_requested = pyqtSignal(float)
    cue_points_changed = pyqtSignal(float, float)
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(80)
        self.setStyleSheet("background-color: #222; border: 1px solid #444;")
        self.waveform_data, self.position_percent = [], 0.0
        self.cue_in, self.cue_out = 0.0, 1.0
        self.zoom_level, self.view_offset = 1.0, 0.0
        self.last_mouse_x, self.is_panning, self.has_moved = 0, False, False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    def load_waveform_from_file(self, file_path):
        self.waveform_data, self.zoom_level, self.view_offset = [], 1.0, 0.0
        self.cue_in, self.cue_out = 0.0, 1.0
        self.cue_points_changed.emit(0.0, 1.0)
        try:
            from cc.waveform import load_waveform_peaks
            self.waveform_data = load_waveform_peaks(file_path)
            self.update()
        except Exception:
            logging.exception("waveform failed")
    def clear_waveform(self): self.waveform_data, self.position_percent = [], 0.0; self.update()
    def set_position(self, percent): self.position_percent = percent; self.update()
    def set_start_point(self, percent): self.cue_in = max(0.0, min(percent, self.cue_out)); self.cue_points_changed.emit(self.cue_in, self.cue_out); self.update()
    def set_end_point(self, percent): self.cue_out = min(1.0, max(percent, self.cue_in)); self.cue_points_changed.emit(self.cue_in, self.cue_out); self.update()
    def reset_clip(self): self.cue_in, self.cue_out = 0.0, 1.0; self.cue_points_changed.emit(0.0, 1.0); self.update()
    def wheelEvent(self, event):
        if not self.waveform_data: return
        delta = event.angleDelta().y(); zoom_factor = 1.1 if delta > 0 else 0.9
        new_zoom = max(1.0, min(50.0, self.zoom_level * zoom_factor))
        mx, w = event.position().x(), self.width()
        tp_old = w * self.zoom_level
        mouse_pct = (mx + self.view_offset) / tp_old if tp_old > 0 else 0
        self.zoom_level = new_zoom
        self.view_offset = max(0, min((mouse_pct * w * self.zoom_level) - mx, (w * self.zoom_level) - w))
        self.update()
    def mousePressEvent(self, event):
        self.last_mouse_x, self.has_moved = event.position().x(), False
        if event.button() == Qt.MouseButton.LeftButton:
            self.seek_requested.emit(max(0.0, min(1.0, (event.position().x() + self.view_offset) / (self.width() * self.zoom_level))))
        elif event.button() == Qt.MouseButton.RightButton:
            self.is_panning = True; self.setCursor(Qt.CursorShape.ClosedHandCursor)
    def mouseMoveEvent(self, event):
        if self.is_panning:
            dx = event.position().x() - self.last_mouse_x
            if abs(dx) > 2: self.has_moved = True
            self.last_mouse_x = event.position().x()
            self.view_offset = max(0, min(self.view_offset - dx, (self.width() * self.zoom_level) - self.width()))
            self.update()
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.is_panning = False; self.setCursor(Qt.CursorShape.PointingHandCursor)
            if not self.has_moved:
                pct = max(0.0, min(1.0, (event.position().x() + self.view_offset) / (self.width() * self.zoom_level)))
                self.show_context_menu(event.globalPosition().toPoint(), pct)
    def show_context_menu(self, global_pos, percent):
        m = QMenu(self)
        m.addAction("Set Start (Cue In)", lambda: self.set_start_point(percent))
        m.addAction("Set End (Cue Out)", lambda: self.set_end_point(percent))
        m.addSeparator(); m.addAction("Reset Clip", self.reset_clip); m.exec(global_pos)
    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        mid_h = h / 2
        if not self.waveform_data: return
        p_br, p_dm = QPen(QColor("#00bcd4")), QPen(QColor("#444444"))
        num_samples = len(self.waveform_data)
        virtual_width = w * self.zoom_level
        step = virtual_width / num_samples
        for i in range(max(0, int(self.view_offset / step)), min(num_samples, int((self.view_offset + w) / step) + 1)):
            x = (i * step) - self.view_offset
            amp = self.waveform_data[i] * mid_h * 0.95
            painter.setPen(p_br if self.cue_in <= i/num_samples <= self.cue_out else p_dm)
            painter.drawLine(int(x), int(mid_h - amp), int(x), int(mid_h + amp))
        for color, pct in [("#00ff00", self.cue_in), ("#ff0000", self.cue_out), ("#ffffff", self.position_percent)]:
            x = (pct * virtual_width) - self.view_offset
            if 0 <= x <= w:
                painter.setPen(QPen(QColor(color), 2)); painter.drawLine(int(x), 0, int(x), h)

# --- 6. PLAYER MODULE ---
class PlayerModule(QWidget):
    def __init__(self, pid, mm, ar):
        super().__init__(); self.setAcceptDrops(True)
        self.player_id, self.mm, self.ar = pid, mm, ar
        self.pfl, self.playing, self.dur = False, False, 0
        self.c_in, self.c_out, self.seek_req = 0.0, 1.0, True
        self.show_remaining = True
        self.clip = None
        self.ar.register_player(self)
        self.setStyleSheet("border-right: 1px solid #333; background: #1a1a1a;")
        self.setFixedWidth(240)
        lay = QHBoxLayout(self); lay.setContentsMargins(2,2,2,2)
        l_cnt = QWidget(); l_lay = QVBoxLayout(l_cnt); l_lay.setContentsMargins(0,0,0,0)
        self.vol = MidiSlider(Qt.Orientation.Vertical, f"p{pid}_vol", mm, self.set_v_internal)
        self.vol.setRange(0, 100); self.vol.setValue(100); self.vol.valueChanged.connect(self.set_v_engine)
        self.lbl_t = ClickableLabel("00:00"); self.lbl_t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_t.setStyleSheet("font-size:24px; font-weight:bold; color:#ff5555; font-family:monospace;")
        self.lbl_t.clicked.connect(self.toggle_time_mode)
        self.lbl_s = ClickableLabel(f"Player {pid}"); self.lbl_s.setWordWrap(True)
        self.lbl_s.setStyleSheet("color:#eee; font-size:12px; font-weight:bold; min-height:40px;")
        self.lbl_s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_s.clicked.connect(self.toggle_pfl); self.lbl_s.right_clicked.connect(self.open_menu)
        self.wf = WaveformWidget(); self.wf.seek_requested.connect(self.seek_audio); self.wf.cue_points_changed.connect(self.upd_clip)
        ctrls = QHBoxLayout()
        self.b_load = QPushButton("LOAD"); self.b_play = MidiButton("PLAY", f"p{pid}_play", mm, self.toggle_play)
        self.b_stop = MidiButton("STOP", f"p{pid}_stop", mm, self.stop_audio); self.b_dump = MidiButton("DUMP", f"p{pid}_dump", mm, self.dump_track)
        for b in [self.b_load, self.b_play, self.b_stop, self.b_dump]: b.setStyleSheet("background:#333; color:white; font-size:10px; padding:6px;")
        self.b_load.clicked.connect(self.load_dialog); self.b_play.clicked.connect(self.toggle_play)
        self.b_stop.clicked.connect(self.stop_audio); self.b_dump.clicked.connect(self.dump_track)
        l_lay.addWidget(self.lbl_t); l_lay.addWidget(self.lbl_s); l_lay.addWidget(self.wf)
        ctrls.addWidget(self.b_load); ctrls.addWidget(self.b_play); ctrls.addWidget(self.b_stop); ctrls.addWidget(self.b_dump)
        l_lay.addLayout(ctrls); lay.addWidget(l_cnt); lay.addWidget(self.vol)
        self.tmr = QTimer(); self.tmr.timeout.connect(self.update_ui)
    def dragEnterEvent(self, event): (event.accept() if get_filepath_from_drop(event) else event.ignore())
    def dropEvent(self, event):
        path = get_filepath_from_drop(event)
        if path:
            self.load_track(path)
            event.accept()
    def set_v_internal(self, v): self.vol.setValue(v)
    def set_v_engine(self, v):
        if self.clip: self.clip.set_volume(get_log_volume(v))
    def apply_output_device(self, device_name):
        if self.clip: self.clip.set_device(device_name)
    def toggle_pfl(self):
        self.pfl = not self.pfl; self.lbl_s.setStyleSheet(f"color:{'#ffa500' if self.pfl else '#eee'}; font-size:12px; font-weight:bold; border:{'1px solid #ffa500' if self.pfl else 'none'};")
        self.ar.route_player(self.player_id, self.pfl)
    def toggle_time_mode(self): self.show_remaining = not self.show_remaining; self.update_ui()
    def upd_clip(self, s, e): self.c_in, self.c_out = s, e; (not self.playing) and (setattr(self, "seek_req", True) or self.wf.set_position(s))
    def load_dialog(self):
        f, _ = QFileDialog.getOpenFileName(self, "Load Audio", "", AUDIO_FILE_FILTER)
        if f: self.load_track(f)
    def _release_clip(self):
        self.tmr.stop()
        self.playing = False
        self.b_play.setText("PLAY")
        if self.clip:
            try: self.clip.close()
            except Exception: logging.exception("clip close")
            self.clip = None
    def load_track(self, path):
        self._release_clip(); self.lbl_s.setText(os.path.basename(path)); self.wf.load_waveform_from_file(path); self.dur = 0
        try:
            from cc.playback import open_clip
            target = self.ar.global_cue_sink if self.pfl else self.ar.global_pgm_sink
            self.clip = open_clip(
                path,
                app_name=f"Currycaster_Player_{self.player_id}",
                device=target,
                volume=get_log_volume(self.vol.value()),
                on_eos=None,
                start_paused=True,
            )
            dur = self.clip.query_duration_ns()
            self.dur = dur or 0
            self.update_ui_label(0); self.wf.set_position(0.0)
        except Exception as e:
            print(f"Load error: {e}")
            logging.exception("load_track failed")
            self.clip = None
        self.playing = False; self.seek_req = True
    def toggle_play(self):
        if not self.clip: return
        if self.playing:
            self.clip.pause()
            self.tmr.stop()
            self.playing = False
            self.b_play.setText("PLAY")
        else:
            if self.seek_req: self.clip.pause(); self.enforce_seek()
            self.clip.play(); self.tmr.start(40); self.playing = True; self.b_play.setText("PAUSE")
            self.ar.route_player(self.player_id, self.pfl)
    def enforce_seek(self):
        if not self.clip: return
        d = self.clip.query_duration_ns()
        if d: self.dur = d
        if self.dur > 0 and self.c_in > 0: self.clip.seek_ns(int(self.c_in * self.dur))
        self.seek_req = False
    def stop_audio(self):
        if not self.clip: return
        if self.playing:
            self.clip.pause()
            self.tmr.stop()
            self.playing = False
            self.b_play.setText("PLAY")
            self.enforce_seek(); self.wf.set_position(self.c_in); self.update_ui_label(int(self.c_in * self.dur))
        else:
            if self.dur > 0: self.clip.seek_ns(0)
            self.wf.set_position(0.0); self.update_ui_label(0)
    def dump_track(self):
        self._release_clip()
        self.lbl_t.setText("00:00")
        self.lbl_s.setText(f"Player {self.player_id}")
        self.wf.clear_waveform()
        self.dur = 0
    def seek_audio(self, p):
        if self.clip and self.dur > 0:
            if self.playing: self.clip.seek_ns(int(p * self.dur))
            else: self.c_in, self.seek_req = p, True
        self.wf.set_position(p)
    def update_ui(self):
        if not self.clip: return
        d = self.clip.query_duration_ns(); p = self.clip.query_position_ns()
        if d: self.dur = d
        if p is not None and self.dur > 0:
            if self.seek_req and p < int(self.c_in * self.dur): return
            self.wf.set_position(p / self.dur); self.update_ui_label(p)
            if reached_cue_out(p, self.dur, self.c_out): self.stop_audio()
    def update_ui_label(self, p):
        if not self.dur: return
        self.lbl_t.setText(format_player_time(p, self.dur, self.c_out, self.show_remaining))
        self.lbl_t.setStyleSheet(f"font-size:24px; font-weight:bold; color:{'#ff5555' if self.show_remaining else '#00bcd4'}; font-family:monospace;")
    def open_menu(self):
        m = QMenu(self); m.addAction("Toggle PFL", self.toggle_pfl); pm, cm = m.addMenu("Program Out"), m.addMenu("Cue Out")
        for s in self.ar.refresh_devices():
            pm.addAction(s.description, lambda n=s.name: self.ar.set_program_device(n))
            cm.addAction(s.description, lambda n=s.name: self.ar.set_cue_device(n))
        m.exec(self.lbl_s.mapToGlobal(self.lbl_s.rect().center()))
    def is_active(self): return self.clip is not None

# --- 7. CART BUTTON ---
class CartButton(QFrame):
    playing_triggered, finished_triggered = pyqtSignal(object), pyqtSignal(object)
    def __init__(self, ar, parent=None):
        super().__init__(parent); self.setAcceptDrops(True); self.setFrameShape(QFrame.Shape.StyledPanel); self.setMinimumHeight(100)
        self.ar, self.file, self.clip, self.playing = ar, None, None, False
        self.uid = f"Currycaster_Cart_{id(self)}"; self.ar.register_cart(self)
        self.c_name, self.c_color = "", "#333333"
        lay = QHBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)
        self.btn = QPushButton("EMPTY"); self.btn.setSizePolicy(self.btn.sizePolicy().Policy.Expanding, self.btn.sizePolicy().Policy.Expanding)
        self.btn.clicked.connect(self.toggle_play); self.btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.btn.customContextMenuRequested.connect(self.open_context)
        self.vol = QSlider(Qt.Orientation.Vertical); self.vol.setRange(0, 100); self.vol.setValue(100); self.vol.setFixedWidth(12); self.vol.valueChanged.connect(self.upd_vol)
        lay.addWidget(self.btn); lay.addWidget(self.vol)
    def dragEnterEvent(self, event): (event.accept() if get_filepath_from_drop(event) else event.ignore())
    def dropEvent(self, event): path = get_filepath_from_drop(event); (path and self.load_file(path) or event.accept())
    def open_context(self, pos):
        if not self.file: return
        m = QMenu(self); m.addAction("Rename Cart", self.ask_rename); m.addAction("Set Color", self.ask_color); m.addSeparator(); m.addAction("Clear Cart", self.clear_cart); m.exec(self.btn.mapToGlobal(pos))
    def ask_rename(self):
        t, ok = QInputDialog.getText(self, "Rename Cart", "New Name:", text=self.c_name)
        if ok and t: self.c_name = t; self.upd_ui()
    def ask_color(self):
        c = QColorDialog.getColor(initial=QColor(self.c_color), parent=self, title="Cart Color")
        if c.isValid(): self.c_color = c.name(); self.upd_ui()
    def clear_cart(self): self.stop(); self.file, self.c_name, self.c_color = None, "", "#333333"; self.upd_ui()
    def wheelEvent(self, event):
        cur_v = self.vol.value()
        step = 5 if event.angleDelta().y() > 0 else -5
        self.vol.setValue(max(0, min(100, cur_v + step)))
    def load_file(self, p, n=None, c=None, v=100):
        self.file = p
        self.c_name = n or os.path.basename(p)
        self.c_color = c or self.c_color
        self.vol.setValue(v)
        self.upd_ui()
    def upd_ui(self):
        self.btn.setText(self.c_name if self.file else "EMPTY")
        color = self.c_color if self.file else "#222"
        text_color = "white" if self.file else "#555"
        border = "2px solid #00ff00" if self.playing else "none"
        self.btn.setStyleSheet(f"background:{color}; color:{text_color}; font-weight:bold; font-size:11px; border:{border};")
    def toggle_play(self): self.stop() if self.playing else self.play()
    def apply_output_device(self, device_name):
        if self.clip: self.clip.set_device(device_name)
    def play(self):
        if not self.file: return
        self.stop()
        try:
            from cc.playback import open_clip
            self.clip = open_clip(
                self.file,
                app_name=self.uid,
                device=self.ar.global_pgm_sink,
                volume=get_log_volume(self.vol.value()),
                on_eos=self.stop,
                start_paused=False,
            )
        except Exception as e:
            print(f"Cart load error: {e}")
            logging.exception("cart play failed")
            self.clip = None
            return
        self.playing = True; self.upd_ui(); self.playing_triggered.emit(self)
    def stop(self):
        if self.clip:
            try: self.clip.close()
            except Exception: logging.exception("cart stop")
            self.clip = None
        self.playing = False; self.upd_ui(); self.finished_triggered.emit(self)
    def upd_vol(self):
        if self.clip: self.clip.set_volume(get_log_volume(self.vol.value()))
    def get_rem_ns(self):
        if self.clip:
            position = self.clip.query_position_ns(); duration = self.clip.query_duration_ns()
            if position is not None and duration: return duration - position
        return 0
    def get_data(self): return {"path": self.file, "name": self.c_name, "color": self.c_color, "vol": self.vol.value()}

# --- 8. FILE EXPLORER ---
class JunkFileFilter(QSortFilterProxyModel):
    def filterAcceptsRow(self, r, p):
        idx = self.sourceModel().index(r, 0, p); fn = self.sourceModel().fileName(idx)
        return not any(fn.startswith(x) for x in [".", "found."]) and fn not in ["$RECYCLE.BIN", "Recovery", "System Volume Information"]

class FileExplorerWindow(QWidget):
    file_selected = pyqtSignal(str)
    def __init__(self):
        super().__init__(); self.setWindowTitle("Library (SSD)"); self.resize(400, 700); self.setStyleSheet("background:#222; color:#eee;")
        window_manager.apply(self, "library_window"); lay = QVBoxLayout(self)
        self.root = self.load_root_path(); self.db, self.is_focused = [], False
        self.font_family, self.font_size = "Sans Serif", 10
        tb = QHBoxLayout(); self.si = QLineEdit(); self.si.setPlaceholderText("Search Library... (Ctrl+F)"); self.si.textChanged.connect(self.on_search)
        self.btn_refresh = QPushButton("Re-Index"); self.btn_refresh.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.btn_refresh.customContextMenuRequested.connect(self.show_refresh_menu); self.btn_refresh.clicked.connect(self.start_indexing)
        self.btn_select_folder = QPushButton("..."); self.btn_select_folder.setToolTip("Select Root Folder"); self.btn_select_folder.clicked.connect(self.select_root_folder)
        self.btn_font = QPushButton("Aa"); self.btn_font.clicked.connect(self.choose_font)
        tb.addWidget(self.si); tb.addWidget(self.btn_select_folder); tb.addWidget(self.btn_refresh); tb.addWidget(self.btn_font); lay.addLayout(tb)
        self.btn_focus = QPushButton("Focus on Folder"); self.btn_focus.clicked.connect(self.toggle_focus); lay.addWidget(self.btn_focus)
        self.sm = QFileSystemModel(); self.sm.setRootPath(self.root); self.pm = JunkFileFilter(); self.pm.setSourceModel(self.sm)
        self.tr = QTreeView(); self.tr.setModel(self.pm); self.tr.setDragEnabled(True); self.tr.setRootIndex(self.pm.mapFromSource(self.sm.index(self.root)))
        for i in range(1,4): self.tr.setColumnHidden(i, True)
        self.tr.setHeaderHidden(True); self.tr.clicked.connect(self.on_tree_click); lay.addWidget(self.tr)
        self.rl = DraggableListWidget(); self.rl.setVisible(False); self.rl.itemClicked.connect(self.on_list_click); lay.addWidget(self.rl); self.rl.setDragEnabled(True)
        self.progress = QProgressBar(); self.progress.setVisible(False); self.progress.setRange(0, 0); self.progress.setStyleSheet("QProgressBar { height: 4px; border: none; background: #333; } QProgressBar::chunk { background-color: #00bcd4; }")
        lay.addWidget(self.progress); QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self.si.setFocus)
        self.load_cache(); self.load_font_config(); QTimer.singleShot(1000, self.start_indexing)
        self.search_timer = QTimer(self); self.search_timer.setSingleShot(True); self.search_timer.timeout.connect(self.perform_search); self.current_query = ""
        self.update_title()
    def _read_explorer(self):
        if os.path.exists(EXPLORER_CONFIG_FILE):
            try:
                with open(EXPLORER_CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict): return data
            except Exception: pass
        return {}
    def _write_explorer(self, data):
        with open(EXPLORER_CONFIG_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)
    def load_root_path(self):
        data = self._read_explorer()
        fallback = default_media_root()
        path = data.get("root_path", fallback)
        if path and os.path.isdir(path): return path
        if os.path.isdir(fallback): return fallback
        # Linux keeps the historical show-drive path even while it is unmounted.
        if sys.platform != "win32": return fallback
        return os.path.expanduser("~")
    def save_root_path(self):
        self._write_explorer(merge_config(self._read_explorer(), {"root_path": self.root}))
    def select_root_folder(self):
        start = self.root if os.path.isdir(self.root) else os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(self, "Select Root Folder", start)
        if folder and os.path.isdir(folder):
            self.root = folder
            self.save_root_path()
            self.sm.setRootPath(self.root)
            self.tr.setRootIndex(self.pm.mapFromSource(self.sm.index(self.root)))
            self.load_cache()
            QTimer.singleShot(100, self.start_indexing)
            self.update_title()
    def update_title(self):
        self.setWindowTitle(f"Library ({display_name(self.root)})")
    def load_cache(self):
        if os.path.exists(LIBRARY_INDEX_FILE):
            try:
                with open(LIBRARY_INDEX_FILE, "r", encoding="utf-8") as f: self.db = json.load(f)
            except Exception: pass
    def load_font_config(self):
        data = self._read_explorer()
        self.font_family, self.font_size = data.get("family", "Sans Serif"), data.get("size", 10)
        self.apply_font()
    def save_font_config(self):
        self._write_explorer(merge_config(self._read_explorer(), {
            "family": self.font_family, "size": self.font_size, "root_path": self.root,
        }))
    def choose_font(self):
        f, ok = QFontDialog.getFont(QFont(self.font_family, self.font_size), self, "Select Library Font")
        if ok: self.font_family, self.font_size = f.family(), f.pointSize(); self.apply_font(); self.save_font_config()
    def apply_font(self):
        ss = f"QTreeView, QListWidget {{ background-color: #1a1a1a; border: none; font-family: '{self.font_family}'; font-size: {self.font_size}pt; }} QTreeView::item, QListWidget::item {{ padding: 5px; }} QTreeView::item:hover, QListWidget::item:hover {{ background: #333; }} QTreeView::item:selected, QListWidget::item:selected {{ background: #00bcd4; color: black; }}"
        self.tr.setStyleSheet(ss); self.rl.setStyleSheet(ss)
    def show_refresh_menu(self, pos):
        m = QMenu(self); m.addAction("Clear Library Cache", self.clear_cache); m.exec(self.btn_refresh.mapToGlobal(pos))
    def clear_cache(self):
        if os.path.exists(LIBRARY_INDEX_FILE): os.remove(LIBRARY_INDEX_FILE)
        self.db = []; self.start_indexing()
    def start_indexing(self):
        self.btn_refresh.setText("Scanning..."); self.progress.setVisible(True); self.worker = FileIndexerWorker(self.root)
        self.worker.index_finished.connect(self.on_idx_fin); self.worker.start()
    def on_idx_fin(self, db):
        self.db = db; self.btn_refresh.setText("Re-Index"); self.progress.setVisible(False)
        with open(LIBRARY_INDEX_FILE, "w", encoding="utf-8") as f: json.dump(db, f)
    def on_search(self, t): self.current_query = t; self.search_timer.start(300)
    def perform_search(self):
        q = self.current_query.strip().lower()
        if not q: self.tr.setVisible(True); self.rl.setVisible(False); return
        self.tr.setVisible(False); self.rl.setVisible(True); self.rl.clear()
        for f, p, m in self.db:
            if all(x in f.lower() for x in q.split()):
                item = QListWidgetItem(f); item.setData(Qt.ItemDataRole.UserRole, p); self.rl.addItem(item)
    def toggle_focus(self):
        if self.is_focused: self.tr.setRootIndex(self.pm.mapFromSource(self.sm.index(self.root))); self.is_focused, self.btn_focus.setText = False, "Focus on Folder"
        else:
            idx = self.tr.currentIndex()
            if idx.isValid() and self.sm.isDir(self.pm.mapToSource(idx)): self.tr.setRootIndex(idx); self.is_focused, self.btn_focus.setText = True, "Show Full Library"
    def on_tree_click(self, idx): (not self.sm.isDir(self.pm.mapToSource(idx))) and self.file_selected.emit(self.sm.filePath(self.pm.mapToSource(idx)))
    def on_list_click(self, i): self.file_selected.emit(i.data(Qt.ItemDataRole.UserRole))
    def closeEvent(self, e): window_manager.record(self, "library_window"); super().closeEvent(e)

# --- 9. CART WALL ---
class CartWallWindow(QMainWindow):
    def __init__(self, ar):
        super().__init__(); self.setWindowTitle("Cart Wall"); self.resize(300, 700); self.setStyleSheet("background:#222;")
        self.ar = ar; window_manager.apply(self, "cart_window")
        self.last_cart_dir = USER_CONFIG_DIR
        cv = QWidget(); lay = QVBoxLayout(cv); lay.setContentsMargins(0,0,0,0)
        t_lay = QHBoxLayout(); self.lbl_tmr = QLabel("00:00"); self.lbl_tmr.setStyleSheet("background:#111; color:#ff5555; font-size:32px; font-weight:bold; font-family:monospace; padding:10px; border-bottom:2px solid #333;")
        self.lbl_clk = QLabel("00:00:00"); self.lbl_clk.setStyleSheet("background:#111; color:#00bcd4; font-size:32px; font-weight:bold; font-family:monospace; padding:10px; border-bottom:2px solid #333;")
        t_lay.addWidget(self.lbl_tmr); t_lay.addWidget(self.lbl_clk); lay.addLayout(t_lay)
        self.tabs = QTabWidget(); self.tabs.setStyleSheet("QTabBar::tab { background:#333; color:#888; padding:8px 20px; } QTabBar::tab:selected { background:#555; color:white; border-bottom:2px solid #00bcd4; }")
        lay.addWidget(self.tabs); self.setCentralWidget(cv); self.carts, self.active = [], []
        for n in ["Openers", "Donations", "General", "Misc"]:
            tab = QWidget(); g = QGridLayout(tab); g.setSpacing(6); g.setContentsMargins(4,4,4,4)
            for r in range(6):
                for c in range(3):
                    cart = CartButton(ar); cart.playing_triggered.connect(self.on_start); cart.finished_triggered.connect(self.on_fin)
                    g.addWidget(cart, r, c); self.carts.append(cart)
            self.tabs.addTab(tab, n)
        self.tmr = QTimer(); self.tmr.timeout.connect(self.upd_tmr); self.tmr.start(100)
        self.clk = QTimer(); self.clk.timeout.connect(lambda: self.lbl_clk.setText(QTime.currentTime().toString("HH:mm:ss"))); self.clk.start(500); self.current_file = None; self.load()
        menu = self.menuBar(); file_menu = menu.addMenu("File")
        for act, func in [("Save", self.save_current), ("Save As...", self.save_as), ("Open...", self.open_cartwall)]:
            a = QAction(act, self); a.triggered.connect(func); file_menu.addAction(a)
    def on_start(self, c): (c not in self.active) and self.active.append(c)
    def on_fin(self, c): (c in self.active) and self.active.remove(c)
    def upd_tmr(self):
        if not self.active: self.lbl_tmr.setText("00:00"); return
        ts = int(self.active[-1].get_rem_ns() / 1e9); self.lbl_tmr.setText(f"{ts//60:02}:{ts%60:02}")
    def load(self):
        if os.path.exists(CART_CONFIG_FILE):
            try:
                with open(CART_CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.last_cart_dir = data.get("last_dir", USER_CONFIG_DIR)
                    lp = data.get("last_set")
                    if lp and os.path.exists(lp):
                        with open(lp, "r", encoding="utf-8") as j:
                            st = json.load(j)
                            for i, d in enumerate(st.get("carts", [])):
                                if i < len(self.carts) and d.get("path"): self.carts[i].load_file(d["path"], d.get("name"), d.get("color"), d.get("vol"))
                        self.current_file = lp
            except Exception: pass
    def save_current(self): self.save_to_file(self.current_file) if self.current_file else self.save_as()
    def save_as(self):
        file, _ = QFileDialog.getSaveFileName(self, "Save Cartwall", self.last_cart_dir, "JSON (*.json)")
        if file:
            self.last_cart_dir = os.path.dirname(file)
            self.save_to_file(file); self.current_file = file; self.update_last_set(file)
    def open_cartwall(self):
        file, _ = QFileDialog.getOpenFileName(self, "Open Cartwall", self.last_cart_dir, "JSON (*.json)")
        if file:
            self.last_cart_dir = os.path.dirname(file)
            self.load_from_file(file); self.current_file = file; self.update_last_set(file)
    def save_to_file(self, file_path):
        data = {"carts": [cart.get_data() for cart in self.carts]}
        with open(file_path, "w", encoding="utf-8") as f: json.dump(data, f, indent=4)
    def load_from_file(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                st = json.load(f); [c.clear_cart() for c in self.carts]
                for i, d in enumerate(st.get("carts", [])):
                    if i < len(self.carts) and d.get("path"): self.carts[i].load_file(d["path"], d.get("name"), d.get("color"), d.get("vol"))
        except Exception: pass
    def update_last_set(self, file_path):
        with open(CART_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"last_set": file_path, "last_dir": self.last_cart_dir}, f, indent=4)
    def closeEvent(self, e):
        window_manager.record(self, "cart_window")
        for cart in self.carts:
            try: cart.stop()
            except Exception: logging.exception("cart close")
        super().closeEvent(e)

# --- 10. MAIN WINDOW ---
class MainWindow(QWidget):
    def __init__(self, ar):
        super().__init__(); self.setWindowTitle("Broadcast Bar"); window_manager.apply(self, "player_window")
        self.ar, self.mm = ar, MidiMapper(); self.mw = MidiWorker(); self.mw.midi_signal.connect(self.mm.handle); self.mw.start()
        lay = QHBoxLayout(self); lay.setSpacing(0); lay.setContentsMargins(0,0,0,0); self.players = [PlayerModule(i, self.mm, ar) for i in range(1,9)]
        for p in self.players: lay.addWidget(p)
    def load_auto(self, path):
        logging.info(f"load_auto called with: {path}")
        (next((p for p in self.players if not p.is_active()), self.players[0])).load_track(path)
    def closeEvent(self, e):
        window_manager.record(self, "player_window")
        for player in self.players:
            try: player._release_clip()
            except Exception: logging.exception("player close")
        self.mw.stop()
        super().closeEvent(e)

def _configure_windows_runtime():
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.currycaster.broadcast")
    except Exception:
        logging.exception("AppUserModelID")
    try:
        import mido
        mido.set_backend("mido.backends.rtmidi")
    except Exception:
        logging.warning("Windows MIDI backend is not available", exc_info=True)

def _missing_windows_modules():
    missing = []
    for module_name in ("av", "sounddevice", "mido"):
        try:
            __import__(module_name)
        except Exception:
            missing.append(module_name)
    return missing

def _write_result(name, text):
    try:
        os.makedirs(USER_CONFIG_DIR, exist_ok=True)
        with open(os.path.join(USER_CONFIG_DIR, name), "w", encoding="utf-8") as handle:
            handle.write(text)
    except OSError:
        logging.exception("could not write %s", name)

def run_smoke():
    notes = []
    code = 1
    try:
        if sys.platform != "win32":
            from cc.playback_gst import ensure_gst
            ensure_gst()
        app = QApplication.instance() or QApplication(sys.argv)
        if hasattr(app, "setDesktopFileName"):
            app.setDesktopFileName("currycaster")
        router = AudioRouter()
        window = MainWindow(router)
        carts = CartWallWindow(router)
        library = FileExplorerWindow()
        window.show(); carts.show(); library.show()
        app.processEvents()
        from cc.tone import write_sine_wav
        wav_path = os.path.join(USER_CONFIG_DIR, "smoke-tone.wav")
        write_sine_wav(wav_path, seconds=1.0)
        window.players[0].load_track(wav_path)
        app.processEvents()
        if not window.players[0].is_active():
            raise RuntimeError("player did not load the smoke-test tone")
        if window.players[0].dur <= 0:
            raise RuntimeError("player duration was not reported")
        notes.append(f"loaded duration_ns={window.players[0].dur}")
        notes.append(f"program_sink={router.global_pgm_sink}")
        notes.append(f"players={len(window.players)} carts={len(carts.carts)}")
        window.close(); carts.close(); library.close()
        app.processEvents()
        result = "ok\n" + "\n".join(notes) + "\n"
        code = 0
    except Exception as exc:
        logging.exception("smoke failed")
        result = f"fail: {exc}\n" + "\n".join(notes) + "\n"
        code = 1
    print(result, end="")
    _write_result("smoke-result.txt", result)
    return code

def run_app():
    if sys.platform == "win32":
        _configure_windows_runtime()
        missing = _missing_windows_modules()
        if missing and not getattr(sys, "frozen", False):
            print("Missing Python packages: " + ", ".join(missing))
            print("Install them with: python -m pip install -r requirements-windows.txt")
            return 1
    else:
        try:
            from cc.playback_gst import ensure_gst
            ensure_gst()
        except Exception as exc:
            logging.exception("GStreamer init failed")
            print(f"GStreamer is required on this platform: {exc}")
            return 1
    app = QApplication(sys.argv)
    if hasattr(app, "setDesktopFileName"):
        app.setDesktopFileName("currycaster")
    router = AudioRouter()
    window = MainWindow(router)
    window.show()
    carts = CartWallWindow(router)
    carts.show()
    library = FileExplorerWindow()
    library.show()
    library.file_selected.connect(window.load_auto)
    ipc_server = IpcServer(window.load_auto)
    try:
        ipc_server.start()
    except Exception:
        logging.exception("IPC Server failed to listen on port 9876")
    code = app.exec()
    try:
        ipc_server.stop()
    except Exception:
        logging.exception("IPC stop failed")
    return code

def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if "--self-check" in args:
        from cc.selfcheck import run_self_check
        return run_self_check()
    if "--smoke" in args:
        return run_smoke()
    return run_app()

if __name__ == "__main__":
    from multiprocessing import freeze_support
    freeze_support()
    sys.exit(main())
