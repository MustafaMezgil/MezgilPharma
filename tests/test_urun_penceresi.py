"""Urunler listesi ve urun karti ekranlari."""

from dataclasses import replace
from decimal import Decimal

import pytest
from PyQt6.QtWidgets import QDialog, QMessageBox, QWidget

from arayuz import urun_penceresi
from arayuz.urun_penceresi import UrunKartiPenceresi, UrunlerPenceresi
from ayarlar import VeritabaniAyari
from moduller.ilac.servis import (
    ReceteTuru,
    UrunBilgisi,
    UrunFiyati,
    UrunTuru,
    urun_ara,
    urun_ekle,
    urun_getir,
)
from moduller.kullanici.servis import Kullanici, Rol, giris_dogrula, kullanici_olustur
from veritabani.baglanti import Baglanti

PAROLA = "Deneme-Parola1"
GTIN = "08691234567890"
FIYAT = UrunFiyati(Decimal("1234.50"), Decimal("99.90"), Decimal("10"))

pytestmark = pytest.mark.usefixtures("qt_uygulamasi")


def _giris(baglanti: Baglanti, kullanici_adi: str) -> Kullanici:
    kullanici = giris_dogrula(baglanti, kullanici_adi, PAROLA)
    assert kullanici is not None
    return kullanici


@pytest.fixture
def eczaci(uygulama_baglanti: Baglanti) -> Kullanici:
    kullanici_olustur(uygulama_baglanti, "eczaci1", "Test Eczacı", PAROLA, Rol.ECZACI)
    return _giris(uygulama_baglanti, "eczaci1")


@pytest.fixture
def personel(uygulama_baglanti: Baglanti, eczaci: Kullanici) -> Kullanici:
    kullanici_olustur(uygulama_baglanti, "personel1", "Test Personel", PAROLA, Rol.PERSONEL)
    return _giris(uygulama_baglanti, "personel1")


def _bilgi(ad: str = "Deneme İlaç") -> UrunBilgisi:
    return UrunBilgisi(
        ad=ad,
        gtin=GTIN,
        urun_turu=UrunTuru.ILAC,
        karekodlu=True,
        recete_turu=ReceteTuru.KIRMIZI,
        kritik_stok=4,
        raf_yeri="A-3",
        etken_madde="Denemeol",
        farmasotik_form="Tablet",
        atc_kodu="N02BE01",
        uretici_firma="Deneme Firma",
        soguk_zincir=True,
    )


def _formu_doldur(pencere: UrunKartiPenceresi) -> None:
    pencere.ad_alani.setText("Yeni İlaç")
    pencere.gtin_alani.setText("8691234567890")
    pencere.etken_madde_alani.setText("Denemeol")
    pencere.form_alani.setText("Şurup")
    pencere.atc_alani.setText("N02BE01")
    pencere.uretici_alani.setText("Deneme Firma")
    pencere.raf_alani.setText("B-1")
    pencere.kritik_stok_alani.setValue(6)
    pencere.soguk_zincir_kutusu.setChecked(True)
    pencere.recete_secimi.setCurrentIndex(pencere.recete_secimi.findData(ReceteTuru.YESIL))


def _fiyat_doldur(pencere: UrunKartiPenceresi) -> None:
    pencere.psf_alani.setText("1.234,50")
    pencere.kamu_alani.setText("99,90")
    pencere.kdv_alani.setText("10")


def _sutun_metni(pencere: UrunlerPenceresi, satir: int, sutun: int) -> str:
    hucre = pencere.tablo.item(satir, sutun)
    assert hucre is not None
    return hucre.text()


def _onayla(monkeypatch: pytest.MonkeyPatch, yanit: QMessageBox.StandardButton) -> list[str]:
    sorular: list[str] = []

    def _soru(_ust: QWidget | None, _baslik: str, metin: str) -> QMessageBox.StandardButton:
        sorular.append(metin)
        return yanit

    monkeypatch.setattr(QMessageBox, "question", _soru)
    return sorular


# --- Urun karti ---


def test_eczaci_form_ile_kart_ekler(
    uygulama_baglanti: Baglanti, uygulama_ayari: VeritabaniAyari, eczaci: Kullanici
) -> None:
    pencere = UrunKartiPenceresi(uygulama_ayari, eczaci)
    _formu_doldur(pencere)
    _fiyat_doldur(pencere)

    pencere.kaydet_dugmesi.click()

    assert pencere.result() == QDialog.DialogCode.Accepted
    urun = urun_ara(uygulama_baglanti, eczaci, "yeni")[0]
    assert urun.gtin == GTIN
    assert urun.recete_turu is ReceteTuru.YESIL
    assert urun.farmasotik_form == "Şurup"
    assert urun.kritik_stok == 6
    assert urun.soguk_zincir
    assert urun.psf == Decimal("1234.50")
    assert urun.kamu_fiyati == Decimal("99.90")
    assert urun.kdv_orani == Decimal("10")


