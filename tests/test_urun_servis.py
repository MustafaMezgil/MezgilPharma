"""Urun karti: ekleme, duzenleme, fiyat gecmisi, arama ve rol kisitlari."""

from datetime import date
from decimal import Decimal

import psycopg
import pytest

from moduller.hatalar import GorunurHata
from moduller.ilac.servis import (
    Urun,
    UrunBilgisi,
    UrunFiyati,
    UrunTuru,
    ReceteTuru,
    arama_metni,
    urun_aktif_yap,
    urun_ara,
    urun_ekle,
    urun_getir,
    urun_guncelle,
    urun_pasif_yap,
)
from moduller.kullanici.servis import (
    Kullanici,
    Rol,
    YetkiHatasi,
    giris_dogrula,
    kullanici_olustur,
    pasif_yap,
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


def _bilgi(
    ad: str = "Deneme İlaç 500 mg Tablet",
    gtin: str | None = GTIN,
    urun_turu: UrunTuru = UrunTuru.ILAC,
    karekodlu: bool = True,
    recete_turu: ReceteTuru = ReceteTuru.NORMAL,
    kritik_stok: int = 0,
    etken_madde: str | None = "Denemeol",
    atc_kodu: str | None = "N02BE01",
) -> UrunBilgisi:
    return UrunBilgisi(
        ad=ad,
        gtin=gtin,
        urun_turu=urun_turu,
        karekodlu=karekodlu,
        recete_turu=recete_turu,
        kritik_stok=kritik_stok,
        raf_yeri="A-3",
        etken_madde=etken_madde,
        farmasotik_form="Tablet",
        atc_kodu=atc_kodu,
        uretici_firma="Deneme Firma",
        soguk_zincir=False,
    )


def _diger_bilgi(ad: str = "Deneme Krem") -> UrunBilgisi:
    return _bilgi(
        ad=ad,
        gtin=None,
        urun_turu=UrunTuru.DIGER,
        karekodlu=False,
        recete_turu=ReceteTuru.RECETESIZ,
        etken_madde=None,
        atc_kodu=None,
    )


def _parti_ekle(baglanti: Baglanti, urun_id: int, miktar: int, skt: str = "2030-01-31") -> None:
    baglanti.execute(
        "INSERT INTO stok_partileri (urun_id, parti_no, skt, miktar, birim_maliyet) "
        "VALUES (%s, %s, %s, %s, %s)",
        (urun_id, f"P{skt}{miktar}", skt, miktar, Decimal("80.00")),
    )


def _gecmis(baglanti: Baglanti, urun_id: int) -> list[dict[str, object]]:
    return [
        dict(satir)
        for satir in baglanti.execute(
            "SELECT eski_psf, yeni_psf, eski_kamu_fiyati, yeni_kamu_fiyati, stok_miktari, "
            "kullanici_id, tarih FROM fiyat_gecmisi WHERE urun_id = %s ORDER BY id",
            (urun_id,),
        ).fetchall()
    ]


# --- Ekleme ---


def test_eczaci_tum_bilgileriyle_kart_ekler(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(kritik_stok=3), FIYAT)

    urun = urun_getir(uygulama_baglanti, eczaci, urun_id)
    assert urun.ad == "Deneme İlaç 500 mg Tablet"
    assert urun.gtin == GTIN
    assert urun.urun_turu is UrunTuru.ILAC
    assert urun.karekodlu
    assert urun.recete_turu is ReceteTuru.NORMAL
    assert urun.kritik_stok == 3
    assert urun.etken_madde == "Denemeol"
    assert urun.atc_kodu == "N02BE01"
    assert urun.psf == Decimal("125.50")
    assert urun.kamu_fiyati == Decimal("99.90")
    assert urun.kdv_orani == Decimal("10")
    assert urun.aktif


def test_barkod_14_haneye_tamamlanarak_saklanir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(gtin="8691234567890"), FIYAT)
    assert urun_getir(uygulama_baglanti, eczaci, urun_id).gtin == GTIN


def test_ayni_barkod_iki_kartta_olamaz(uygulama_baglanti: Baglanti, eczaci: Kullanici) -> None:
    urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    with pytest.raises(GorunurHata, match="barkod"):
        urun_ekle(uygulama_baglanti, eczaci, _bilgi(ad="Başka"), FIYAT)


