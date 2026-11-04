"""Kullanicilar ekrani ile parola degistirme ve kullanici ekleme pencereleri."""

from dataclasses import replace

import pytest
from PyQt6.QtWidgets import QDialog, QMessageBox, QWidget

from arayuz.kullanici_penceresi import (
    KullaniciEklePenceresi,
    KullanicilarPenceresi,
    ParolaDegistirPenceresi,
    ParolaSifirlaPenceresi,
)
from ayarlar import VeritabaniAyari
from moduller.kullanici.servis import (
    AZAMI_HATALI_GIRIS,
    HesapKilitliHatasi,
    Kullanici,
    KullaniciOzeti,
    Rol,
    giris_dogrula,
    kullanici_olustur,
    kullanicilari_listele,
)
from veritabani.baglanti import Baglanti

PAROLA = "Deneme-Parola1"
GECICI = "Gecici-Parola1"
YENI = "Yeni-Parola-123"

pytestmark = pytest.mark.usefixtures("qt_uygulamasi")


def _giris(baglanti: Baglanti, kullanici_adi: str, parola: str = PAROLA) -> Kullanici:
    kullanici = giris_dogrula(baglanti, kullanici_adi, parola)
    assert kullanici is not None
    return kullanici


@pytest.fixture
def eczaci(uygulama_baglanti: Baglanti) -> Kullanici:
    kullanici_olustur(uygulama_baglanti, "eczaci1", "Birinci Eczacı", PAROLA, Rol.ECZACI)
    return _giris(uygulama_baglanti, "eczaci1")


@pytest.fixture
def personel(uygulama_baglanti: Baglanti, eczaci: Kullanici) -> Kullanici:
    kullanici_olustur(uygulama_baglanti, "personel1", "Birinci Personel", PAROLA, Rol.PERSONEL)
    return _giris(uygulama_baglanti, "personel1")


def _ozet(baglanti: Baglanti, yapan: Kullanici, kullanici_adi: str) -> KullaniciOzeti:
    for ozet in kullanicilari_listele(baglanti, yapan):
        if ozet.kullanici_adi == kullanici_adi:
            return ozet
    raise AssertionError(kullanici_adi)


def _satiri_sec(pencere: KullanicilarPenceresi, kullanici_adi: str) -> None:
    for satir in range(pencere.tablo.rowCount()):
        hucre = pencere.tablo.item(satir, 1)
        if hucre is not None and hucre.text() == kullanici_adi:
            pencere.tablo.selectRow(satir)
            return
    raise AssertionError(kullanici_adi)


def _onayla(monkeypatch: pytest.MonkeyPatch, yanit: QMessageBox.StandardButton) -> list[str]:
    sorular: list[str] = []

    def _soru(_ust: QWidget | None, _baslik: str, metin: str) -> QMessageBox.StandardButton:
        sorular.append(metin)
        return yanit

    monkeypatch.setattr(QMessageBox, "question", _soru)
    return sorular


# --- Kullanici ekleme penceresi ---


def _ekleme_doldur(pencere: KullaniciEklePenceresi, tekrar: str = GECICI) -> None:
    pencere.ad_soyad_alani.setText("Yeni Kişi")
    pencere.kullanici_adi_alani.setText("yeni")
    pencere.parola_alani.setText(GECICI)
    pencere.parola_tekrar_alani.setText(tekrar)


def test_ekleme_penceresi_varsayilan_olarak_personel_ekler(
    uygulama_baglanti: Baglanti, uygulama_ayari: VeritabaniAyari, eczaci: Kullanici
) -> None:
    pencere = KullaniciEklePenceresi(uygulama_ayari, eczaci)
    _ekleme_doldur(pencere)

    pencere.kaydet_dugmesi.click()

    assert pencere.result() == QDialog.DialogCode.Accepted
    giren = _giris(uygulama_baglanti, "yeni", GECICI)
    assert giren.rol is Rol.PERSONEL
    assert giren.parola_degismeli