def test_personelde_fiyat_alanlari_kapali_ve_fiyatsiz_kaydeder(
    uygulama_baglanti: Baglanti, uygulama_ayari: VeritabaniAyari, personel: Kullanici
) -> None:
    pencere = UrunKartiPenceresi(uygulama_ayari, personel)
    assert not pencere.psf_alani.isEnabled()
    assert not pencere.kamu_alani.isEnabled()
    assert not pencere.kdv_alani.isEnabled()
    _formu_doldur(pencere)

    pencere.kaydet_dugmesi.click()

    assert pencere.result() == QDialog.DialogCode.Accepted
    assert urun_ara(uygulama_baglanti, personel, "yeni")[0].psf is None


def test_eczacida_psf_bossa_turkce_uyari(
    uygulama_ayari: VeritabaniAyari, eczaci: Kullanici
) -> None:
    pencere = UrunKartiPenceresi(uygulama_ayari, eczaci)
    _formu_doldur(pencere)
    pencere.kdv_alani.setText("10")

    pencere.kaydet_dugmesi.click()

    assert pencere.result() != QDialog.DialogCode.Accepted
    assert "PSF" in pencere.hata_etiketi.text()


def test_hatali_tutarda_kayit_olmaz(
    uygulama_baglanti: Baglanti, uygulama_ayari: VeritabaniAyari, eczaci: Kullanici
) -> None:
    pencere = UrunKartiPenceresi(uygulama_ayari, eczaci)
    _formu_doldur(pencere)
    _fiyat_doldur(pencere)
    pencere.psf_alani.setText("12,345")

    pencere.kaydet_dugmesi.click()

    assert "PSF" in pencere.hata_etiketi.text()
    assert urun_ara(uygulama_baglanti, eczaci, "") == []


def test_kamu_fiyati_bos_birakilabilir(
    uygulama_baglanti: Baglanti, uygulama_ayari: VeritabaniAyari, eczaci: Kullanici
) -> None:
    pencere = UrunKartiPenceresi(uygulama_ayari, eczaci)
    _formu_doldur(pencere)
    _fiyat_doldur(pencere)
    pencere.kamu_alani.clear()

    pencere.kaydet_dugmesi.click()

    assert urun_ara(uygulama_baglanti, eczaci, "yeni")[0].kamu_fiyati is None


def test_diger_urun_secilince_recete_ve_karekod_kapanir(
    uygulama_ayari: VeritabaniAyari, eczaci: Kullanici
) -> None:
    pencere = UrunKartiPenceresi(uygulama_ayari, eczaci)
    pencere.recete_secimi.setCurrentIndex(pencere.recete_secimi.findData(ReceteTuru.KIRMIZI))

    pencere.tur_secimi.setCurrentIndex(pencere.tur_secimi.findData(UrunTuru.DIGER))

    assert pencere.recete_secimi.currentData() is ReceteTuru.RECETESIZ
    assert not pencere.recete_secimi.isEnabled()
    assert not pencere.karekodlu_kutusu.isChecked()

    pencere.tur_secimi.setCurrentIndex(pencere.tur_secimi.findData(UrunTuru.ILAC))
    assert pencere.recete_secimi.isEnabled()
    assert pencere.karekodlu_kutusu.isChecked()


def test_yeni_kart_varsayilan_olarak_karekodlu_ilactir(
    uygulama_ayari: VeritabaniAyari, eczaci: Kullanici
) -> None:
    pencere = UrunKartiPenceresi(uygulama_ayari, eczaci)
    assert pencere.tur_secimi.currentData() is UrunTuru.ILAC
    assert pencere.karekodlu_kutusu.isChecked()


