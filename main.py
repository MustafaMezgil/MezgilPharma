"""Programin giris noktasi."""

import logging
import sqlite3
import sys

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from arayuz.ana_pencere import AnaPencere
from arayuz.giris_penceresi import GirisPenceresi, IlkKullaniciPenceresi
from ayarlar import Ayarlar, ayarlari_yukle
from gunluk import gunlugu_baslat
from moduller.kullanici.servis import Kullanici, aktif_kullanici_var_mi
from veritabani.baglanti import baglanti_ac
from veritabani.migration import MigrationHatasi, guncel_surum, migrationlari_uygula

_log = logging.getLogger(__name__)

_BASLIK = "Program başlatılamadı"
_GENEL_MESAJ = (
    "Veritabanı açılamadı. Program güvenlik için kapatılacak.\n"
    "Sorun devam ederse log dosyasını destek için saklayın."
)


def veritabanini_hazirla(ayarlar: Ayarlar) -> int:
    """Veritabanini acar, bekleyen migration'lari uygular ve guncel surumu dondurur."""
    baglanti = baglanti_ac(ayarlar.veritabani_yolu)
    try:
        migrationlari_uygula(baglanti, yedek_klasoru=ayarlar.yedek_klasoru)
        return guncel_surum(baglanti)
    finally:
        baglanti.close()


def kullanici_girisi(ayarlar: Ayarlar) -> Kullanici | None:
    """Gerekirse ilk hesabi olusturur, giris yaptirir. Vazgecilirse None dondurur."""
    baglanti = baglanti_ac(ayarlar.veritabani_yolu)
    try:
        if not aktif_kullanici_var_mi(baglanti):
            if IlkKullaniciPenceresi(baglanti).exec() != QDialog.DialogCode.Accepted:
                return None
        pencere = GirisPenceresi(baglanti)
        pencere.exec()
        return pencere.kullanici
    finally:
        baglanti.close()


def baslat(ayarlar: Ayarlar) -> int:
    """Programi calistirir ve cikis kodunu dondurur (0: sorunsuz, 1: acilamadi)."""
    gunlugu_baslat(ayarlar.log_klasoru)
    uygulama = QApplication.instance() or QApplication(sys.argv)
    try:
        surum = veritabanini_hazirla(ayarlar)
        kullanici = kullanici_girisi(ayarlar)
    except MigrationHatasi as hata:
        _log.exception("Veritabani guncellenemedi")
        QMessageBox.critical(None, _BASLIK, str(hata))
        return 1
    except (sqlite3.Error, OSError):
        _log.exception("Veritabani acilamadi")
        QMessageBox.critical(None, _BASLIK, _GENEL_MESAJ)
        return 1

    if kullanici is None:
        return 0

    pencere = AnaPencere(ayarlar.ortam, surum, kullanici)
    pencere.show()
    return uygulama.exec()


if __name__ == "__main__":
    sys.exit(baslat(ayarlari_yukle()))
