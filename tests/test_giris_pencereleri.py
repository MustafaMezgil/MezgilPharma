import sqlite3
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QDialog, QLineEdit

from arayuz.giris_penceresi import GirisPenceresi, IlkKullaniciPenceresi
from moduller.kullanici.servis import Rol, giris_dogrula, kullanici_olustur
from veritabani.baglanti import baglanti_ac
from veritabani.migration import migrationlari_uygula

PAROLA = "Deneme-Parola1"

pytestmark = pytest.mark.usefixtures("qt_uygulamasi")


@pytest.fixture
def baglanti(tmp_path: Path) -> sqlite3.Connection:
    baglanti = baglanti_ac(tmp_path / "deneme.db")
    migrationlari_uygula(baglanti, yedek_klasoru=tmp_path / "yedekler")
    return baglanti


@pytest.fixture
def kayitli_baglanti(baglanti: sqlite3.Connection) -> sqlite3.Connection:
    kullanici_olustur(baglanti, "test_eczaci", "Test Kişi", PAROLA, Rol.ECZACI)
    return baglanti


def test_dogru_bilgilerle_giris_yapilir(kayitli_baglanti: sqlite3.Connection) -> None:
    pencere = GirisPenceresi(kayitli_baglanti)
    pencere.kullanici_adi_alani.setText("test_eczaci")
    pencere.parola_alani.setText(PAROLA)

    pencere.giris_dugmesi.click()

    assert pencere.result() == QDialog.DialogCode.Accepted
    assert pencere.kullanici is not None
    assert pencere.kullanici.ad_soyad == "Test Kişi"


def test_yanlis_parolada_uyari_verilir_ve_parola_temizlenir(
    kayitli_baglanti: sqlite3.Connection,
) -> None:
    pencere = GirisPenceresi(kayitli_baglanti)
    pencere.kullanici_adi_alani.setText("test_eczaci")
    pencere.parola_alani.setText("yanlis-parola")

    pencere.giris_dugmesi.click()

    assert pencere.kullanici is None
    assert pencere.result() != QDialog.DialogCode.Accepted
    assert pencere.hata_etiketi.text() == "Kullanıcı adı veya parola hatalı."
    assert pencere.parola_alani.text() == ""


def test_parola_alani_yazilani_gizler(baglanti: sqlite3.Connection) -> None:
    pencere = GirisPenceresi(baglanti)
    assert pencere.parola_alani.echoMode() == QLineEdit.EchoMode.Password


def test_giris_sirasinda_veritabani_hatasi_programi_dusurmez(
    baglanti: sqlite3.Connection,
) -> None:
    pencere = GirisPenceresi(baglanti)
    pencere.kullanici_adi_alani.setText("test_eczaci")
    pencere.parola_alani.setText(PAROLA)
    baglanti.close()

    pencere.giris_dugmesi.click()

    assert pencere.kullanici is None
    assert "tekrar deneyin" in pencere.hata_etiketi.text()


def _ilk_kullanici_doldur(
    pencere: IlkKullaniciPenceresi, parola: str = PAROLA, tekrar: str = PAROLA
) -> None:
    pencere.ad_soyad_alani.setText("Test Kişi")
    pencere.kullanici_adi_alani.setText("test_eczaci")
    pencere.parola_alani.setText(parola)
    pencere.parola_tekrar_alani.setText(tekrar)


def test_ilk_kullanici_eczaci_olarak_olusturulur(baglanti: sqlite3.Connection) -> None:
    pencere = IlkKullaniciPenceresi(baglanti)
    _ilk_kullanici_doldur(pencere)

    pencere.kaydet_dugmesi.click()

    assert pencere.result() == QDialog.DialogCode.Accepted
    kullanici = giris_dogrula(baglanti, "test_eczaci", PAROLA)
    assert kullanici is not None
    assert kullanici.rol is Rol.ECZACI


def test_parolalar_uyusmazsa_kullanici_olusturulmaz(baglanti: sqlite3.Connection) -> None:
    pencere = IlkKullaniciPenceresi(baglanti)
    _ilk_kullanici_doldur(pencere, tekrar="Baska-Parola1")

    pencere.kaydet_dugmesi.click()

    assert pencere.result() != QDialog.DialogCode.Accepted
    assert pencere.hata_etiketi.text() == "Parolalar aynı değil."
    assert giris_dogrula(baglanti, "test_eczaci", PAROLA) is None


def test_kisa_parolada_turkce_uyari_gosterilir(baglanti: sqlite3.Connection) -> None:
    pencere = IlkKullaniciPenceresi(baglanti)
    _ilk_kullanici_doldur(pencere, parola="kisa", tekrar="kisa")

    pencere.kaydet_dugmesi.click()

    assert pencere.result() != QDialog.DialogCode.Accepted
    assert "en az 8" in pencere.hata_etiketi.text()
