# Currycaster - podcast playout software
# Copyright (c) 2024 Adam Curry
# SPDX-License-Identifier: MIT
"""Qt binding shim.

The original application imports PyQt6. That remains the preferred binding so
existing Linux installs behave the same way. PyQt6 is GPL (or commercially
licensed), so the Windows build installs PySide6 instead. PySide6 is LGPL and
can ship beside this MIT-licensed program. The widget APIs used here match.
"""
try:
    from PyQt6.QtCore import (
        QCoreApplication, QDir, QMimeData, QObject, QSortFilterProxyModel,
        QThread, QTime, QTimer, QUrl, Qt, pyqtSignal,
    )
    from PyQt6.QtGui import (
        QAction, QColor, QDrag, QFileSystemModel, QFont, QKeySequence, QPainter,
        QPen, QShortcut,
    )
    from PyQt6.QtWidgets import (
        QApplication, QColorDialog, QFileDialog, QFontDialog, QFrame, QGridLayout,
        QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
        QMainWindow, QMenu, QProgressBar, QPushButton, QSlider, QTabWidget,
        QTreeView, QVBoxLayout, QWidget,
    )
    BINDING = "PyQt6"
except ImportError:  # Windows packaging, or a machine that only has PySide6
    from PySide6.QtCore import (
        QCoreApplication, QDir, QMimeData, QObject, QSortFilterProxyModel,
        QThread, QTime, QTimer, QUrl, Qt, Signal as pyqtSignal,
    )
    from PySide6.QtGui import (
        QAction, QColor, QDrag, QFileSystemModel, QFont, QKeySequence, QPainter,
        QPen, QShortcut,
    )
    from PySide6.QtWidgets import (
        QApplication, QColorDialog, QFileDialog, QFontDialog, QFrame, QGridLayout,
        QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
        QMainWindow, QMenu, QProgressBar, QPushButton, QSlider, QTabWidget,
        QTreeView, QVBoxLayout, QWidget,
    )
    BINDING = "PySide6"
