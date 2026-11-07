# Currycaster - podcast playout software
# Copyright (c) 2024 Adam Curry
# SPDX-License-Identifier: MIT
"""Qt binding shim.

The original application imports PyQt6. That remains the preferred binding so
existing Linux installs behave the same way. PyQt6 is GPL (or commercially
licensed), so the Windows build installs PySide6 instead. PySide6 is LGPL and
can ship beside this MIT-licensed program.

``QFileSystemModel`` lives in ``QtGui`` under PyQt6 and in ``QtWidgets`` under
PySide6. The shim exports it from whichever module actually provides it.
Set ``CURRYCASTER_QT=PySide6`` or ``CURRYCASTER_QT=PyQt6`` to force one binding.
"""
import os


def _order():
    prefer = os.environ.get("CURRYCASTER_QT", "").strip().lower()
    if prefer in {"pyside6", "pyside"}:
        return ("PySide6", "PyQt6")
    return ("PyQt6", "PySide6")


def _load_pyqt6():
    from PyQt6.QtCore import (
        QCoreApplication, QDir, QMimeData, QObject, QSortFilterProxyModel,
        QThread, QTime, QTimer, QUrl, Qt, pyqtSignal,
    )
    from PyQt6.QtGui import (
        QAction, QColor, QDrag, QFont, QKeySequence, QPainter, QPen, QShortcut,
    )
    from PyQt6 import QtGui as _QtGui
    from PyQt6.QtWidgets import (
        QApplication, QColorDialog, QFileDialog, QFontDialog, QFrame, QGridLayout,
        QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
        QMainWindow, QMenu, QProgressBar, QPushButton, QSlider, QTabWidget,
        QTreeView, QVBoxLayout, QWidget,
    )
    from PyQt6 import QtWidgets as _QtWidgets
    model = getattr(_QtGui, "QFileSystemModel", None) or _QtWidgets.QFileSystemModel
    return locals()


def _load_pyside6():
    from PySide6.QtCore import (
        QCoreApplication, QDir, QMimeData, QObject, QSortFilterProxyModel,
        QThread, QTime, QTimer, QUrl, Qt, Signal as pyqtSignal,
    )
    from PySide6.QtGui import (
        QAction, QColor, QDrag, QFont, QKeySequence, QPainter, QPen, QShortcut,
    )
    from PySide6 import QtGui as _QtGui
    from PySide6.QtWidgets import (
        QApplication, QColorDialog, QFileDialog, QFontDialog, QFrame, QGridLayout,
        QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
        QMainWindow, QMenu, QProgressBar, QPushButton, QSlider, QTabWidget,
        QTreeView, QVBoxLayout, QWidget,
    )
    from PySide6 import QtWidgets as _QtWidgets
    model = getattr(_QtGui, "QFileSystemModel", None) or _QtWidgets.QFileSystemModel
    return locals()


_LOADERS = {"PyQt6": _load_pyqt6, "PySide6": _load_pyside6}
_errors = []
_loaded = None
_selected = None
for _name in _order():
    try:
        _loaded = _LOADERS[_name]()
        _selected = _name
        break
    except ImportError as exc:
        _errors.append(exc)
if _loaded is None:
    raise ImportError(
        "Currycaster needs PyQt6 (Linux) or PySide6 (Windows). "
        + "; ".join(str(item) for item in _errors)
    )

BINDING = _selected
QFileSystemModel = _loaded.pop("model")
for _key, _value in _loaded.items():
    if _key.startswith("_"):
        continue
    globals()[_key] = _value
del _key, _value, _loaded, _errors, _selected, _LOADERS, _order
