from pathlib import Path

from cc import __version__
from cc.qt_compat import BINDING


def test_license_and_attribution_are_intact():
    license_text = Path("LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in license_text
    assert "Copyright (c) 2024 Adam Curry" in license_text
    assert "Permission is hereby granted" in license_text


def test_installer_is_windows_10_x64_and_matches_the_version():
    script = Path("windows/installer.iss").read_text(encoding="utf-8")
    assert f'#define MyAppVersion "{__version__}"' in script
    assert "ArchitecturesAllowed=x64compatible" in script
    assert "ArchitecturesInstallIn64BitMode=x64compatible" in script
    assert "MinVersion=10.0" in script
    assert "LicenseFile=..\\LICENSE" in script
    assert "Currycaster.exe" in script


def test_pyinstaller_spec_builds_an_onedir_windowed_app():
    spec = Path("windows/currycaster.spec").read_text(encoding="utf-8")
    assert "console=False" in spec
    assert 'name="Currycaster"' in spec
    assert "exclude_binaries=True" in spec
    assert "LICENSE" in spec


def test_qt_binding_is_one_of_the_supported_toolkits():
    assert BINDING in {"PyQt6", "PySide6"}
