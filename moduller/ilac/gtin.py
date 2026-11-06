"""Barkodu 14 haneli GTIN bicimine getirir ve kontrol hanesini denetler."""

import re

from moduller.hatalar import GorunurHata

_GTIN_UZUNLUGU = 14
_BARKOD = re.compile(r"[0-9]{8}|[0-9]{12,14}")


def _kontrol_hanesi_dogru_mu(gtin: str) -> bool:
    """GS1 kurali: sagdan basa dogru rakamlar sirayla 3 ve 1 ile carpilir."""
    toplam = sum(
        int(rakam) * (3 if sira % 2 == 0 else 1)
        for sira, rakam in enumerate(reversed(gtin[:-1]))
    )
    return (10 - toplam % 10) % 10 == int(gtin[-1])


def gtin_normalle(metin: str) -> str:
    """Gecerli barkodu basina sifir ekleyerek 14 haneye tamamlar, degilse hata verir."""
    temiz = metin.strip()
    if not _BARKOD.fullmatch(temiz):
        raise GorunurHata("Barkod 8, 12, 13 veya 14 haneli olmalı ve yalnızca rakam içermelidir.")
    gtin = temiz.zfill(_GTIN_UZUNLUGU)
    if not _kontrol_hanesi_dogru_mu(gtin):
        raise GorunurHata("Barkod hatalı: son hane tutmuyor. Lütfen kontrol edin.")
    return gtin
