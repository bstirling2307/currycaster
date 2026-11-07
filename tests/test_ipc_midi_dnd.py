import json
import socket
import time

from cc.dnd import local_path_from_text
from cc.ipc import IpcServer


def test_dropped_text_handles_linux_and_windows_urls():
    assert local_path_from_text("file:///home/user/a.mp3") == "/home/user/a.mp3"
    assert local_path_from_text("file:///C:/music/a%20b.mp3") == "C:/music/a b.mp3"
    assert local_path_from_text(r"C:\music\a.mp3") == r"C:\music\a.mp3"


def test_ipc_server_emits_the_path(qapp):
    received = []
    server = IpcServer(received.append, port=0)
    server.start()
    try:
        client = socket.create_connection((server.host, server.port), timeout=2)
        client.sendall(b"C:/media/show.mp3\n")
        client.close()
        for _ in range(50):
            qapp.processEvents()
            if received:
                break
            time.sleep(0.02)
    finally:
        server.stop()
    assert received == ["C:/media/show.mp3"]


def test_midi_learn_round_trip(qapp, tmp_path, monkeypatch):
    import currycaster
    monkeypatch.setattr(currycaster, "MIDI_CONFIG_FILE", str(tmp_path / "midi.json"))
    mapper = currycaster.MidiMapper()
    seen = []
    mapper.register("p1_play", lambda value: seen.append(value))
    mapper.start_learning("p1_play")
    mapper.handle("note", 0, 60, 127)
    assert seen == []
    mapper.handle("note", 0, 60, 100)
    assert seen == [100]
    saved = json.loads((tmp_path / "midi.json").read_text(encoding="utf-8"))
    assert saved["p1_play"] == "note:0:60"
    reloaded = currycaster.MidiMapper()
    assert reloaded.l_map["p1_play"] == "note:0:60"


def test_windows_router_points_the_player_at_the_cue_device():
    import currycaster
    router = currycaster.AudioRouter.__new__(currycaster.AudioRouter)
    router.global_pgm_sink = "Speakers"
    router.global_cue_sink = "Headphones"
    router.active_carts = []

    class Player:
        player_id = 3
        def apply_output_device(self, name):
            self.device = name

    player = Player()
    router.active_players = [player]
    router._route_wasapi("Currycaster_Player_3", True)
    assert player.device == "Headphones"
    router._route_wasapi("Currycaster_Player_3", False)
    assert player.device == "Speakers"