def test_barkodsuz_iki_urun_olabilir(uygulama_baglanti: Baglanti, eczaci: Kullanici) -> None:
    urun_ekle(uygulama_baglanti, eczaci, _diger_bilgi("Krem A"), FIYAT)
    urun_ekle(uygulama_baglanti, eczaci, _diger_bilgi("Krem B"), FIYAT)
    assert len(urun_ara(uygulama_baglanti, eczaci, "krem")) == 2


def test_karekodlu_urunde_barkod_zorunludur(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    with pytest.raises(GorunurHata, match="Karekodlu"):
        urun_ekle(uygulama_baglanti, eczaci, _bilgi(gtin=None), FIYAT)


def test_gecersiz_barkod_reddedilir(uygulama_baglanti: Baglanti, eczaci: Kullanici) -> None:
    with pytest.raises(GorunurHata, match="Barkod"):
        urun_ekle(uygulama_baglanti, eczaci, _bilgi(gtin="08691234567891"), FIYAT)


def test_ad_bos_olamaz(uygulama_baglanti: Baglanti, eczaci: Kullanici) -> None:
    with pytest.raises(GorunurHata, match="Ürün adı"):
        urun_ekle(uygulama_baglanti, eczaci, _bilgi(ad="   "), FIYAT)


def test_diger_urunde_recete_turu_secilemez(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    bilgi = _bilgi(
        gtin=None, urun_turu=UrunTuru.DIGER, karekodlu=False, recete_turu=ReceteTuru.KIRMIZI
    )
    with pytest.raises(GorunurHata, match="Reçete"):
        urun_ekle(uygulama_baglanti, eczaci, bilgi, FIYAT)


def test_kritik_stok_eksi_olamaz(uygulama_baglanti: Baglanti, eczaci: Kullanici) -> None:
    with pytest.raises(GorunurHata, match="Kritik stok"):
        urun_ekle(uygulama_baglanti, eczaci, _bilgi(kritik_stok=-1), FIYAT)


@pytest.mark.parametrize("atc", ["N02BE01X", "N02 BE", "N02-BE"])
def test_gecersiz_atc_reddedilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, atc: str
) -> None:
    with pytest.raises(GorunurHata, match="ATC"):
        urun_ekle(uygulama_baglanti, eczaci, _bilgi(atc_kodu=atc), FIYAT)


def test_atc_buyuk_harfe_cevrilir(uygulama_baglanti: Baglanti, eczaci: Kullanici) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(atc_kodu=" n02be01 "), FIYAT)
    assert urun_getir(uygulama_baglanti, eczaci, urun_id).atc_kodu == "N02BE01"


def test_bos_metin_alanlari_bos_kaydedilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(etken_madde="   "), FIYAT)
    assert urun_getir(uygulama_baglanti, eczaci, urun_id).etken_madde is None


# --- Fiyat kurallari ---


@pytest.mark.parametrize(
    "fiyat",
    [
        UrunFiyati(Decimal("0"), None, Decimal("10")),
        UrunFiyati(Decimal("-1"), None, Decimal("10")),
        UrunFiyati(Decimal("10.123"), None, Decimal("10")),
        UrunFiyati(Decimal("NaN"), None, Decimal("10")),
        UrunFiyati(Decimal("10"), Decimal("-1"), Decimal("10")),
        UrunFiyati(Decimal("10"), Decimal("1.234"), Decimal("10")),
        UrunFiyati(Decimal("10"), None, Decimal("101")),
        UrunFiyati(Decimal("10"), None, Decimal("-1")),
    ],
)
def test_gecersiz_fiyat_yuvarlanmaz_reddedilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, fiyat: UrunFiyati
) -> None:
    with pytest.raises(GorunurHata):
        urun_ekle(uygulama_baglanti, eczaci, _bilgi(), fiyat)
    assert urun_ara(uygulama_baglanti, eczaci, "") == []


def test_eczaci_fiyatsiz_kart_acamaz(uygulama_baglanti: Baglanti, eczaci: Kullanici) -> None:
    with pytest.raises(GorunurHata, match="PSF"):
        urun_ekle(uygulama_baglanti, eczaci, _bilgi(), None)


