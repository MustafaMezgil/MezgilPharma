from dataclasses import replace

import pytest
from PyQt6.QtWidgets import QDialog, QLineEdit

from arayuz.giris_penceresi import GirisPenceresi, IlkKullaniciPenceresi
from ayarlar import VeritabaniAyari
from moduller.kullanici.servis import (
    AZAMI_HATALI_GIRIS,
    Rol,
    giris_dogrula,
    kullanici_olustur,
)
from veritabani.baglanti import Baglanti

PAROLA = "Deneme-Parola1"

pytestmark = pytest.mark.usefixtures("qt_uygulamasi")


@pytest.fixture
def kayitli_baglanti(uygulama_baglanti: Baglanti) -> Baglanti:
    kullanici_olustur(uygulama_baglanti, "test_eczaci", "Test Kişi", PAROLA, Rol.ECZACI)
    return uygulama_baglanti


@pytest.mark.usefixtures("kayitli_baglanti")
def test_dogru_bilgilerle_giris_yapilir(uygulama_ayari: VeritabaniAyari) -> None:
    pencere = GirisPenceresi(uygulama_ayari)
    pencere.kullanici_adi_alani.setText("test_eczaci")
    pencere.parola_alani.setText(PAROLA)

    pencere.giris_dugmesi.click()

    assert pencere.result() == QDialog.DialogCode.Accepted
    assert pencere.kullanici is not None
    assert pencere.kullanici.ad_soyad == "Test Kişi"


@pytest.mark.usefixtures("kayitli_baglanti")
def test_yanlis_parolada_uyari_verilir_ve_parola_temizlenir(
    uygulama_ayari: VeritabaniAyari,
) -> None:
    pencere = GirisPenceresi(uygulama_ayari)
    pencere.kullanici_adi_alani.setText("test_eczaci")
    pencere.parola_alani.setText("yanlis-parola")

    pencere.giris_dugmesi.click()

    assert pencere.kullanici is None
    assert pencere.result() != QDialog.DialogCode.Accepted
    assert pencere.hata_etiketi.text() == "Kullanıcı adı veya parola hatalı."
    assert pencere.parola_alani.text() == ""


@pytest.mark.usefixtures("kayitli_baglanti")
def test_besinci_yanlis_denemede_kilit_mesaji_gosterilir(
    uygulama_ayari: VeritabaniAyari,
) -> None:
    pencere = GirisPenceresi(uygulama_ayari)
    pencere.kullanici_adi_alani.setText("test_eczaci")
    for _ in range(AZAMI_HATALI_GIRIS):
        pencere.parola_alani.setText("yanlis-parola")
        pencere.giris_dugmesi.click()

    assert pencere.kullanici is None
    assert "15 dakika" in pencere.hata_etiketi.text()
    assert pencere.parola_alani.text() == ""


@pytest.mark.usefixtures("kayitli_baglanti")
def test_kilitliyken_dogru_parola_ile_giris_yapilamaz(
    uygulama_ayari: VeritabaniAyari,
) -> None:
    pencere = GirisPenceresi(uygulama_ayari)
    pencere.kullanici_adi_alani.setText("test_eczaci")
    for _ in range(AZAMI_HATALI_GIRIS):
        pencere.parola_alani.setText("yanlis-parola")
        pencere.giris_dugmesi.click()

    pencere.parola_alani.setText(PAROLA)
    pencere.giris_dugmesi.click()

    assert pencere.kullanici is None
    assert pencere.result() != QDialog.DialogCode.Accepted
    assert "tekrar deneyin" in pencere.hata_etiketi.text()


def test_ilk_kurulum_kurtarma_komutundan_soz_eder(uygulama_ayari: VeritabaniAyari) -> None:
    pencere = IlkKullaniciPenceresi(uygulama_ayari)
    metin = pencere.aciklama_etiketi.text()
    assert "kurtarma" in metin
    assert "sıfırlama özelliği yoktur" not in metin


def test_parola_alani_yazilani_gizler(uygulama_ayari: VeritabaniAyari) -> None:
    pencere = GirisPenceresi(uygulama_ayari)
    assert pencere.parola_alani.echoMode() == QLineEdit.EchoMode.Password


@pytest.mark.yavas
def test_baglanti_kopunca_program_dusmez_sonra_tekrar_denenebilir(
    kayitli_baglanti: Baglanti, uygulama_ayari: VeritabaniAyari
) -> None:
    pencere = GirisPenceresi(replace(uygulama_ayari, port=1))
    pencere.kullanici_adi_alani.setText("test_eczaci")
    pencere.parola_alani.setText(PAROLA)

    pencere.giris_dugmesi.click()

    assert pencere.kullanici is None
    assert "tekrar deneyin" in pencere.hata_etiketi.text()
    assert pencere.parola_alani.text() == PAROLA

    pencere.veritabani_ayari = uygulama_ayari
    pencere.giris_dugmesi.click()

    assert pencere.kullanici is not None


def _ilk_kullanici_doldur(
    pencere: IlkKullaniciPenceresi, parola: str = PAROLA, tekrar: str = PAROLA
) -> None:
    pencere.ad_soyad_alani.setText("Test Kişi")
    pencere.kullanici_adi_alani.setText("test_eczaci")
    pencere.parola_alani.setText(parola)
    pencere.parola_tekrar_alani.setText(tekrar)


def test_ilk_kullanici_eczaci_olarak_olusturulur(
    uygulama_baglanti: Baglanti, uygulama_ayari: VeritabaniAyari
) -> None:
    pencere = IlkKullaniciPenceresi(uygulama_ayari)
    _ilk_kullanici_doldur(pencere)

    pencere.kaydet_dugmesi.click()

    assert pencere.result() == QDialog.DialogCode.Accepted
    kullanici = giris_dogrula(uygulama_baglanti, "test_eczaci", PAROLA)
    assert kullanici is not None
    assert kullanici.rol is Rol.ECZACI


def test_parolalar_uyusmazsa_kullanici_olusturulmaz(
    uygulama_baglanti: Baglanti, uygulama_ayari: VeritabaniAyari
) -> None:
    pencere = IlkKullaniciPenceresi(uygulama_ayari)
    _ilk_kullanici_doldur(pencere, tekrar="Baska-Parola1")

    pencere.kaydet_dugmesi.click()

    assert pencere.result() != QDialog.DialogCode.Accepted
    assert pencere.hata_etiketi.text() == "Parolalar aynı değil."
    assert giris_dogrula(uygulama_baglanti, "test_eczaci", PAROLA) is None


@pytest.mark.usefixtures("uygulama_baglanti")
def test_kisa_parolada_turkce_uyari_gosterilir(uygulama_ayari: VeritabaniAyari) -> None:
    pencere = IlkKullaniciPenceresi(uygulama_ayari)
    _ilk_kullanici_doldur(pencere, parola="kisa", tekrar="kisa")

    pencere.kaydet_dugmesi.click()

    assert pencere.result() != QDialog.DialogCode.Accepted
    assert "en az 8" in pencere.hata_etiketi.text()


@pytest.mark.yavas
def test_ilk_kullanici_kaydinda_baglanti_yoksa_turkce_uyari_verilir(
    uygulama_ayari: VeritabaniAyari,
) -> None:
    pencere = IlkKullaniciPenceresi(replace(uygulama_ayari, port=1))
    _ilk_kullanici_doldur(pencere)

    pencere.kaydet_dugmesi.click()

    assert pencere.result() != QDialog.DialogCode.Accepted
    assert "tekrar deneyin" in pencere.hata_etiketi.text()
