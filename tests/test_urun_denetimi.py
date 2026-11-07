"""Kart yetkileri, eczaci onayi ve kart degisikliklerinin erisim_log'a yazilmasi."""

from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest

from moduller.hatalar import GorunurHata
from moduller.ilac.servis import (
    ReceteTuru,
    UrunBilgisi,
    UrunFiyati,
    UrunTuru,
    urun_aktif_yap,
    urun_ara,
    urun_ekle,
    urun_getir,
    urun_guncelle,
    urun_onayla,
    urun_pasif_yap,
)
from moduller.kullanici.servis import (
    Kullanici,
    Rol,
    YetkiHatasi,
    giris_dogrula,
    kullanici_olustur,
)
from veritabani.baglanti import Baglanti

PAROLA = "Deneme-Parola1"
GTIN = "08691234567890"
GTIN_2 = "08699788698084"
FIYAT = UrunFiyati(psf=Decimal("125.50"), kamu_fiyati=Decimal("99.90"), kdv_orani=Decimal("10"))


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


def _bilgi(**degisen: Any) -> UrunBilgisi:
    temel = UrunBilgisi(
        ad="Deneme İlaç",
        gtin=GTIN,
        urun_turu=UrunTuru.ILAC,
        karekodlu=True,
        recete_turu=ReceteTuru.KIRMIZI,
        kritik_stok=2,
        raf_yeri="A-3",
        etken_madde="Denemeol",
        farmasotik_form="Tablet",
        atc_kodu="N02BE01",
        uretici_firma="Deneme Firma",
        soguk_zincir=False,
    )
    return replace(temel, **degisen)


def _kayitlar(baglanti: Baglanti) -> list[dict[str, Any]]:
    return [
        dict(satir)
        for satir in baglanti.execute(
            "SELECT kullanici_id, islem, kayit_turu, kayit_id, ayrinti "
            "FROM erisim_log WHERE kayit_turu = 'urun' ORDER BY id"
        ).fetchall()
    ]


# --- Eczaci onayi ---


def test_personelin_actigi_kart_onay_bekler_eczacininki_beklemez(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    personel_karti = urun_ekle(uygulama_baglanti, personel, _bilgi(), None)
    eczaci_karti = urun_ekle(uygulama_baglanti, eczaci, _bilgi(gtin=GTIN_2), FIYAT)

    assert urun_getir(uygulama_baglanti, eczaci, personel_karti).onay_bekliyor
    assert not urun_getir(uygulama_baglanti, eczaci, eczaci_karti).onay_bekliyor


def test_eczaci_onaylayinca_bekleme_kalkar_ve_kayit_yazilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, personel, _bilgi(), None)

    urun_onayla(uygulama_baglanti, eczaci, urun_id)

    assert not urun_getir(uygulama_baglanti, eczaci, urun_id).onay_bekliyor
    son = _kayitlar(uygulama_baglanti)[-1]
    assert (son["kullanici_id"], son["islem"], son["kayit_id"]) == (
        eczaci.id,
        "urun_onaylama",
        urun_id,
    )


def test_personel_onaylayamaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, personel, _bilgi(), None)
    with pytest.raises(YetkiHatasi):
        urun_onayla(uygulama_baglanti, personel, urun_id)
    assert urun_getir(uygulama_baglanti, eczaci, urun_id).onay_bekliyor


def test_onay_beklemeyen_kart_onaylanamaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    with pytest.raises(GorunurHata, match="onay"):
        urun_onayla(uygulama_baglanti, eczaci, urun_id)


def test_eczacinin_duzenlemesi_onayi_kendiliginden_vermez(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, personel, _bilgi(), None)
    urun_guncelle(uygulama_baglanti, eczaci, urun_id, _bilgi(ad="Düzeltildi"), FIYAT)
    assert urun_getir(uygulama_baglanti, eczaci, urun_id).onay_bekliyor


