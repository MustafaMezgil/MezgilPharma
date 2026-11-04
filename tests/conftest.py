"""Testlerin ortak hazirliklari. Gercek veritabanina ve .env dosyasina dokunulmaz."""

import logging
import os
from collections.abc import Iterator

import pytest

# Pencereler testlerde ekranda acilmasin; PyQt6 yuklenmeden once ayarlanmalidir.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def qt_uygulamasi() -> QApplication:
    mevcut = QApplication.instance()
    if isinstance(mevcut, QApplication):
        return mevcut
    return QApplication([])


@pytest.fixture
def temiz_gunluk() -> Iterator[None]:
    """Test bitince log ayarlarini eski haline getirir ve log dosyasini kapatir."""
    kok = logging.getLogger()
    eski_isleyiciler = kok.handlers[:]
    eski_seviye = kok.level
    yield
    for isleyici in kok.handlers[:]:
        kok.removeHandler(isleyici)
        if isleyici not in eski_isleyiciler:
            isleyici.close()
    for isleyici in eski_isleyiciler:
        kok.addHandler(isleyici)
    kok.setLevel(eski_seviye)