def test_duzenlemede_alanlar_dolu_gelir_ve_kaydedilir(
    uygulama_baglanti: Baglanti, uygulama_ayari: VeritabaniAyari, eczaci: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    urun = urun_getir(uygulama_baglanti, eczaci, urun_id)

    pencere = UrunKartiPenceresi(uygulama_ayari, eczaci, urun)

    assert pencere.ad_alani.text() == "Deneme İlaç"
    assert pencere.gtin_alani.text() == GTIN
    assert pencere.recete_secimi.currentData() is ReceteTuru.KIRMIZI
    assert pencere.kritik_stok_alani.value() == 4
    assert pencere.soguk_zincir_kutusu.isChecked()
    assert pencere.psf_alani.text() == "1.234,50"
    assert pencere.kamu_alani.text() == "99,90"
    assert pencere.kdv_alani.text() == "10,00"

    pencere.psf_alani.setText("1.000,00")
    pencere.kaydet_dugmesi.click()

    assert pencere.result() == QDialog.DialogCode.Accepted
    assert urun_getir(uygulama_baglanti, eczaci, urun_id).psf == Decimal("1000.00")


def test_personel_duzenlemede_fiyati_bozmaz(
    uygulama_baglanti: Baglanti,
    uygulama_ayari: VeritabaniAyari,
    eczaci: Kullanici,
    personel: Kullanici,
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    urun = urun_getir(uygulama_baglanti, personel, urun_id)

    pencere = UrunKartiPenceresi(uygulama_ayari, personel, urun)
    pencere.ad_alani.setText("Düzeltilmiş Ad")
    pencere.kaydet_dugmesi.click()

    assert pencere.result() == QDialog.DialogCode.Accepted
    guncel = urun_getir(uygulama_baglanti, eczaci, urun_id)
    assert guncel.ad == "Düzeltilmiş Ad"
    assert guncel.psf == FIYAT.psf


@pytest.mark.yavas
def test_baglanti_yoksa_kart_ekranı_turkce_uyari_verir(
    uygulama_ayari: VeritabaniAyari, eczaci: Kullanici
) -> None:
    pencere = UrunKartiPenceresi(replace(uygulama_ayari, port=1), eczaci)
    _formu_doldur(pencere)
    _fiyat_doldur(pencere)

    pencere.kaydet_dugmesi.click()

    assert pencere.result() != QDialog.DialogCode.Accepted
    assert "tekrar deneyin" in pencere.hata_etiketi.text()


# --- Urunler listesi ---


def test_liste_urunu_turkce_bicimlerle_gosterir(
    uygulama_baglanti: Baglanti, uygulama_ayari: VeritabaniAyari, eczaci: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    uygulama_baglanti.execute(
        "INSERT INTO stok_partileri (urun_id, parti_no, skt, miktar, alis_fiyati) "
        "VALUES (%s, 'P1', '2030-01-31', 5, 80)",
        (urun_id,),
    )

    pencere = UrunlerPenceresi(uygulama_ayari, eczaci)

    assert pencere.tablo.rowCount() == 1
    assert _sutun_metni(pencere, 0, 0) == "Deneme İlaç"
    assert _sutun_metni(pencere, 0, 1) == GTIN
    assert _sutun_metni(pencere, 0, 2) == "5"
    assert _sutun_metni(pencere, 0, 3) == "31.01.2030"
    assert _sutun_metni(pencere, 0, 4) == "1.234,50"
    assert _sutun_metni(pencere, 0, 5) == "Aktif"


def test_fiyatsiz_ve_stoksuz_urun_listede_acikca_gorunur(
    uygulama_baglanti: Baglanti, uygulama_ayari: VeritabaniAyari, personel: Kullanici
) -> None:
    urun_ekle(uygulama_baglanti, personel, _bilgi(), None)

    pencere = UrunlerPenceresi(uygulama_ayari, personel)

    assert _sutun_metni(pencere, 0, 2) == "0"
    assert _sutun_metni(pencere, 0, 3) == "-"
    assert _sutun_metni(pencere, 0, 4) == "Fiyat girilmedi"


def test_arama_dugmesi_listeyi_suzer(
    uygulama_baglanti: Baglanti, uygulama_ayari: VeritabaniAyari, eczaci: Kullanici
) -> None:
    urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    pencere = UrunlerPenceresi(uygulama_ayari, eczaci)
    assert pencere.tablo.rowCount() == 1

    pencere.arama_alani.setText("olmayan")
    pencere.ara_dugmesi.click()
    assert pencere.tablo.rowCount() == 0

    pencere.arama_alani.setText("ILAC")
    pencere.ara_dugmesi.click()
    assert pencere.tablo.rowCount() == 1


def test_pasifleri_goster_kutusu_pasifleri_listeler(
    uygulama_baglanti: Baglanti,
    uygulama_ayari: VeritabaniAyari,
    eczaci: Kullanici,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _onayla(monkeypatch, QMessageBox.StandardButton.Yes)
    urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    pencere = UrunlerPenceresi(uygulama_ayari, eczaci)
    pencere.tablo.selectRow(0)
    pencere.pasif_aktif_dugmesi.click()
    assert pencere.tablo.rowCount() == 0

    pencere.pasifleri_goster.setChecked(True)

    assert pencere.tablo.rowCount() == 1
    assert _sutun_metni(pencere, 0, 5) == "Pasif"
    pencere.tablo.selectRow(0)
    assert pencere.pasif_aktif_dugmesi.text() == "Aktif Yap"
    pencere.pasif_aktif_dugmesi.click()
    assert _sutun_metni(pencere, 0, 5) == "Aktif"


def test_pasif_yapma_onay_ister_stok_miktarini_soyler_reddedilirse_yapmaz(
    uygulama_baglanti: Baglanti,
    uygulama_ayari: VeritabaniAyari,
    eczaci: Kullanici,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sorular = _onayla(monkeypatch, QMessageBox.StandardButton.No)
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    uygulama_baglanti.execute(
        "INSERT INTO stok_partileri (urun_id, parti_no, skt, miktar, alis_fiyati) "
        "VALUES (%s, 'P1', '2030-01-31', 5, 80)",
        (urun_id,),
    )
    pencere = UrunlerPenceresi(uygulama_ayari, eczaci)
    pencere.tablo.selectRow(0)

    pencere.pasif_aktif_dugmesi.click()

    assert len(sorular) == 1
    assert "Deneme İlaç" in sorular[0]
    assert "5" in sorular[0]
    assert urun_getir(uygulama_baglanti, eczaci, urun_id).aktif


def test_personelde_pasif_dugmesi_yoktur(
    uygulama_ayari: VeritabaniAyari, personel: Kullanici
) -> None:
    pencere = UrunlerPenceresi(uygulama_ayari, personel)
    assert pencere.pasif_aktif_dugmesi.isHidden()
    assert pencere.pasifleri_goster.isHidden()


def test_secim_yokken_duzenle_uyari_verir(
    uygulama_ayari: VeritabaniAyari, eczaci: Kullanici
) -> None:
    pencere = UrunlerPenceresi(uygulama_ayari, eczaci)
    pencere.duzenle_dugmesi.click()
    assert "seçin" in pencere.hata_etiketi.text()


def test_yeni_dugmesi_karti_acar_ve_listeyi_yeniler(
    uygulama_ayari: VeritabaniAyari,
    eczaci: Kullanici,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _kaydet(kart: UrunKartiPenceresi) -> int:
        _formu_doldur(kart)
        _fiyat_doldur(kart)
        kart.kaydet_dugmesi.click()
        return kart.result()

    monkeypatch.setattr(UrunKartiPenceresi, "exec", _kaydet)
    pencere = UrunlerPenceresi(uygulama_ayari, eczaci)
    assert pencere.tablo.rowCount() == 0

    pencere.yeni_dugmesi.click()

    assert pencere.tablo.rowCount() == 1


def test_duzenle_dugmesi_secili_karti_acar(
    uygulama_baglanti: Baglanti,
    uygulama_ayari: VeritabaniAyari,
    eczaci: Kullanici,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    acilan: list[str] = []

    def _kaydet(kart: UrunKartiPenceresi) -> int:
        acilan.append(kart.ad_alani.text())
        return QDialog.DialogCode.Rejected.value

    monkeypatch.setattr(UrunKartiPenceresi, "exec", _kaydet)
    pencere = UrunlerPenceresi(uygulama_ayari, eczaci)
    pencere.tablo.selectRow(0)

    pencere.duzenle_dugmesi.click()

    assert acilan == ["Deneme İlaç"]


def test_sonuc_siniri_asilinca_kullanici_uyarilir(
    uygulama_baglanti: Baglanti,
    uygulama_ayari: VeritabaniAyari,
    eczaci: Kullanici,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    monkeypatch.setattr(urun_penceresi, "ARAMA_SINIRI", 1)

    pencere = UrunlerPenceresi(uygulama_ayari, eczaci)

    assert "daraltın" in pencere.hata_etiketi.text()


@pytest.mark.yavas
def test_liste_baglanti_yoksa_program_dusmez(
    uygulama_ayari: VeritabaniAyari, eczaci: Kullanici
) -> None:
    pencere = UrunlerPenceresi(replace(uygulama_ayari, port=1), eczaci)
    assert pencere.tablo.rowCount() == 0
    assert "tekrar deneyin" in pencere.hata_etiketi.text()
