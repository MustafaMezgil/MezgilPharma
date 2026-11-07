"""Stok girisinin veritabanisiz kurallari: SKT okuma, parti numarasi, net maliyet, ay ekleme."""

import calendar
import re
from datetime import date
from decimal import Decimal

from moduller.hatalar import GorunurHata
from moduller.para import yuvarla

MALIYET_ONDALIGI = 4
_PARTI_UZUNLUGU = 20

_GUN_AY_YIL = re.compile(r"([0-9]{1,2})[./]([0-9]{1,2})[./]([0-9]{4})")
_AY_YIL = re.compile(r"([0-9]{1,2})[./]([0-9]{4})")
_ISO = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
# Karekod kilavuzu Madde 5: yalnizca 0-9 ve A-Z.
_KAREKODLU_PARTI = re.compile(r"[A-Z0-9]{1,%d}" % _PARTI_UZUNLUGU)
# Karekodsuz urunlerde (kozmetik, medikal) kucuk harf ve tire de kabul edilir.
_KAREKODSUZ_PARTI = re.compile(r"[A-Za-z0-9-]{1,%d}" % _PARTI_UZUNLUGU)

_SKT_MESAJI = "SKT'yi gün.ay.yıl (31.01.2030) veya ay.yıl (01.2030) biçiminde yazın."


def _ayin_son_gunu(yil: int, ay: int) -> date:
    return date(yil, ay, calendar.monthrange(yil, ay)[1])


def skt_coz(metin: str) -> date:
    """SKT'yi okur. Yalnizca ay ve yil yazilmissa ayin son gunu sayilir."""
    temiz = metin.strip()
    try:
        if eslesme := _GUN_AY_YIL.fullmatch(temiz):
            gun, ay, yil = (int(parca) for parca in eslesme.groups())
            return date(yil, ay, gun)
        if eslesme := _AY_YIL.fullmatch(temiz):
            ay, yil = (int(parca) for parca in eslesme.groups())
            return _ayin_son_gunu(yil, ay)
        if eslesme := _ISO.fullmatch(temiz):
            yil, ay, gun = (int(parca) for parca in eslesme.groups())
            return date(yil, ay, gun)
    except ValueError as hata:
        raise GorunurHata(f"Geçersiz tarih. {_SKT_MESAJI}") from hata
    raise GorunurHata(_SKT_MESAJI)


def parti_no_duzenle(metin: str | None, *, karekodlu: bool) -> str | None:
    """Parti numarasini denetler; bos ise None dondurur. Numara kendiliginden degistirilmez."""
    temiz = (metin or "").strip()
    if not temiz:
        return None
    if karekodlu:
        if not _KAREKODLU_PARTI.fullmatch(temiz):
            raise GorunurHata(
                "Parti numarası karekodlu ilaçta yalnızca büyük harf (A-Z) ve rakam içerebilir, "
                f"en fazla {_PARTI_UZUNLUGU} karakter olabilir. Kutudakiyle aynı yazın."
            )
    elif not _KAREKODSUZ_PARTI.fullmatch(temiz):
        raise GorunurHata(
            "Parti numarası yalnızca harf (Türkçe karakter olmadan), rakam ve tire içerebilir, "
            f"en fazla {_PARTI_UZUNLUGU} karakter olabilir."
        )
    return temiz


def net_birim_maliyet(toplam_tutar: Decimal, alinan_adet: int, mf_adet: int) -> Decimal:
    """Mal fazlasi dahil kutu basina net maliyet: toplam tutar / toplam kutu, 4 hane."""
    kutu = alinan_adet + mf_adet
    if kutu <= 0:
        raise GorunurHata("Miktar en az 1 kutu olmalıdır.")
    return yuvarla(toplam_tutar / kutu, MALIYET_ONDALIGI)


def ay_ekle(baslangic: date, ay: int) -> date:
    """Tarihe ay ekler; gun o ayda yoksa ayin son gunu alinir (31 Agustos + 6 ay = 28 Subat)."""
    toplam = baslangic.year * 12 + baslangic.month - 1 + ay
    yil, ay_no = divmod(toplam, 12)
    son_gun = calendar.monthrange(yil, ay_no + 1)[1]
    return date(yil, ay_no + 1, min(baslangic.day, son_gun))
