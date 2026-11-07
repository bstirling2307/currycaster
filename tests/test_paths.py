import os

from cc.paths import default_media_root, display_name, merge_config, resolve_log_file, user_config_dir


def test_linux_config_dir_is_unchanged(monkeypatch, tmp_path):
    monkeypatch.setattr(os.path, "expanduser", lambda _path: str(tmp_path))
    assert user_config_dir(platform="linux", home=str(tmp_path)) == os.path.join(str(tmp_path), ".config", "currycaster")


def test_windows_config_dir_uses_appdata(tmp_path):
    assert user_config_dir(platform="win32", environ={"APPDATA": str(tmp_path)}, home=str(tmp_path)) == os.path.join(str(tmp_path), "currycaster")


def test_windows_config_dir_falls_back_without_appdata(tmp_path):
    expected = os.path.join(str(tmp_path), "AppData", "Roaming", "currycaster")
    assert user_config_dir(platform="win32", environ={}, home=str(tmp_path)) == expected


def test_legacy_log_is_kept_when_writable(tmp_path):
    legacy = tmp_path / "currycaster.log"
    legacy.write_text("", encoding="utf-8")
    other = tmp_path / "config"
    other.mkdir()
    assert resolve_log_file(str(other), platform="linux", legacy_path=str(legacy)) == str(legacy)


def test_windows_log_ignores_legacy_path(tmp_path):
    legacy = tmp_path / "legacy.log"
    legacy.write_text("", encoding="utf-8")
    config = tmp_path / "config"
    config.mkdir()
    resolved = resolve_log_file(str(config), platform="win32", legacy_path=str(legacy))
    assert resolved == os.path.join(str(config), "currycaster.log")


def test_linux_media_root_stays_on_the_show_drive():
    assert default_media_root(platform="linux") == "/run/media/adam/NO AGENDA"


def test_windows_media_root_uses_music_when_present(tmp_path):
    music = tmp_path / "Music"
    music.mkdir()
    assert default_media_root(platform="win32", home=str(tmp_path)) == str(music)


def test_windows_media_root_uses_profile_without_music(tmp_path):
    assert default_media_root(platform="win32", home=str(tmp_path)) == str(tmp_path)


def test_display_name_uses_basename():
    assert display_name(r"C:\Shows\No Agenda") == "No Agenda"
    assert display_name("/run/media/adam/NO AGENDA") == "NO AGENDA"
    assert display_name("") == "Library"


def test_merge_config_keeps_unrelated_keys():
    merged = merge_config({"root_path": "/media/show", "size": 12}, {"family": "Consolas"})
    assert merged == {"root_path": "/media/show", "size": 12, "family": "Consolas"}