def test_ekleme_penceresinde_eczaci_rolu_secilebilir(
    uygulama_baglanti: Baglanti, uygulama_ayari: VeritabaniAyari, eczaci: Kullanici
) -> None:
    pencere = KullaniciEklePenceresi(uygulama_ayari, eczaci)
    _ekleme_doldur(pencere)
    pencere.rol_secimi.setCurrentIndex(pencere.rol_secimi.findData(Rol.ECZACI))

    pencere.kaydet_dugmesi.click()

    assert _giris(uygulama_baglanti, "yeni", GECICI).rol is Rol.ECZACI


def test_ekleme_penceresinde_parolalar_uyusmazsa_kayit_olmaz(
    uygulama_baglanti: Baglanti, uygulama_ayari: VeritabaniAyari, eczaci: Kullanici
) -> None:
    pencere = KullaniciEklePenceresi(uygulama_ayari, eczaci)
    _ekleme_doldur(pencere, tekrar="Baska-Parola1")

    pencere.kaydet_dugmesi.click()

    assert pencere.result() != QDialog.DialogCode.Accepted
    assert pencere.hata_etiketi.text() == "Parolalar aynı değil."
    assert giris_dogrula(uygulama_baglanti, "yeni", GECICI) is None


def test_ekleme_penceresi_baglanti_yoksa_turkce_uyari_verir(
    uygulama_ayari: VeritabaniAyari, eczaci: Kullanici
) -> None:
    pencere = KullaniciEklePenceresi(replace(uygulama_ayari, port=1), eczaci)
    _ekleme_doldur(pencere)

    pencere.kaydet_dugmesi.click()

    assert pencere.result() != QDialog.DialogCode.Accepted
    assert "tekrar deneyin" in pencere.hata_etiketi.text()


# --- Parola sifirlama penceresi ---


def test_sifirlama_penceresi_parolayi_degistirir(
    uygulama_baglanti: Baglanti,
    uygulama_ayari: VeritabaniAyari,
    eczaci: Kullanici,
    personel: Kullanici,
) -> None:
    hedef = _ozet(uygulama_baglanti, eczaci, personel.kullanici_adi)
    pencere = ParolaSifirlaPenceresi(uygulama_ayari, eczaci, hedef)
    pencere.parola_alani.setText(GECICI)
    pencere.parola_tekrar_alani.setText(GECICI)

    pencere.kaydet_dugmesi.click()

    assert pencere.result() == QDialog.DialogCode.Accepted
    assert _giris(uygulama_baglanti, "personel1", GECICI).parola_degismeli


# --- Parola degistirme penceresi ---


def _degistirme_doldur(
    pencere: ParolaDegistirPenceresi, mevcut: str = PAROLA, tekrar: str = YENI
) -> None:
    pencere.mevcut_parola_alani.setText(mevcut)
    pencere.yeni_parola_alani.setText(YENI)
    pencere.yeni_parola_tekrar_alani.setText(tekrar)


def test_parola_degistirme_penceresi_yeni_parolayi_kaydeder(
    uygulama_baglanti: Baglanti, uygulama_ayari: VeritabaniAyari, personel: Kullanici
) -> None:
    pencere = ParolaDegistirPenceresi(uygulama_ayari, personel)
    _degistirme_doldur(pencere)

    pencere.kaydet_dugmesi.click()

    assert pencere.result() == QDialog.DialogCode.Accepted
    assert giris_dogrula(uygulama_baglanti, "personel1", YENI) is not None


def test_mevcut_parola_yanlissa_uyari_gosterilir(
    uygulama_ayari: VeritabaniAyari, personel: Kullanici
) -> None:
    pencere = ParolaDegistirPenceresi(uygulama_ayari, personel)
    _degistirme_doldur(pencere, mevcut="yanlis-parola")

    pencere.kaydet_dugmesi.click()

    assert pencere.result() != QDialog.DialogCode.Accepted
    assert "Mevcut parola" in pencere.hata_etiketi.text()
    assert pencere.mevcut_parola_alani.text() == ""