def test_kamu_fiyati_bos_olabilir(uygulama_baglanti: Baglanti, eczaci: Kullanici) -> None:
    fiyat = UrunFiyati(Decimal("50"), None, Decimal("20"))
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _diger_bilgi(), fiyat)
    assert urun_getir(uygulama_baglanti, eczaci, urun_id).kamu_fiyati is None


def test_fiyat_sutunlari_para_turundedir(uygulama_baglanti: Baglanti) -> None:
    satirlar = uygulama_baglanti.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name IN ('urunler', 'fiyat_gecmisi', 'stok_partileri', 'stok_hareketleri') "
        "AND (column_name LIKE '%%psf%%' OR column_name LIKE '%%fiyat%%' "
        "OR column_name LIKE '%%kdv%%' OR column_name LIKE '%%maliyet%%' "
        "OR column_name LIKE '%%tutar%%')"
    ).fetchall()
    assert len(satirlar) >= 9
    assert {satir["data_type"] for satir in satirlar} == {"numeric"}


# --- Fiyat gecmisi ---


def test_ilk_fiyat_gecmise_yazilir(uygulama_baglanti: Baglanti, eczaci: Kullanici) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)

    gecmis = _gecmis(uygulama_baglanti, urun_id)
    assert len(gecmis) == 1
    assert gecmis[0]["eski_psf"] is None
    assert gecmis[0]["yeni_psf"] == Decimal("125.50")
    assert gecmis[0]["stok_miktari"] == 0
    assert gecmis[0]["kullanici_id"] == eczaci.id


def test_fiyat_degisince_o_anki_stok_toplami_yazilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    _parti_ekle(uygulama_baglanti, urun_id, 7, "2030-01-31")
    _parti_ekle(uygulama_baglanti, urun_id, 5, "2031-06-30")
    yeni = UrunFiyati(Decimal("110.00"), Decimal("88.00"), Decimal("10"))

    urun_guncelle(uygulama_baglanti, eczaci, urun_id, _bilgi(), yeni)

    son = _gecmis(uygulama_baglanti, urun_id)[-1]
    assert son["eski_psf"] == Decimal("125.50")
    assert son["yeni_psf"] == Decimal("110.00")
    assert son["eski_kamu_fiyati"] == Decimal("99.90")
    assert son["yeni_kamu_fiyati"] == Decimal("88.00")
    assert son["stok_miktari"] == 12
    assert son["kullanici_id"] == eczaci.id
    assert son["tarih"] is not None


def test_baska_urunun_stogu_gecmise_karismaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    baska_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(ad="Başka", gtin=GTIN_2), FIYAT)
    _parti_ekle(uygulama_baglanti, baska_id, 9)

    urun_guncelle(
        uygulama_baglanti,
        eczaci,
        urun_id,
        _bilgi(),
        UrunFiyati(Decimal("1"), None, Decimal("10")),
    )

    assert _gecmis(uygulama_baglanti, urun_id)[-1]["stok_miktari"] == 0


def test_yalniz_kamu_fiyati_degisince_de_gecmise_yazilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    yeni = UrunFiyati(FIYAT.psf, Decimal("70.00"), FIYAT.kdv_orani)

    urun_guncelle(uygulama_baglanti, eczaci, urun_id, _bilgi(), yeni)

    assert len(_gecmis(uygulama_baglanti, urun_id)) == 2


def test_fiyat_ayni_kalirsa_gecmise_yazilmaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    ayni = UrunFiyati(Decimal("125.5"), Decimal("99.9"), Decimal("10.00"))

    urun_guncelle(uygulama_baglanti, eczaci, urun_id, _bilgi(ad="Yeni Ad"), ayni)

    assert len(_gecmis(uygulama_baglanti, urun_id)) == 1
    assert urun_getir(uygulama_baglanti, eczaci, urun_id).ad == "Yeni Ad"


def test_yalniz_kdv_degisince_gecmise_yazilmaz_ama_kaydedilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    yeni = UrunFiyati(FIYAT.psf, FIYAT.kamu_fiyati, Decimal("20"))

    urun_guncelle(uygulama_baglanti, eczaci, urun_id, _bilgi(), yeni)

    assert len(_gecmis(uygulama_baglanti, urun_id)) == 1
    assert urun_getir(uygulama_baglanti, eczaci, urun_id).kdv_orani == Decimal("20")