def test_aramada_yalnizca_onay_bekleyenler_suzulur(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    bekleyen = urun_ekle(uygulama_baglanti, personel, _bilgi(), None)
    urun_ekle(uygulama_baglanti, eczaci, _bilgi(gtin=GTIN_2), FIYAT)

    sonuc = urun_ara(uygulama_baglanti, eczaci, "", yalnizca_onay_bekleyen=True)

    assert [u.id for u in sonuc] == [bekleyen]
    assert len(urun_ara(uygulama_baglanti, eczaci, "")) == 2


# --- Kritik alanlarda yetki ---

_KRITIK_DEGISIKLIKLER: list[dict[str, Any]] = [
    {"recete_turu": ReceteTuru.RECETESIZ},
    {"gtin": GTIN_2},
    {"karekodlu": False},
    {"urun_turu": UrunTuru.DIGER, "recete_turu": ReceteTuru.RECETESIZ, "karekodlu": False},
]


def test_personel_yeni_kartta_kritik_alanlari_doldurabilir(
    uygulama_baglanti: Baglanti, personel: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, personel, _bilgi(), None)
    urun = urun_getir(uygulama_baglanti, personel, urun_id)
    assert urun.recete_turu is ReceteTuru.KIRMIZI
    assert urun.gtin == GTIN
    assert urun.karekodlu


@pytest.mark.parametrize("degisiklik", _KRITIK_DEGISIKLIKLER)
def test_personel_kritik_alanlari_sonradan_degistiremez(
    uygulama_baglanti: Baglanti,
    eczaci: Kullanici,
    personel: Kullanici,
    degisiklik: dict[str, Any],
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    once = urun_getir(uygulama_baglanti, eczaci, urun_id)
    kayit_sayisi = len(_kayitlar(uygulama_baglanti))

    with pytest.raises(YetkiHatasi, match="yalnızca eczacı"):
        urun_guncelle(
            uygulama_baglanti, personel, urun_id, _bilgi(ad="Değişti", **degisiklik), None
        )

    sonra = urun_getir(uygulama_baglanti, eczaci, urun_id)
    assert sonra.bilgi == once.bilgi
    assert len(_kayitlar(uygulama_baglanti)) == kayit_sayisi


@pytest.mark.parametrize(
    ("baslangic", "hedef"),
    [(UrunTuru.ILAC, UrunTuru.DIGER), (UrunTuru.DIGER, UrunTuru.ILAC)],
)
def test_personel_yalnizca_urun_turunu_de_degistiremez(
    uygulama_baglanti: Baglanti,
    eczaci: Kullanici,
    personel: Kullanici,
    baslangic: UrunTuru,
    hedef: UrunTuru,
) -> None:
    # Recetesiz ve karekodsuz kartta yalnizca urun turu degisir; baska alan onu ele vermez.
    sade = {"gtin": None, "karekodlu": False, "recete_turu": ReceteTuru.RECETESIZ}
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(urun_turu=baslangic, **sade), FIYAT)

    with pytest.raises(YetkiHatasi):
        urun_guncelle(
            uygulama_baglanti, personel, urun_id, _bilgi(urun_turu=hedef, **sade), None
        )

    assert urun_getir(uygulama_baglanti, eczaci, urun_id).urun_turu is baslangic


def test_personel_kendi_actigi_kartta_da_kritik_alani_degistiremez(
    uygulama_baglanti: Baglanti, personel: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, personel, _bilgi(), None)
    with pytest.raises(YetkiHatasi):
        urun_guncelle(
            uygulama_baglanti,
            personel,
            urun_id,
            _bilgi(recete_turu=ReceteTuru.RECETESIZ),
            None,
        )


def test_personel_barkodu_ayni_numaranin_13_haneli_haliyle_kaydedebilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    urun_guncelle(
        uygulama_baglanti, personel, urun_id, _bilgi(gtin="8691234567890", ad="Yeni Ad"), None
    )
    assert urun_getir(uygulama_baglanti, eczaci, urun_id).ad == "Yeni Ad"


def test_personel_kritik_olmayan_alanlari_degistirir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)

    urun_guncelle(
        uygulama_baglanti,
        personel,
        urun_id,
        _bilgi(ad="Yeni Ad", raf_yeri="B-1", soguk_zincir=True, kritik_stok=9),
        None,
    )

    urun = urun_getir(uygulama_baglanti, eczaci, urun_id)
    assert (urun.ad, urun.bilgi.raf_yeri, urun.soguk_zincir, urun.kritik_stok) == (
        "Yeni Ad",
        "B-1",
        True,
        9,
    )


@pytest.mark.parametrize("degisiklik", _KRITIK_DEGISIKLIKLER)
def test_eczaci_kritik_alanlari_degistirebilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, degisiklik: dict[str, Any]
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    urun_guncelle(uygulama_baglanti, eczaci, urun_id, _bilgi(**degisiklik), None)
    assert urun_getir(uygulama_baglanti, eczaci, urun_id).bilgi == _bilgi(**degisiklik)