def test_yeni_parolalar_uyusmazsa_uyari_gosterilir(
    uygulama_baglanti: Baglanti, uygulama_ayari: VeritabaniAyari, personel: Kullanici
) -> None:
    pencere = ParolaDegistirPenceresi(uygulama_ayari, personel)
    _degistirme_doldur(pencere, tekrar="Baska-Parola1")

    pencere.kaydet_dugmesi.click()

    assert pencere.hata_etiketi.text() == "Parolalar aynı değil."
    assert giris_dogrula(uygulama_baglanti, "personel1", PAROLA) is not None


def test_zorunlu_degistirmede_aciklama_gosterilir(
    uygulama_ayari: VeritabaniAyari, personel: Kullanici
) -> None:
    zorunlu = ParolaDegistirPenceresi(uygulama_ayari, personel, zorunlu=True)
    normal = ParolaDegistirPenceresi(uygulama_ayari, personel)

    assert "kendi parolanızı" in zorunlu.aciklama_etiketi.text()
    assert normal.aciklama_etiketi.text() == ""


# --- Kullanicilar ekrani ---


def test_liste_kullanicilari_ve_durumlarini_gosterir(
    uygulama_ayari: VeritabaniAyari, eczaci: Kullanici, personel: Kullanici
) -> None:
    pencere = KullanicilarPenceresi(uygulama_ayari, eczaci)

    assert pencere.tablo.rowCount() == 2
    metinler: list[str] = []
    for satir in range(pencere.tablo.rowCount()):
        for sutun in range(pencere.tablo.columnCount()):
            hucre = pencere.tablo.item(satir, sutun)
            assert hucre is not None
            metinler.append(hucre.text())
    assert "Birinci Personel" in metinler
    assert "Personel" in metinler
    assert "Eczacı" in metinler
    assert "Aktif" in metinler


def test_kilitli_kullanici_listede_kilitli_gorunur(
    uygulama_baglanti: Baglanti,
    uygulama_ayari: VeritabaniAyari,
    eczaci: Kullanici,
    personel: Kullanici,
) -> None:
    for _ in range(AZAMI_HATALI_GIRIS - 1):
        giris_dogrula(uygulama_baglanti, personel.kullanici_adi, "yanlis-parola")
    with pytest.raises(HesapKilitliHatasi):
        giris_dogrula(uygulama_baglanti, personel.kullanici_adi, "yanlis-parola")

    pencere = KullanicilarPenceresi(uygulama_ayari, eczaci)
    _satiri_sec(pencere, "personel1")
    satir = pencere.tablo.currentRow()
    durum = pencere.tablo.item(satir, 3)
    assert durum is not None
    assert durum.text() == "Kilitli"


def test_secim_yokken_islem_uyari_verir(
    uygulama_ayari: VeritabaniAyari, eczaci: Kullanici
) -> None:
    pencere = KullanicilarPenceresi(uygulama_ayari, eczaci)
    pencere.tablo.clearSelection()
    pencere.tablo.setCurrentCell(-1, -1)

    pencere.kilit_ac_dugmesi.click()

    assert "seçin" in pencere.hata_etiketi.text()


def test_kilit_ac_dugmesi_kilidi_kaldirir_ve_liste_yenilenir(
    uygulama_baglanti: Baglanti,
    uygulama_ayari: VeritabaniAyari,
    eczaci: Kullanici,
    personel: Kullanici,
) -> None:
    for _ in range(AZAMI_HATALI_GIRIS - 1):
        giris_dogrula(uygulama_baglanti, personel.kullanici_adi, "yanlis-parola")
    with pytest.raises(HesapKilitliHatasi):
        giris_dogrula(uygulama_baglanti, personel.kullanici_adi, "yanlis-parola")
    pencere = KullanicilarPenceresi(uygulama_ayari, eczaci)
    _satiri_sec(pencere, "personel1")

    pencere.kilit_ac_dugmesi.click()

    assert giris_dogrula(uygulama_baglanti, personel.kullanici_adi, PAROLA) is not None
    _satiri_sec(pencere, "personel1")
    durum = pencere.tablo.item(pencere.tablo.currentRow(), 3)
    assert durum is not None
    assert durum.text() == "Aktif"


