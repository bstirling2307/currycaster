# Currycaster - podcast playout software
# Copyright (c) 2024 Adam Curry
# SPDX-License-Identifier: MIT

def get_log_volume(linear_value):
    """Convert a 0-100 fader value to a 0.0-1.0 cubic gain."""
    return (linear_value / 100.0) ** 3
