from decimal import Decimal

import pytest

from moduller.hatalar import GorunurHata
from moduller.para import oran_coz, para_coz, para_metni, yuvarla


@pytest.mark.parametrize(
    ("metin", "beklenen"),
    [
        ("125,50", "125.50"),
        ("125.50", "125.50"),
        (" 125,5 ", "125.5"),
        ("125", "125"),
        ("1.234,50", "1234.50"),
        ("1.234.567,89", "1234567.89"),
        ("0,01", "0.01"),
        ("0", "0"),
    ],
)
def test_para_coz_gecerli_tutarlari_okur(metin: str, beklenen: str) -> None:
    sonuc = para_coz(metin, "PSF")
    assert isinstance(sonuc, Decimal)
    assert sonuc == Decimal(beklenen)


@pytest.mark.parametrize(
    "metin",
    [
        "",
        "   ",
        "abc",
        "-5",
        "12,345",  # uc ondalik: yuvarlanmaz, reddedilir
        "1.234",  # binlik mi ondalik mi belli degil: tahmin edilmez
        "1,234",
        "12.34.56",
        "1,234.50",
        "NaN",
        "Infinity",
        "1e5",
        "٣",  # Arap rakami
        "99999999999,00",  # veritabani sinirinin ustu
    ],
)
def test_para_coz_hatali_yaziyi_reddeder(metin: str) -> None:
    with pytest.raises(GorunurHata, match="PSF"):
        para_coz(metin, "PSF")


@pytest.mark.parametrize(
    ("metin", "beklenen"),
    [("10", "10"), ("1", "1"), ("0", "0"), ("20,00", "20.00"), ("8,5", "8.5"), ("100", "100")],
)
def test_oran_coz_gecerli_oranlari_okur(metin: str, beklenen: str) -> None:
    assert oran_coz(metin, "KDV") == Decimal(beklenen)


@pytest.mark.parametrize("metin", ["", "101", "-1", "abc", "10,123"])
def test_oran_coz_hatali_orani_reddeder(metin: str) -> None:
    with pytest.raises(GorunurHata, match="KDV"):
        oran_coz(metin, "KDV")


@pytest.mark.parametrize(
    ("tutar", "beklenen"),
    [
        ("125.5", "125,50"),
        ("1234.5", "1.234,50"),
        ("1234567.89", "1.234.567,89"),
        ("0", "0,00"),
        ("0.05", "0,05"),
    ],
)
def test_para_metni_turkce_bicimde_yazar(tutar: str, beklenen: str) -> None:
    assert para_metni(Decimal(tutar)) == beklenen


@pytest.mark.parametrize(
    ("tutar", "hane", "beklenen"),
    [
        ("0.125", 2, "0.13"),  # yarim ve ustu yukari (bankaci yuvarlamasi 0.12 verirdi)
        ("0.135", 2, "0.14"),
        ("0.124", 2, "0.12"),
        ("90.90909", 4, "90.9091"),
        ("0.03125", 4, "0.0313"),
        ("10", 2, "10.00"),
    ],
)
def test_yuvarla_yarim_ve_ustunu_yukari_yuvarlar(tutar: str, hane: int, beklenen: str) -> None:
    sonuc = yuvarla(Decimal(tutar), hane)
    assert sonuc == Decimal(beklenen)
    assert str(sonuc) == beklenen


def test_para_metni_ekranda_yarimi_yukari_yuvarlar() -> None:
    assert para_metni(Decimal("90.9091")) == "90,91"
    assert para_metni(Decimal("0.125")) == "0,13"


@pytest.mark.parametrize(("metin", "beklenen"), [("12,3456", "12.3456"), ("1.234,5678", "1234.5678")])
def test_para_coz_istenirse_dort_ondalik_okur(metin: str, beklenen: str) -> None:
    assert para_coz(metin, "Birim fiyat", ondalik=4) == Decimal(beklenen)


def test_para_coz_dort_ondalikta_da_besinci_haneyi_reddeder() -> None:
    with pytest.raises(GorunurHata, match="Birim fiyat"):
        para_coz("12,34567", "Birim fiyat", ondalik=4)


def test_para_metni_okunabilen_metin_uretir() -> None:
    assert para_coz(para_metni(Decimal("1234.50")), "PSF") == Decimal("1234.50")
