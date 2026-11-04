"""Teknik hatalarin yazildigi log dosyasi. Loglara hasta verisi yazilmaz."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_AZAMI_BOYUT = 5 * 1024 * 1024
_ESKI_DOSYA_SAYISI = 5


def gunlugu_baslat(klasor: Path) -> None:
    klasor.mkdir(parents=True, exist_ok=True)
    isleyici = RotatingFileHandler(
        klasor / "eczane.log",
        maxBytes=_AZAMI_BOYUT,
        backupCount=_ESKI_DOSYA_SAYISI,
        encoding="utf-8",
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[isleyici],
        force=True,
    )
