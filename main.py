"""Programin giris noktasi."""

import logging
import sys

import psycopg
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from arayuz.ana_pencere import AnaPencere
from arayuz.giris_penceresi import GirisPenceresi, IlkKullaniciPenceresi
from ayarlar import AyarHatasi, Ayarlar, ayarlari_yukle
from gunluk import gunlugu_baslat
from moduller.kullanici.servis import Kullanici, aktif_kullanici_var_mi
from veritabani.baglanti import baglanti_ac
from veritabani.migration import MigrationHatasi, surum_dogrula

_log = logging.getLogger(__name__)

_BASLIK = "Program başlatılamadı"
_BAGLANTI_MESAJI = (
    "Ana makinedeki veritabanına ulaşılamadı.\n"
    "Ana makinenin açık ve ağa bağlı olduğunu kontrol edip programı yeniden açın."
)


def veritabanini_dogrula(ayarlar: Ayarlar) -> int:
    """Veritabani bu programla uyumluysa surumunu dondurur. Yapisini degistirmez."""
    with baglanti_ac(ayarlar.veritabani) as baglanti:
        return surum_dogrula(baglanti)


def kullanici_girisi(ayarlar: Ayarlar) -> Kullanici | None:
    """Gerekirse ilk hesabi olusturur, giris yaptirir. Vazgecilirse None dondurur."""
    with baglanti_ac(ayarlar.veritabani) as baglanti:
        kullanici_var = aktif_kullanici_var_mi(baglanti)
    if not kullanici_var:
        pencere = IlkKullaniciPenceresi(ayarlar.veritabani)
        if pencere.exec() != QDialog.DialogCode.Accepted:
            return None
    giris = GirisPenceresi(ayarlar.veritabani)
    giris.exec()
    return giris.kullanici


def baslat(ayarlar: Ayarlar) -> int:
    """Programi calistirir ve cikis kodunu dondurur (0: sorunsuz, 1: acilamadi)."""
    gunlugu_baslat(ayarlar.log_klasoru)
    uygulama = QApplication.instance() or QApplication(sys.argv)
    try:
        surum = veritabanini_dogrula(ayarlar)
        kullanici = kullanici_girisi(ayarlar)
    except MigrationHatasi as hata:
        _log.exception("Veritabani surumu uyumsuz")
        QMessageBox.critical(None, _BASLIK, str(hata))
        return 1
    except (psycopg.Error, OSError):
        _log.exception("Veritabanina ulasilamadi")
        QMessageBox.critical(None, _BASLIK, _BAGLANTI_MESAJI)
        return 1

    if kullanici is None:
        return 0

    pencere = AnaPencere(ayarlar.ortam, surum, kullanici)
    pencere.show()
    return uygulama.exec()


def calistir() -> int:
    """Ayarlari okur ve programi baslatir."""
    # Pencere gosterilebilmesi icin uygulama nesnesi fonksiyon boyunca yasamalidir.
    _uygulama = QApplication.instance() or QApplication(sys.argv)
    try:
        ayarlar = ayarlari_yukle()
    except AyarHatasi as hata:
        QMessageBox.critical(None, _BASLIK, str(hata))
        return 1
    return baslat(ayarlar)


if __name__ == "__main__":
    sys.exit(calistir())