# --- Roller ---


def test_personel_fiyatsiz_kart_acabilir_ve_gecmise_yazilmaz(
    uygulama_baglanti: Baglanti, personel: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, personel, _bilgi(), None)

    urun = urun_getir(uygulama_baglanti, personel, urun_id)
    assert urun.psf is None
    assert urun.kamu_fiyati is None
    assert urun.kdv_orani is None
    assert _gecmis(uygulama_baglanti, urun_id) == []


def test_personel_fiyatli_kart_acamaz(uygulama_baglanti: Baglanti, personel: Kullanici) -> None:
    with pytest.raises(YetkiHatasi):
        urun_ekle(uygulama_baglanti, personel, _bilgi(), FIYAT)
    assert urun_ara(uygulama_baglanti, personel, "") == []


def test_personel_fiyat_disindaki_bilgileri_duzenler(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)

    urun_guncelle(uygulama_baglanti, personel, urun_id, _bilgi(ad="Personel Düzeltti"), None)

    urun = urun_getir(uygulama_baglanti, personel, urun_id)
    assert urun.ad == "Personel Düzeltti"
    assert urun.psf == FIYAT.psf


def test_personel_fiyat_degistiremez_diger_bilgiler_de_kaydolmaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    yeni = UrunFiyati(Decimal("1"), None, Decimal("1"))

    with pytest.raises(YetkiHatasi):
        urun_guncelle(uygulama_baglanti, personel, urun_id, _bilgi(ad="Değişti"), yeni)

    urun = urun_getir(uygulama_baglanti, eczaci, urun_id)
    assert urun.psf == FIYAT.psf
    assert urun.ad != "Değişti"


def test_eczaci_personelin_actigi_karta_fiyat_girer(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, personel, _bilgi(), None)
    _parti_ekle(uygulama_baglanti, urun_id, 4)

    urun_guncelle(uygulama_baglanti, eczaci, urun_id, _bilgi(), FIYAT)

    gecmis = _gecmis(uygulama_baglanti, urun_id)
    assert len(gecmis) == 1
    assert gecmis[0]["eski_psf"] is None
    assert gecmis[0]["stok_miktari"] == 4


def test_personel_kart_pasif_yapamaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    with pytest.raises(YetkiHatasi):
        urun_pasif_yap(uygulama_baglanti, personel, urun_id)
    assert urun_getir(uygulama_baglanti, eczaci, urun_id).aktif


def test_yetki_nesneden_degil_veritabanindan_okunur(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    sahte = Kullanici(personel.id, personel.kullanici_adi, personel.ad_soyad, Rol.ECZACI)
    with pytest.raises(YetkiHatasi):
        urun_ekle(uygulama_baglanti, sahte, _bilgi(), FIYAT)


def test_pasif_yapilan_kullanici_hicbir_kart_islemi_yapamaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    pasif_yap(uygulama_baglanti, eczaci, personel.id)

    with pytest.raises(YetkiHatasi):
        urun_ara(uygulama_baglanti, personel, "")
    with pytest.raises(YetkiHatasi):
        urun_getir(uygulama_baglanti, personel, urun_id)
    with pytest.raises(YetkiHatasi):
        urun_ekle(uygulama_baglanti, personel, _bilgi(ad="X", gtin=GTIN_2), None)
    with pytest.raises(YetkiHatasi):
        urun_guncelle(uygulama_baglanti, personel, urun_id, _bilgi(), None)


# --- Pasif / aktif ---


def test_pasif_kart_aramada_cikmaz_kayit_silinmez_geri_alinir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)

    urun_pasif_yap(uygulama_baglanti, eczaci, urun_id)

    assert urun_ara(uygulama_baglanti, eczaci, "deneme") == []
    pasifler = urun_ara(uygulama_baglanti, eczaci, "deneme", pasifler_dahil=True)
    assert [u.id for u in pasifler] == [urun_id]
    assert not pasifler[0].aktif

    urun_aktif_yap(uygulama_baglanti, eczaci, urun_id)
    assert len(urun_ara(uygulama_baglanti, eczaci, "deneme")) == 1


