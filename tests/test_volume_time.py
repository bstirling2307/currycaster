from cc.timecode import format_player_time, reached_cue_out
from cc.volume import get_log_volume


def test_cubic_fader_curve():
    assert get_log_volume(0) == 0
    assert get_log_volume(100) == 1
    assert get_log_volume(50) == 0.125


def test_player_clock_matches_original_formatting():
    duration = 90 * 1_000_000_000
    assert format_player_time(0, duration, 1.0, True) == "-01:30"
    assert format_player_time(0, duration, 1.0, False) == "00:00"
    assert format_player_time(30 * 1_000_000_000, duration, 1.0, False) == "00:30"
    assert format_player_time(duration, duration, 1.0, True) == "-00:00"
    assert format_player_time(0, 60 * 1_000_000_000, 0.5, True) == "-00:30"


def test_cue_out_uses_full_duration_at_one():
    duration = 10_000_000_000
    assert reached_cue_out(duration, duration, 1.0)
    assert not reached_cue_out(duration - 1, duration, 1.0)
    assert reached_cue_out(5_000_000_000, duration, 0.5)
    assert not reached_cue_out(None, duration, 1.0)
