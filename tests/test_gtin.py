import pytest

from moduller.hatalar import GorunurHata
from moduller.ilac.gtin import gtin_normalle


@pytest.mark.parametrize(
    ("metin", "beklenen"),
    [
        ("08691234567890", "08691234567890"),  # karekod kilavuzundaki ornek
        ("8691234567890", "08691234567890"),  # 13 haneli barkod
        ("08699788698084", "08699788698084"),  # referans kilavuzundaki ornek
        ("08699788699050", "08699788699050"),
        (" 08691234567890 ", "08691234567890"),
        ("036000291452", "00036000291452"),  # 12 haneli
        ("96385074", "00000096385074"),  # 8 haneli
    ],
)
def test_gecerli_barkod_14_haneye_tamamlanir(metin: str, beklenen: str) -> None:
    assert gtin_normalle(metin) == beklenen


@pytest.mark.parametrize(
    "metin",
    [
        "",
        "123",
        "08691234567891",  # son hane yanlis
        "8691234567891",
        "0869123456789A",
        "086912345678901",  # 15 hane
        "0869 1234567890",
        "٠٨٦٩١٢٣٤٥٦٧٨٩٠٠٠",  # Arap rakamlari
    ],
)
def test_gecersiz_barkod_reddedilir(metin: str) -> None:
    with pytest.raises(GorunurHata, match="Barkod"):
        gtin_normalle(metin)
