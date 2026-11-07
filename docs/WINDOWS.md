# Currycaster on Windows 10/11 x64

Currycaster is podcast playout software. The Linux version routes GStreamer through PulseAudio or PipeWire. This fork keeps that path and adds a Windows build that uses the same on-screen players, cart wall, library, MIDI learn, and TCP loader.

Copyright (c) 2024 Adam Curry. The program remains under the MIT license in `LICENSE`. The Windows installer shows that license and copies it next to the executable.

## What the Windows build changes

| Linux | Windows |
| --- | --- |
| PyQt6 | PySide6 in the packaged build. Source runs with PySide6 or PyQt6. PySide6 is LGPL, which allows shipping it with this MIT program. |
| GStreamer `playbin` + `pulsesink` | PyAV decodes the file. PortAudio plays 48 kHz stereo to a WASAPI endpoint in shared mode. |
| PulseAudio sink names | WASAPI output names. Program and Cue are chosen from the same right-click menus. |
| PFL moves the PulseAudio stream | PFL closes the player's stream and opens the Cue endpoint. Expect a short gap. |
| `~/.config/currycaster/` | `%APPDATA%\currycaster` |
| Log file `/home/adam/currycaster.log` when that directory is writable | `%APPDATA%\currycaster\currycaster.log` |
| Library default `/run/media/adam/NO AGENDA` | `%USERPROFILE%\Music`, or the profile folder if Music does not exist |
| `ffmpeg` draws the waveform | The same `ffmpeg` command when `ffmpeg.exe` is on `PATH`. Otherwise PyAV draws it. |

Carts still go to Program only. Players still cue, seek, dump, and show remaining time. MIDI learn still writes `midi_config.json`. The loader still listens on `127.0.0.1:9876`.

Decoded formats follow the FFmpeg build inside the `av` wheel: MP3, WAV, FLAC, OGG Vorbis, AAC/M4A, and WMA. A RODECaster, or any other USB interface, is used by picking its WASAPI output as Program (and another output, or the same one, as Cue). The Linux PipeWire profile is not used on Windows.

## Run from source

Python 3.10 or newer, 64-bit:

```powershell
py -3 -m pip install -r requirements-windows.txt
py -3 currycaster.py
```

A missing package prints the install command and exits. Playback errors and the device list are written to `%APPDATA%\currycaster\currycaster.log`.

Check imports without opening the windows:

```powershell
py -3 currycaster.py --self-check
```

Build the windows offscreen and load a one-second tone:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
py -3 currycaster.py --smoke
```

`--self-check` confirms PyAV, PortAudio, and the MIDI backend. `--smoke` constructs the broadcast bar, cart wall, and library and loads a generated WAV. Neither one is a substitute for listening on a Windows machine.

### Load a file from another program

```powershell
$client = New-Object System.Net.Sockets.TcpClient("127.0.0.1", 9876)
$stream = $client.GetStream()
$bytes = [Text.Encoding]::UTF8.GetBytes("C:\path\to\audio.mp3")
$stream.Write($bytes, 0, $bytes.Length)
$client.Close()
```

The path must be a local file. It is loaded into the first empty player.

## Portable executable and installer

On a Windows x64 machine, from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File windows\build.ps1
```

The script installs the Windows requirements, runs the unit tests, and builds `dist\Currycaster\Currycaster.exe` with PyInstaller. If Inno Setup 6 is installed, it also writes `windows\output\Currycaster-Setup.exe`. The build is per-user by default (`PrivilegesRequired=lowest`) and is limited to Windows 10 or later, 64-bit.

GitHub Actions (`.github/workflows/windows.yml`) repeats that on `windows-latest` and uploads:

- `dist/Currycaster-windows-x64.zip` (portable folder)
- `windows/output/Currycaster-Setup.exe`

Those files are workflow artifacts, not a GitHub Release. Nothing in this port publishes a release.

The frozen executable is windowed. If it exits before the UI appears, read `%APPDATA%\currycaster\startup.log` and `currycaster.log`. `--self-check` also writes `self-check.txt` in that folder.

Install from the setup program, or unzip the portable folder and run `Currycaster.exe`. Uninstall the setup build from Windows Settings. A portable folder is removed by deleting it. Config remains in `%APPDATA%\currycaster`.

## Tests

```powershell
py -3 -m pip install -r requirements-windows.txt -r requirements-dev.txt
py -3 -m pytest -q
```

On Linux the same tests cover paths, the fader curve, waveforms, the WASAPI device filter, PyAV decode/seek/gain, IPC, MIDI learn, and, when GStreamer and PulseAudio are installed, a real `pulsesink` playback against the null sink. See the workflow for the packages that job installs.

## Not verified from this port

- Clicking through the live UI on a physical Windows desktop.
- Listening on a RODECaster or other hardware interface.
- A MIDI controller attached to a Windows machine. The backend is `python-rtmidi`; CI only checks that the library loads.
- Code signing. Windows SmartScreen will warn on the unsigned installer and executable.
- WASAPI exclusive mode. Streams are shared so several players can use one device.
- Sample-accurate scrubbing. Seeks land on the nearest earlier frame, in the same spirit as the GStreamer keyframe seek.
- Gapless PFL. Changing endpoint reopens the stream.
- A second copy of the app. The TCP port is 9876; if it is taken, the UI still opens and the log records the bind error.