def test_pasif_yapma_onay_ister_ve_onaylanmazsa_yapmaz(
    uygulama_baglanti: Baglanti,
    uygulama_ayari: VeritabaniAyari,
    eczaci: Kullanici,
    personel: Kullanici,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sorular = _onayla(monkeypatch, QMessageBox.StandardButton.No)
    pencere = KullanicilarPenceresi(uygulama_ayari, eczaci)
    _satiri_sec(pencere, "personel1")

    pencere.pasif_aktif_dugmesi.click()

    assert len(sorular) == 1
    assert "Birinci Personel" in sorular[0]
    assert giris_dogrula(uygulama_baglanti, personel.kullanici_adi, PAROLA) is not None


def test_pasif_yapma_onaylaninca_yapilir_ve_geri_alinabilir(
    uygulama_baglanti: Baglanti,
    uygulama_ayari: VeritabaniAyari,
    eczaci: Kullanici,
    personel: Kullanici,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _onayla(monkeypatch, QMessageBox.StandardButton.Yes)
    pencere = KullanicilarPenceresi(uygulama_ayari, eczaci)
    _satiri_sec(pencere, "personel1")

    pencere.pasif_aktif_dugmesi.click()
    assert giris_dogrula(uygulama_baglanti, personel.kullanici_adi, PAROLA) is None

    _satiri_sec(pencere, "personel1")
    assert pencere.pasif_aktif_dugmesi.text() == "Aktif Yap"
    pencere.pasif_aktif_dugmesi.click()
    assert giris_dogrula(uygulama_baglanti, personel.kullanici_adi, PAROLA) is not None


def test_son_eczaci_pasif_yapilmak_istenirse_turkce_uyari_gosterilir(
    uygulama_baglanti: Baglanti,
    uygulama_ayari: VeritabaniAyari,
    eczaci: Kullanici,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _onayla(monkeypatch, QMessageBox.StandardButton.Yes)
    pencere = KullanicilarPenceresi(uygulama_ayari, eczaci)
    _satiri_sec(pencere, "eczaci1")

    pencere.pasif_aktif_dugmesi.click()

    assert "Son aktif eczacı" in pencere.hata_etiketi.text()
    assert giris_dogrula(uygulama_baglanti, "eczaci1", PAROLA) is not None


def test_yeni_kullanici_dugmesi_ekleme_penceresini_acar_ve_listeyi_yeniler(
    uygulama_ayari: VeritabaniAyari,
    eczaci: Kullanici,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _doldur_kaydet(ekleme: KullaniciEklePenceresi) -> int:
        _ekleme_doldur(ekleme)
        ekleme.kaydet_dugmesi.click()
        return ekleme.result()

    monkeypatch.setattr(KullaniciEklePenceresi, "exec", _doldur_kaydet)
    pencere = KullanicilarPenceresi(uygulama_ayari, eczaci)
    assert pencere.tablo.rowCount() == 1

    pencere.yeni_dugmesi.click()

    assert pencere.tablo.rowCount() == 2


def test_sifirla_dugmesi_secili_kullanici_icin_pencere_acar(
    uygulama_ayari: VeritabaniAyari,
    eczaci: Kullanici,
    personel: Kullanici,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    acilanlar: list[str] = []

    def _kaydet(sifirlama: ParolaSifirlaPenceresi) -> int:
        acilanlar.append(sifirlama.hedef.kullanici_adi)
        return QDialog.DialogCode.Rejected.value

    monkeypatch.setattr(ParolaSifirlaPenceresi, "exec", _kaydet)
    pencere = KullanicilarPenceresi(uygulama_ayari, eczaci)
    _satiri_sec(pencere, personel.kullanici_adi)

    pencere.sifirla_dugmesi.click()

    assert acilanlar == ["personel1"]


def test_liste_baglanti_yoksa_program_dusmez(
    uygulama_ayari: VeritabaniAyari, eczaci: Kullanici
) -> None:
    pencere = KullanicilarPenceresi(replace(uygulama_ayari, port=1), eczaci)
    assert pencere.tablo.rowCount() == 0
    assert "tekrar deneyin" in pencere.hata_etiketi.text()
