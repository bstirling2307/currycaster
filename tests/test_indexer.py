import os

from cc.indexer import VALID_EXTENSIONS, index_audio_files, should_skip_directory


def test_supported_extensions_match_the_original_set():
    assert VALID_EXTENSIONS == {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma"}


def test_skip_rules_cover_linux_and_windows_paths():
    assert should_skip_directory("/home/adam/.hidden/files")
    assert should_skip_directory(r"C:\Users\show\.hidden")
    assert should_skip_directory("/media/found.000")
    assert should_skip_directory(r"C:\$RECYCLE.BIN\S-1")
    assert should_skip_directory(r"C:\System Volume Information")
    assert not should_skip_directory("/home/adam/NO AGENDA")
    assert not should_skip_directory(r"C:\Users\show\Music")


def test_index_sorts_newest_first_and_skips_hidden(tmp_path):
    older = tmp_path / "older.mp3"
    newer = tmp_path / "newer.wav"
    older.write_bytes(b"old")
    newer.write_bytes(b"new")
    os.utime(older, (1_000, 1_000))
    os.utime(newer, (2_000, 2_000))
    hidden = tmp_path / ".secret"
    hidden.mkdir()
    (hidden / "nope.mp3").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("no", encoding="utf-8")
    recycle = tmp_path / "$RECYCLE.BIN"
    recycle.mkdir()
    (recycle / "gone.mp3").write_bytes(b"x")
    indexed = index_audio_files(str(tmp_path))
    assert [item[0] for item in indexed] == ["newer.wav", "older.mp3"]