# --- Erisim kaydi ---


def test_kart_ekleme_kaydedilir(uygulama_baglanti: Baglanti, personel: Kullanici) -> None:
    urun_id = urun_ekle(uygulama_baglanti, personel, _bilgi(), None)
    assert [(k["kullanici_id"], k["islem"], k["kayit_turu"], k["kayit_id"])
            for k in _kayitlar(uygulama_baglanti)] == [
        (personel.id, "urun_ekleme", "urun", urun_id)
    ]


def test_kritik_alanlarin_eski_ve_yeni_degeri_kaydedilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    yeni_fiyat = UrunFiyati(FIYAT.psf, FIYAT.kamu_fiyati, Decimal("20"))

    urun_guncelle(
        uygulama_baglanti,
        eczaci,
        urun_id,
        _bilgi(
            recete_turu=ReceteTuru.YESIL,
            gtin=GTIN_2,
            karekodlu=False,
            soguk_zincir=True,
        ),
        yeni_fiyat,
    )

    son = _kayitlar(uygulama_baglanti)[-1]
    assert (son["kullanici_id"], son["islem"], son["kayit_id"]) == (
        eczaci.id,
        "urun_guncelleme",
        urun_id,
    )
    assert son["ayrinti"]["kritik"] == {
        "recete_turu": {"eski": "kirmizi", "yeni": "yesil"},
        "gtin": {"eski": GTIN, "yeni": GTIN_2},
        "karekodlu": {"eski": True, "yeni": False},
        "soguk_zincir": {"eski": False, "yeni": True},
        "kdv_orani": {"eski": "10.00", "yeni": "20.00"},
    }


def test_kritik_olmayan_alanlarin_yalnizca_adi_kaydedilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)

    urun_guncelle(
        uygulama_baglanti, personel, urun_id, _bilgi(ad="Gizli Ad", raf_yeri="Z-9"), None
    )

    son = _kayitlar(uygulama_baglanti)[-1]
    assert son["kullanici_id"] == personel.id
    assert sorted(son["ayrinti"]["degisen"]) == ["ad", "raf_yeri"]
    assert son["ayrinti"]["kritik"] == {}
    assert "Gizli Ad" not in str(son["ayrinti"])


def test_fiyat_degisikligi_adiyla_kaydedilir_degeri_fiyat_gecmisinde_kalir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)

    urun_guncelle(
        uygulama_baglanti,
        eczaci,
        urun_id,
        _bilgi(),
        UrunFiyati(Decimal("99.00"), Decimal("80.00"), FIYAT.kdv_orani),
    )

    son = _kayitlar(uygulama_baglanti)[-1]
    assert sorted(son["ayrinti"]["degisen"]) == ["kamu_fiyati", "psf"]
    assert son["ayrinti"]["kritik"] == {}


def test_hicbir_sey_degismezse_kayit_yazilmaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    ayni_fiyat = UrunFiyati(Decimal("125.5"), Decimal("99.9"), Decimal("10.0"))

    urun_guncelle(uygulama_baglanti, eczaci, urun_id, _bilgi(gtin="8691234567890"), ayni_fiyat)

    assert [k["islem"] for k in _kayitlar(uygulama_baglanti)] == ["urun_ekleme"]


def test_pasif_ve_aktif_yapma_kaydedilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)

    urun_pasif_yap(uygulama_baglanti, eczaci, urun_id)
    urun_aktif_yap(uygulama_baglanti, eczaci, urun_id)

    assert [k["islem"] for k in _kayitlar(uygulama_baglanti)] == [
        "urun_ekleme",
        "urun_pasif_yapma",
        "urun_aktif_yapma",
    ]


def test_basarisiz_islem_kayit_birakmaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    with pytest.raises(GorunurHata):
        urun_ekle(uygulama_baglanti, eczaci, _bilgi(ad="Kopya"), FIYAT)  # ayni barkod
    assert len(_kayitlar(uygulama_baglanti)) == 1


def test_kullanici_islemlerinin_kaydi_bozulmaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    satir = uygulama_baglanti.execute(
        "SELECT kayit_turu, ayrinti FROM erisim_log WHERE kayit_turu = 'kullanici'"
    ).fetchall()
    assert satir == []
