"""Pencerelerin ortak parcalari ve veritabani islemi calistirma yardimcisi."""

import logging
from collections.abc import Callable

import psycopg
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton

from ayarlar import VeritabaniAyari
from moduller.hatalar import GorunurHata
from veritabani.baglanti import Baglanti, baglanti_ac

_log = logging.getLogger(__name__)

VERITABANI_HATA_MESAJI = "Ana makineye ulaşılamadı. Lütfen tekrar deneyin."
PAROLALAR_AYNI_DEGIL_MESAJI = "Parolalar aynı değil."


def parola_alani_olustur() -> QLineEdit:
    alan = QLineEdit()
    alan.setEchoMode(QLineEdit.EchoMode.Password)
    return alan


def hata_etiketi_olustur() -> QLabel:
    etiket = QLabel()
    etiket.setStyleSheet("color: #b00020;")
    etiket.setWordWrap(True)
    return etiket


def dugmeler_olustur(iptal: QPushButton, kaydet: QPushButton) -> QHBoxLayout:
    kaydet.setDefault(True)
    iptal.setAutoDefault(False)
    dugmeler = QHBoxLayout()
    dugmeler.addStretch()
    dugmeler.addWidget(iptal)
    dugmeler.addWidget(kaydet)
    return dugmeler


def islemi_calistir(
    ayar: VeritabaniAyari, hata_etiketi: QLabel, islem: Callable[[Baglanti], object]
) -> bool:
    """Veritabani islemini yapar; hatayi etikette Turkce gosterir, teknik ayrinti loga gider."""
    try:
        with baglanti_ac(ayar) as baglanti:
            islem(baglanti)
    except GorunurHata as hata:
        hata_etiketi.setText(str(hata))
        return False
    except psycopg.Error:
        _log.exception("Islem sirasinda veritabani hatasi")
        hata_etiketi.setText(VERITABANI_HATA_MESAJI)
        return False
    return True
