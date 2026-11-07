"""SKT okuma, parti numarasi kurali, net maliyet ve ay ekleme: veritabanisiz saf kurallar."""

from datetime import date
from decimal import Decimal

import pytest

from moduller.hatalar import GorunurHata
from moduller.stok.kurallar import ay_ekle, net_birim_maliyet, parti_no_duzenle, skt_coz

# --- SKT ---


@pytest.mark.parametrize(
    ("metin", "beklenen"),
    [
        ("31.01.2030", date(2030, 1, 31)),
        ("31/01/2030", date(2030, 1, 31)),
        ("1.2.2030", date(2030, 2, 1)),
        (" 15.06.2031 ", date(2031, 6, 15)),
        ("01.2030", date(2030, 1, 31)),  # yalnizca ay/yil: ayin son gunu
        ("1.2030", date(2030, 1, 31)),
        ("02/2028", date(2028, 2, 29)),  # artik yil
        ("02.2030", date(2030, 2, 28)),
        ("04.2030", date(2030, 4, 30)),
        ("12.2030", date(2030, 12, 31)),
        ("2030-01-31", date(2030, 1, 31)),
    ],
)
def test_skt_okunur(metin: str, beklenen: date) -> None:
    assert skt_coz(metin) == beklenen


@pytest.mark.parametrize(
    "metin",
    ["", "   ", "abc", "32.01.2030", "29.02.2030", "13.2030", "00.2030", "01.30", "31.01.30",
     "2030", "31-01-2030x", "٣١.٠١.٢٠٣٠"],
)
def test_hatali_skt_reddedilir(metin: str) -> None:
    with pytest.raises(GorunurHata, match="SKT"):
        skt_coz(metin)


# --- Parti numarasi ---


@pytest.mark.parametrize("parti", ["ABC123", "123456ABC", "A", "A" * 20, " AB12 "])
def test_karekodlu_ilacta_buyuk_harf_ve_rakam_kabul_edilir(parti: str) -> None:
    assert parti_no_duzenle(parti, karekodlu=True) == parti.strip()


@pytest.mark.parametrize("parti", ["abc123", "AB-12", "AB 12", "ABÇ12", "AB/12", "A" * 21, "AB.12"])
def test_karekodlu_ilacta_kurala_uymayan_parti_reddedilir(parti: str) -> None:
    with pytest.raises(GorunurHata, match="Parti"):
        parti_no_duzenle(parti, karekodlu=True)


@pytest.mark.parametrize("parti", ["abc-123", "Lot-7", "AB12", "x"])
def test_karekodsuz_urunde_kucuk_harf_ve_tire_kabul_edilir(parti: str) -> None:
    assert parti_no_duzenle(parti, karekodlu=False) == parti


@pytest.mark.parametrize("parti", ["ab ç", "AB 12", "AB/12", "şeker", "a" * 21])
def test_karekodsuz_urunde_de_bosluk_turkce_harf_ve_isaret_reddedilir(parti: str) -> None:
    with pytest.raises(GorunurHata, match="Parti"):
        parti_no_duzenle(parti, karekodlu=False)


@pytest.mark.parametrize("karekodlu", [True, False])
def test_bos_parti_bos_doner(karekodlu: bool) -> None:
    assert parti_no_duzenle("   ", karekodlu=karekodlu) is None


# --- Net maliyet ---


@pytest.mark.parametrize(
    ("toplam", "alinan", "mf", "beklenen"),
    [
        ("1000.00", 10, 1, "90.9091"),  # 10+1 mal fazlasi
        ("1000.00", 10, 0, "100.0000"),
        ("0.00", 0, 3, "0.0000"),  # yalnizca bedelsiz kutu
        ("1.00", 32, 0, "0.0313"),  # 0,03125: yarim ve ustu yukari
        ("1.00", 3, 0, "0.3333"),
    ],
)
def test_net_birim_maliyet_dort_haneye_yuvarlanir(
    toplam: str, alinan: int, mf: int, beklenen: str
) -> None:
    sonuc = net_birim_maliyet(Decimal(toplam), alinan, mf)
    assert sonuc == Decimal(beklenen)
    assert sonuc.as_tuple().exponent == -4


def test_kutu_yoksa_maliyet_hesaplanmaz() -> None:
    with pytest.raises(GorunurHata):
        net_birim_maliyet(Decimal("10"), 0, 0)


# --- Ay ekleme ---


@pytest.mark.parametrize(
    ("baslangic", "ay", "beklenen"),
    [
        (date(2026, 1, 15), 6, date(2026, 7, 15)),
        (date(2026, 8, 31), 6, date(2027, 2, 28)),
        (date(2027, 8, 31), 6, date(2028, 2, 29)),
        (date(2026, 11, 7), 84, date(2033, 11, 7)),
        (date(2026, 12, 31), 1, date(2027, 1, 31)),
    ],
)
def test_ay_ekle_ay_sonunu_dogru_hesaplar(baslangic: date, ay: int, beklenen: date) -> None:
    assert ay_ekle(baslangic, ay) == beklenen
