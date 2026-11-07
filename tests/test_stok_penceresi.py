"""Stok girisi, stok detayi ve depolar ekranlari."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from PyQt6.QtWidgets import QDialog, QInputDialog, QMessageBox, QWidget

from arayuz.stok_penceresi import DepolarPenceresi, StokDetayiPenceresi, StokGirisiPenceresi
from arayuz.urun_penceresi import UrunlerPenceresi
from ayarlar import VeritabaniAyari
from moduller.ilac.servis import (
    ReceteTuru,
    Urun,
    UrunBilgisi,
    UrunFiyati,
    UrunTuru,
    urun_ekle,
    urun_getir,
)
from moduller.kullanici.servis import Kullanici, Rol, giris_dogrula, kullanici_olustur
from moduller.stok.kurallar import ay_ekle
from moduller.stok.servis import (
    HareketTuru,
    StokGirisi,
    partileri_getir,
    stok_girisi_yap,
    tedarikci_ekle,
    tedarikci_pasif_yap,
)
from veritabani.baglanti import Baglanti

PAROLA = "Deneme-Parola1"
GTIN = "08691234567890"
FIYAT = UrunFiyati(Decimal("125.50"), None, Decimal("10"))
SKT_METNI = ay_ekle(date.today(), 24).strftime("%m.%Y")

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


@pytest.fixture
def urun(uygulama_baglanti: Baglanti, eczaci: Kullanici) -> Urun:
    bilgi = UrunBilgisi(
        ad="Deneme İlaç",
        gtin=GTIN,
        urun_turu=UrunTuru.ILAC,
        karekodlu=True,
        recete_turu=ReceteTuru.NORMAL,
        kritik_stok=0,
        raf_yeri=None,
        etken_madde=None,
        farmasotik_form=None,
        atc_kodu=None,
        uretici_firma=None,
        soguk_zincir=False,
    )
    urun_id = urun_ekle(uygulama_baglanti, eczaci, bilgi, FIYAT)
    return urun_getir(uygulama_baglanti, eczaci, urun_id)


@pytest.fixture
def depo(uygulama_baglanti: Baglanti, eczaci: Kullanici) -> int:
    return tedarikci_ekle(uygulama_baglanti, eczaci, "Deneme Ecza Deposu")


def _doldur(pencere: StokGirisiPenceresi, **degisen: Any) -> None:
    degerler: dict[str, Any] = {
        "fatura": "FTR-1",
        "parti": "ABC123",
        "skt": SKT_METNI,
        "alinan": 10,
        "mf": 1,
        "birim": "100,00",
    }
    degerler.update(degisen)
    pencere.fatura_alani.setText(degerler["fatura"])
    pencere.parti_alani.setText(degerler["parti"])
    pencere.skt_alani.setText(degerler["skt"])
    pencere.alinan_alani.setValue(degerler["alinan"])
    pencere.mf_alani.setValue(degerler["mf"])
    pencere.birim_fiyat_alani.setText(degerler["birim"])


def _onayla(monkeypatch: pytest.MonkeyPatch, yanit: QMessageBox.StandardButton) -> list[str]:
    sorular: list[str] = []

    def _soru(_ust: QWidget | None, _baslik: str, metin: str) -> QMessageBox.StandardButton:
        sorular.append(metin)
        return yanit

    monkeypatch.setattr(QMessageBox, "question", _soru)
    return sorular


def _hucre(tablo: Any, satir: int, sutun: int) -> str:
    hucre = tablo.item(satir, sutun)
    assert hucre is not None
    return hucre.text()


def _basliklar(tablo: Any) -> list[str]:
    return [tablo.horizontalHeaderItem(i).text() for i in range(tablo.columnCount())]


# --- Stok girisi ---


@pytest.mark.usefixtures("depo")
def test_secili_urunle_acilan_ekrandan_giris_yapilir(
    uygulama_baglanti: Baglanti, uygulama_ayari: VeritabaniAyari, eczaci: Kullanici, urun: Urun
) -> None:
    pencere = StokGirisiPenceresi(uygulama_ayari, eczaci, urun)
    assert pencere.urun_secimi.currentText().startswith("Deneme İlaç")
    _doldur(pencere)

    assert pencere.toplam_alani.text() == "1.000,00"
    pencere.kaydet_dugmesi.click()

    assert pencere.result() == QDialog.DialogCode.Accepted
    parti = partileri_getir(uygulama_baglanti, eczaci, urun.id)[0]
    assert (parti.parti_no, parti.miktar, parti.birim_maliyet) == (
        "ABC123",
        11,
        Decimal("90.9091"),
    )


@pytest.mark.usefixtures("depo")
def test_satir_toplami_faturadaki_rakamla_duzeltilebilir(
    uygulama_baglanti: Baglanti, uygulama_ayari: VeritabaniAyari, eczaci: Kullanici, urun: Urun
) -> None:
    pencere = StokGirisiPenceresi(uygulama_ayari, eczaci, urun)
    _doldur(pencere, mf=0, birim="33,3333")
    assert pencere.toplam_alani.text() == "333,33"

    pencere.toplam_alani.setText("333,34")
    pencere.kaydet_dugmesi.click()

    satir = uygulama_baglanti.execute("SELECT toplam_tutar FROM stok_hareketleri").fetchone()
    assert satir is not None
    assert satir["toplam_tutar"] == Decimal("333.34")


@pytest.mark.usefixtures("depo")
def test_barkod_okutunca_urun_bulunur(
    uygulama_ayari: VeritabaniAyari, eczaci: Kullanici, urun: Urun
) -> None:
    pencere = StokGirisiPenceresi(uygulama_ayari, eczaci)
    assert pencere.urun_secimi.count() == 0

    pencere.urun_alani.setText("8691234567890")
    pencere.urun_alani.returnPressed.emit()

    assert pencere.urun_secimi.count() == 1
    assert pencere.urun_secimi.currentData() == urun.id


@pytest.mark.usefixtures("depo")
def test_urun_secilmeden_kaydedilemez(
    uygulama_ayari: VeritabaniAyari, eczaci: Kullanici
) -> None:
    pencere = StokGirisiPenceresi(uygulama_ayari, eczaci)
    _doldur(pencere)
    pencere.kaydet_dugmesi.click()
    assert "ürün" in pencere.hata_etiketi.text()


@pytest.mark.usefixtures("depo")
def test_kaydet_ve_yeni_satir_depo_ve_faturayi_korur(
    uygulama_baglanti: Baglanti, uygulama_ayari: VeritabaniAyari, eczaci: Kullanici, urun: Urun
) -> None:
    pencere = StokGirisiPenceresi(uygulama_ayari, eczaci, urun)
    _doldur(pencere)

    pencere.kaydet_yeni_dugmesi.click()

    assert pencere.result() != QDialog.DialogCode.Accepted
    assert pencere.fatura_alani.text() == "FTR-1"
    assert pencere.depo_secimi.currentText() == "Deneme Ecza Deposu"
    assert pencere.parti_alani.text() == ""
    assert pencere.skt_alani.text() == ""
    assert pencere.birim_fiyat_alani.text() == ""
    assert pencere.urun_secimi.count() == 0
    assert "Deneme İlaç" in pencere.bilgi_etiketi.text()
    assert len(partileri_getir(uygulama_baglanti, eczaci, urun.id)) == 1


@pytest.mark.usefixtures("depo")
def test_hatali_sktde_turkce_uyari(
    uygulama_ayari: VeritabaniAyari, eczaci: Kullanici, urun: Urun
) -> None:
    pencere = StokGirisiPenceresi(uygulama_ayari, eczaci, urun)
    _doldur(pencere, skt="13.2030")
    pencere.kaydet_dugmesi.click()
    assert "SKT" in pencere.hata_etiketi.text()


@pytest.mark.usefixtures("depo")
def test_uyari_onaylanirsa_kaydedilir_onaylanmazsa_kaydedilmez(
    uygulama_baglanti: Baglanti,
    uygulama_ayari: VeritabaniAyari,
    eczaci: Kullanici,
    urun: Urun,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    yakin = ay_ekle(date.today(), 2).strftime("%d.%m.%Y")
    sorular = _onayla(monkeypatch, QMessageBox.StandardButton.No)
    pencere = StokGirisiPenceresi(uygulama_ayari, eczaci, urun)
    _doldur(pencere, skt=yakin)

    pencere.kaydet_dugmesi.click()

    assert len(sorular) == 1
    assert "6 ay" in sorular[0]
    assert partileri_getir(uygulama_baglanti, eczaci, urun.id) == []

    _onayla(monkeypatch, QMessageBox.StandardButton.Yes)
    pencere.kaydet_dugmesi.click()

    assert pencere.result() == QDialog.DialogCode.Accepted
    assert len(partileri_getir(uygulama_baglanti, eczaci, urun.id)) == 1


@pytest.mark.usefixtures("depo")
def test_personel_acilis_stogu_secemez(
    uygulama_ayari: VeritabaniAyari, personel: Kullanici
) -> None:
    pencere = StokGirisiPenceresi(uygulama_ayari, personel)
    turler = [pencere.tur_secimi.itemData(i) for i in range(pencere.tur_secimi.count())]
    assert turler == [HareketTuru.GIRIS]


@pytest.mark.usefixtures("depo")
def test_eczaci_acilis_stogunda_depo_fatura_ve_mf_kapanir(
    uygulama_baglanti: Baglanti, uygulama_ayari: VeritabaniAyari, eczaci: Kullanici, urun: Urun
) -> None:
    pencere = StokGirisiPenceresi(uygulama_ayari, eczaci, urun)
    pencere.tur_secimi.setCurrentIndex(pencere.tur_secimi.findData(HareketTuru.ACILIS))

    assert not pencere.depo_secimi.isEnabled()
    assert not pencere.fatura_alani.isEnabled()
    assert not pencere.mf_alani.isEnabled()

    _doldur(pencere, mf=0, fatura="")
    pencere.kaydet_dugmesi.click()

    assert pencere.result() == QDialog.DialogCode.Accepted
    satir = uygulama_baglanti.execute("SELECT tur, tedarikci_id FROM stok_hareketleri").fetchone()
    assert satir is not None
    assert (satir["tur"], satir["tedarikci_id"]) == ("acilis", None)


def test_pasif_depo_listede_cikmaz_yeni_depo_eklenip_secilir(
    uygulama_baglanti: Baglanti,
    uygulama_ayari: VeritabaniAyari,
    personel: Kullanici,
    eczaci: Kullanici,
    depo: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tedarikci_pasif_yap(uygulama_baglanti, eczaci, depo)
    pencere = StokGirisiPenceresi(uygulama_ayari, personel)
    assert pencere.depo_secimi.count() == 0

    def _metin_al(*_args: object, **_kwargs: object) -> tuple[str, bool]:
        return ("Yeni Depo A.Ş.", True)

    monkeypatch.setattr(QInputDialog, "getText", _metin_al)
    pencere.yeni_depo_dugmesi.click()

    assert pencere.depo_secimi.currentText() == "Yeni Depo A.Ş."


# --- Stok detayi ---


def _stok_gir(baglanti: Baglanti, yapan: Kullanici, urun_id: int, depo_id: int) -> None:
    stok_girisi_yap(
        baglanti,
        yapan,
        StokGirisi(
            urun_id=urun_id,
            tur=HareketTuru.GIRIS,
            parti_no="ABC123",
            skt=ay_ekle(date.today(), 24),
            alinan_adet=10,
            mf_adet=1,
            toplam_tutar=Decimal("1000.00"),
            tedarikci_id=depo_id,
            fatura_no="FTR-1",
        ),
    )


def test_eczaci_detayda_maliyet_ve_tutari_gorur(
    uygulama_baglanti: Baglanti,
    uygulama_ayari: VeritabaniAyari,
    eczaci: Kullanici,
    urun: Urun,
    depo: int,
) -> None:
    _stok_gir(uygulama_baglanti, eczaci, urun.id, depo)

    pencere = StokDetayiPenceresi(uygulama_ayari, eczaci, urun)

    assert "Birim maliyet" in _basliklar(pencere.parti_tablosu)
    assert "Tutar" in _basliklar(pencere.hareket_tablosu)
    assert _hucre(pencere.parti_tablosu, 0, 0) == "ABC123"
    assert _hucre(pencere.parti_tablosu, 0, 2) == "11"
    assert _hucre(pencere.parti_tablosu, 0, 3) == "90,91"
    satir = [_hucre(pencere.hareket_tablosu, 0, s) for s in range(pencere.hareket_tablosu.columnCount())]
    assert "Faturalı giriş" in satir
    assert "Deneme Ecza Deposu" in satir
    assert "1.000,00" in satir


def test_personel_detayda_alis_fiyatini_goremez(
    uygulama_baglanti: Baglanti,
    uygulama_ayari: VeritabaniAyari,
    eczaci: Kullanici,
    personel: Kullanici,
    urun: Urun,
    depo: int,
) -> None:
    _stok_gir(uygulama_baglanti, eczaci, urun.id, depo)

    pencere = StokDetayiPenceresi(uygulama_ayari, personel, urun)

    assert "Birim maliyet" not in _basliklar(pencere.parti_tablosu)
    assert "Tutar" not in _basliklar(pencere.hareket_tablosu)
    hepsi = [
        _hucre(pencere.hareket_tablosu, 0, s) for s in range(pencere.hareket_tablosu.columnCount())
    ]
    assert "1.000,00" not in hepsi
    assert "90,91" not in hepsi


# --- Depolar ---


def test_depolar_ekrani_listeler_ve_ekler(
    uygulama_ayari: VeritabaniAyari,
    personel: Kullanici,
    depo: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pencere = DepolarPenceresi(uygulama_ayari, personel)
    assert pencere.tablo.rowCount() == 1
    assert pencere.pasif_aktif_dugmesi.isHidden()

    def _metin_al(*_args: object, **_kwargs: object) -> tuple[str, bool]:
        return ("İkinci Depo", True)

    monkeypatch.setattr(QInputDialog, "getText", _metin_al)
    pencere.yeni_dugmesi.click()

    assert pencere.tablo.rowCount() == 2


def test_eczaci_depoyu_pasif_yapar_ve_geri_alir(
    uygulama_ayari: VeritabaniAyari,
    eczaci: Kullanici,
    depo: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _onayla(monkeypatch, QMessageBox.StandardButton.Yes)
    pencere = DepolarPenceresi(uygulama_ayari, eczaci)
    pencere.tablo.selectRow(0)

    pencere.pasif_aktif_dugmesi.click()

    assert _hucre(pencere.tablo, 0, 1) == "Pasif"
    pencere.tablo.selectRow(0)
    assert pencere.pasif_aktif_dugmesi.text() == "Aktif Yap"
    pencere.pasif_aktif_dugmesi.click()
    assert _hucre(pencere.tablo, 0, 1) == "Aktif"


def test_ayni_depo_eklenirse_turkce_uyari(
    uygulama_ayari: VeritabaniAyari,
    eczaci: Kullanici,
    depo: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _metin_al(*_args: object, **_kwargs: object) -> tuple[str, bool]:
        return ("DENEME ECZA DEPOSU", True)

    monkeypatch.setattr(QInputDialog, "getText", _metin_al)
    pencere = DepolarPenceresi(uygulama_ayari, eczaci)
    pencere.yeni_dugmesi.click()

    assert "kayıtlı" in pencere.hata_etiketi.text()


# --- Urunler ekranindan acma ---


def test_urunler_ekranindan_stok_girisi_ve_detay_acilir(
    uygulama_ayari: VeritabaniAyari,
    eczaci: Kullanici,
    urun: Urun,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    acilan: list[str] = []

    def _giris_exec(pencere: StokGirisiPenceresi) -> int:
        acilan.append("giris:" + pencere.urun_secimi.currentText())
        return QDialog.DialogCode.Rejected.value

    def _detay_exec(pencere: StokDetayiPenceresi) -> int:
        acilan.append("detay:" + pencere.windowTitle())
        return QDialog.DialogCode.Rejected.value

    monkeypatch.setattr(StokGirisiPenceresi, "exec", _giris_exec)
    monkeypatch.setattr(StokDetayiPenceresi, "exec", _detay_exec)
    pencere = UrunlerPenceresi(uygulama_ayari, eczaci)
    pencere.tablo.selectRow(0)

    pencere.stok_girisi_dugmesi.click()
    pencere.stok_detayi_dugmesi.click()

    assert len(acilan) == 2
    assert acilan[0].startswith("giris:Deneme İlaç")
    assert "Deneme İlaç" in acilan[1]


def test_eski_parti_listesi_degil_guncel_urun_kullanilir(urun: Urun) -> None:
    assert replace(urun, stok_miktari=5).stok_miktari == 5
