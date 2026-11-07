"""Tutar ve oran okuma, denetleme, yuvarlama ve yazma. Para icin float kullanilmaz.

Yuvarlama kurali tek yerdedir: yuvarla(). Yarim ve ustu yukari yuvarlanir (ROUND_HALF_UP).
Girilen tutar yuvarlanmaz: izin verilenden fazla ondalik varsa reddedilir.
"""

import re
from decimal import ROUND_HALF_UP, Decimal

from moduller.hatalar import GorunurHata

_AZAMI_TUTAR = Decimal("10000000000")  # NUMERIC(12, 2) siniri
_AZAMI_ORAN = Decimal("100")
_PARA_ONDALIGI = 2
_BINLIKLI = r"[0-9]{1,3}(\.[0-9]{3})+,[0-9]{1,%d}"
_DUZ = r"[0-9]+([.,][0-9]{1,%d})?"


def yuvarla(tutar: Decimal, hane: int) -> Decimal:
    """Programdaki tek yuvarlama kurali: yarim ve ustu yukari (0,125 -> 0,13)."""
    return tutar.quantize(Decimal(1).scaleb(-hane), rounding=ROUND_HALF_UP)


def tutar_dogrula(tutar: Decimal, alan: str, *, ondalik: int = _PARA_ONDALIGI) -> None:
    """Tutar sifir veya pozitif, en fazla izin verilen ondalikli ve sinirin altinda olmalidir."""
    if not tutar.is_finite() or tutar < 0 or tutar >= _AZAMI_TUTAR:
        raise GorunurHata(f"{alan}: geçerli bir tutar girin.")
    us = tutar.as_tuple().exponent
    if isinstance(us, int) and us < -ondalik:
        raise GorunurHata(f"{alan}: virgülden sonra en fazla {ondalik} hane yazılabilir.")


def oran_dogrula(oran: Decimal, alan: str) -> None:
    tutar_dogrula(oran, alan)
    if oran > _AZAMI_ORAN:
        raise GorunurHata(f"{alan}: 0 ile 100 arasında olmalıdır.")


def para_coz(metin: str, alan: str, *, ondalik: int = _PARA_ONDALIGI) -> Decimal:
    """Kullanicinin yazdigi tutari okur. Belirsiz yaziyi (1.234 gibi) tahmin etmez."""
    temiz = metin.strip()
    if re.fullmatch(_BINLIKLI % ondalik, temiz):
        temiz = temiz.replace(".", "")
    elif not re.fullmatch(_DUZ % ondalik, temiz):
        raise GorunurHata(f"{alan}: tutarı doğru yazın. Örnek: 125,50")
    tutar = Decimal(temiz.replace(",", "."))
    tutar_dogrula(tutar, alan, ondalik=ondalik)
    return tutar


def oran_coz(metin: str, alan: str) -> Decimal:
    oran = para_coz(metin, alan)
    oran_dogrula(oran, alan)
    return oran


def para_metni(tutar: Decimal) -> str:
    """Tutari ekranda gosterilecek bicimde yazar: 1.234,50"""
    return f"{yuvarla(tutar, _PARA_ONDALIGI):,}".replace(",", "X").replace(".", ",").replace("X", ".")
