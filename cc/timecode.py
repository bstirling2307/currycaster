# Currycaster - podcast playout software
# Copyright (c) 2024 Adam Curry
# SPDX-License-Identifier: MIT

def format_player_time(position_ns, duration_ns, cue_out, show_remaining):
    """Match the original player clock, including the leading minus when remaining."""
    if not duration_ns:
        return "00:00"
    end_p = int(cue_out * duration_ns) if cue_out < 1.0 else duration_ns
    delta = end_p - position_ns if show_remaining else position_ns
    ts = int(delta / 1e9)
    prefix = "-" if show_remaining else ""
    return f"{prefix}{ts // 60:02}:{ts % 60:02}"


def reached_cue_out(position_ns, duration_ns, cue_out):
    if not duration_ns or position_ns is None:
        return False
    end_p = int(cue_out * duration_ns) if cue_out < 1.0 else duration_ns
    return position_ns >= end_p