def test_olmayan_kart_icin_turkce_hata(uygulama_baglanti: Baglanti, eczaci: Kullanici) -> None:
    with pytest.raises(GorunurHata, match="bulunamadı"):
        urun_getir(uygulama_baglanti, eczaci, 999999)
    with pytest.raises(GorunurHata, match="bulunamadı"):
        urun_guncelle(uygulama_baglanti, eczaci, 999999, _bilgi(), None)
    with pytest.raises(GorunurHata, match="bulunamadı"):
        urun_pasif_yap(uygulama_baglanti, eczaci, 999999)


# --- Arama ---


@pytest.mark.parametrize(
    ("metin", "beklenen"),
    [
        ("İLAÇ", "ilac"),
        ("ilaç", "ilac"),
        ("ILAC", "ilac"),
        ("ıspanak", "ispanak"),
        ("ŞĞÇÖÜ şğçöü", "sgcou sgcou"),
    ],
)
def test_arama_metni_turkce_harfleri_esitler(metin: str, beklenen: str) -> None:
    assert arama_metni(metin) == beklenen


@pytest.mark.parametrize(
    "aranan",
    [
        "deneme",
        "DENEME",
        "ilaç",
        "İLAÇ",
        "ILAC",
        "ilac",
        "500 tablet",  # sira ve araliksiz kelimeler
        "tablet deneme",
        "denemeol",  # etken madde
        "n02be",  # ATC
        "deneme firma",  # uretici
        GTIN,
        "8691234567890",  # 13 haneli barkod okuyucu
    ],
)
def test_arama_ad_etken_madde_atc_ve_barkodla_bulur(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, aranan: str
) -> None:
    urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    assert len(urun_ara(uygulama_baglanti, eczaci, aranan)) == 1


def test_duzenlenince_arama_guncellenir(uygulama_baglanti: Baglanti, eczaci: Kullanici) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)

    urun_guncelle(uygulama_baglanti, eczaci, urun_id, _bilgi(ad="Şurup Yeni"), None)

    assert urun_ara(uygulama_baglanti, eczaci, "surup")
    assert not urun_ara(uygulama_baglanti, eczaci, "500")


@pytest.mark.parametrize("aranan", ["%", "_", "\\", "ad%s", "'; DROP TABLE urunler; --"])
def test_aramada_ozel_karakterler_joker_sayilmaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, aranan: str
) -> None:
    urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    assert urun_ara(uygulama_baglanti, eczaci, aranan) == []


def test_arama_sonucu_ada_gore_sirali_ve_sinirlidir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    for ad in ("Cc", "Aa", "Bb"):
        urun_ekle(uygulama_baglanti, eczaci, _diger_bilgi(ad), FIYAT)

    assert [u.ad for u in urun_ara(uygulama_baglanti, eczaci, "")] == ["Aa", "Bb", "Cc"]
    assert len(urun_ara(uygulama_baglanti, eczaci, "", limit=2)) == 2


def test_arama_stok_toplami_ve_en_yakin_skt_getirir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    _parti_ekle(uygulama_baglanti, urun_id, 3, "2031-06-30")
    _parti_ekle(uygulama_baglanti, urun_id, 2, "2030-01-31")
    _parti_ekle(uygulama_baglanti, urun_id, 0, "2029-01-31")  # biten parti sayilmaz

    urun: Urun = urun_ara(uygulama_baglanti, eczaci, "deneme")[0]

    assert urun.stok_miktari == 5
    assert urun.en_yakin_skt == date(2030, 1, 31)


def test_stoksuz_urunde_miktar_sifir_skt_bostur(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    urun = urun_ara(uygulama_baglanti, eczaci, "deneme")[0]
    assert urun.stok_miktari == 0
    assert urun.en_yakin_skt is None


# --- Veritabani korumalari ---


def test_veritabani_gecersiz_gtin_kabul_etmez(uygulama_baglanti: Baglanti) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        uygulama_baglanti.execute(
            "INSERT INTO urunler (ad, arama_metni, gtin, urun_turu, recete_turu) "
            "VALUES ('x', 'x', '123', 'ilac', 'normal')"
        )


def test_parti_miktari_eksiye_dusemez(uygulama_baglanti: Baglanti, eczaci: Kullanici) -> None:
    urun_id = urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)
    with pytest.raises(psycopg.errors.CheckViolation):
        _parti_ekle(uygulama_baglanti, urun_id, -1)
