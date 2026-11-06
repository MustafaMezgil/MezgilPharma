"""Tutar ve oran okuma, denetleme, yazma. Para icin float kullanilmaz.

Girilen tutar yuvarlanmaz: kurustan fazla ondalik varsa reddedilir.
"""

import re
from decimal import Decimal

from moduller.hatalar import GorunurHata

_AZAMI_TUTAR = Decimal("10000000000")  # NUMERIC(12, 2) siniri
_AZAMI_ORAN = Decimal("100")
_AZAMI_ONDALIK = 2
_BINLIKLI = re.compile(r"[0-9]{1,3}(\.[0-9]{3})+,[0-9]{1,2}")
_DUZ = re.compile(r"[0-9]+([.,][0-9]{1,2})?")


def tutar_dogrula(tutar: Decimal, alan: str) -> None:
    """Tutar sifir veya pozitif, en fazla iki ondalikli ve sinirin altinda olmalidir."""
    if not tutar.is_finite() or tutar < 0 or tutar >= _AZAMI_TUTAR:
        raise GorunurHata(f"{alan}: geçerli bir tutar girin.")
    us = tutar.as_tuple().exponent
    if isinstance(us, int) and us < -_AZAMI_ONDALIK:
        raise GorunurHata(f"{alan}: kuruştan sonra en fazla iki hane yazılabilir.")


def oran_dogrula(oran: Decimal, alan: str) -> None:
    tutar_dogrula(oran, alan)
    if oran > _AZAMI_ORAN:
        raise GorunurHata(f"{alan}: 0 ile 100 arasında olmalıdır.")


def para_coz(metin: str, alan: str) -> Decimal:
    """Kullanicinin yazdigi tutari okur. Belirsiz yaziyi (1.234 gibi) tahmin etmez."""
    temiz = metin.strip()
    if _BINLIKLI.fullmatch(temiz):
        temiz = temiz.replace(".", "")
    elif not _DUZ.fullmatch(temiz):
        raise GorunurHata(f"{alan}: tutarı doğru yazın. Örnek: 125,50")
    tutar = Decimal(temiz.replace(",", "."))
    tutar_dogrula(tutar, alan)
    return tutar


def oran_coz(metin: str, alan: str) -> Decimal:
    oran = para_coz(metin, alan)
    oran_dogrula(oran, alan)
    return oran


def para_metni(tutar: Decimal) -> str:
    """Tutari ekranda gosterilecek bicimde yazar: 1.234,50"""
    return f"{tutar:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
