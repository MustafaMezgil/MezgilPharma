"""Urun karti: ekleme, duzenleme, fiyat gecmisi, arama, pasif yapma, eczaci onayi.

Roller: Personel karti fiyatsiz acar; actigi kart eczaci onayi bekler. Personel recete
turu, barkod, karekodlu ve urun turunu yeni kartta doldurur ama sonradan degistiremez.
Fiyat, KDV, pasif yapma ve onay eczacinindir. Yetki her islemde veritabanindan okunur.
Her kart islemi erisim_log'a yazilir.
"""

import re
from dataclasses import dataclass, fields, replace
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import LiteralString

import psycopg
from psycopg.rows import DictRow

from moduller.hatalar import GorunurHata
from moduller.ilac.gtin import gtin_normalle
from moduller.kullanici.servis import (
    Kullanici,
    Rol,
    YetkiHatasi,
    aktif_rol_getir,
    eczaci_dogrula,
    islem_kaydet,
)
from moduller.para import oran_dogrula, tutar_dogrula
from veritabani.baglanti import Baglanti

ARAMA_SINIRI = 200

_ATC_KODU = re.compile(r"[A-Z0-9]{1,7}")
_ARAMA_HARFLERI = str.maketrans("İIışğçöüŞĞÇÖÜ", "iiisgcousgcou")
_BULUNAMADI_MESAJI = "Ürün bulunamadı."
_FIYAT_YETKI_MESAJI = "Fiyat ve KDV bilgisini yalnızca eczacı girebilir."
_KAYIT_TURU = "urun"
# Personelin yeni kartta doldurup sonradan degistiremedigi alanlar.
_ECZACI_ALANLARI = frozenset({"urun_turu", "recete_turu", "gtin", "karekodlu"})
# Erisim kaydina eski ve yeni degeriyle yazilan alanlar; digerlerinin yalnizca adi yazilir.
_DEGERI_KAYDEDILEN_ALANLAR = (
    "urun_turu",
    "recete_turu",
    "gtin",
    "karekodlu",
    "soguk_zincir",
    "kdv_orani",
)

_URUN_SORGUSU: LiteralString = """
    SELECT u.*, COALESCE(s.miktar, 0) AS stok_miktari, s.en_yakin_skt
    FROM urunler u
    LEFT JOIN (
        SELECT urun_id, SUM(miktar) AS miktar, MIN(skt) AS en_yakin_skt
        FROM stok_partileri WHERE miktar > 0 GROUP BY urun_id
    ) s ON s.urun_id = u.id
"""


class UrunTuru(Enum):
    ILAC = "ilac"
    DIGER = "diger"

    @property
    def gorunen_ad(self) -> str:
        return "İlaç" if self is UrunTuru.ILAC else "Diğer ürün"


class ReceteTuru(Enum):
    RECETESIZ = "recetesiz"
    NORMAL = "normal"
    KIRMIZI = "kirmizi"
    YESIL = "yesil"
    MOR = "mor"
    TURUNCU = "turuncu"

    @property
    def gorunen_ad(self) -> str:
        return {
            ReceteTuru.RECETESIZ: "Reçetesiz",
            ReceteTuru.NORMAL: "Normal (beyaz)",
            ReceteTuru.KIRMIZI: "Kırmızı",
            ReceteTuru.YESIL: "Yeşil",
            ReceteTuru.MOR: "Mor",
            ReceteTuru.TURUNCU: "Turuncu",
        }[self]


@dataclass(frozen=True)
class UrunBilgisi:
    """Kartin fiyat disindaki bilgileri; personel de duzenleyebilir."""

    ad: str
    gtin: str | None
    urun_turu: UrunTuru
    karekodlu: bool
    recete_turu: ReceteTuru
    kritik_stok: int
    raf_yeri: str | None
    etken_madde: str | None
    farmasotik_form: str | None
    atc_kodu: str | None
    uretici_firma: str | None
    soguk_zincir: bool


@dataclass(frozen=True)
class UrunFiyati:
    """Yalnizca eczaci girer."""

    psf: Decimal
    kamu_fiyati: Decimal | None
    kdv_orani: Decimal


@dataclass(frozen=True)
class Urun:
    id: int
    bilgi: UrunBilgisi
    psf: Decimal | None
    kamu_fiyati: Decimal | None
    kdv_orani: Decimal | None
    aktif: bool
    onay_bekliyor: bool
    stok_miktari: int
    en_yakin_skt: date | None

    @property
    def ad(self) -> str:
        return self.bilgi.ad

    @property
    def gtin(self) -> str | None:
        return self.bilgi.gtin

    @property
    def urun_turu(self) -> UrunTuru:
        return self.bilgi.urun_turu

    @property
    def karekodlu(self) -> bool:
        return self.bilgi.karekodlu

    @property
    def recete_turu(self) -> ReceteTuru:
        return self.bilgi.recete_turu

    @property
    def kritik_stok(self) -> int:
        return self.bilgi.kritik_stok

    @property
    def etken_madde(self) -> str | None:
        return self.bilgi.etken_madde

    @property
    def farmasotik_form(self) -> str | None:
        return self.bilgi.farmasotik_form

    @property
    def atc_kodu(self) -> str | None:
        return self.bilgi.atc_kodu

    @property
    def soguk_zincir(self) -> bool:
        return self.bilgi.soguk_zincir


def arama_metni(metin: str) -> str:
    """Buyuk-kucuk harf ve Turkce harf farkini kaldirir: ILAC, ilaç ve İLAÇ ayni sayilir."""
    return metin.translate(_ARAMA_HARFLERI).lower()


def _bosa_cevir(metin: str | None) -> str | None:
    temiz = (metin or "").strip()
    return temiz or None


def _bilgiyi_duzenle(bilgi: UrunBilgisi) -> UrunBilgisi:
    """Kurallari denetler ve bilgiyi kaydedilecek bicime getirir."""
    ad = bilgi.ad.strip()
    if not ad:
        raise GorunurHata("Ürün adı boş olamaz.")
    gtin = _bosa_cevir(bilgi.gtin)
    if gtin is not None:
        gtin = gtin_normalle(gtin)
    if bilgi.karekodlu and gtin is None:
        raise GorunurHata("Karekodlu üründe barkod zorunludur.")
    if bilgi.urun_turu is not UrunTuru.ILAC and bilgi.recete_turu is not ReceteTuru.RECETESIZ:
        raise GorunurHata("Reçete türü yalnızca ilaçlarda seçilebilir.")
    if bilgi.kritik_stok < 0:
        raise GorunurHata("Kritik stok eksi olamaz.")
    atc = _bosa_cevir(bilgi.atc_kodu)
    if atc is not None:
        atc = atc.upper()
        if not _ATC_KODU.fullmatch(atc):
            raise GorunurHata("ATC kodu en fazla 7 harf ve rakamdan oluşmalıdır.")
    return replace(
        bilgi,
        ad=ad,
        gtin=gtin,
        atc_kodu=atc,
        raf_yeri=_bosa_cevir(bilgi.raf_yeri),
        etken_madde=_bosa_cevir(bilgi.etken_madde),
        farmasotik_form=_bosa_cevir(bilgi.farmasotik_form),
        uretici_firma=_bosa_cevir(bilgi.uretici_firma),
    )


def _fiyati_dogrula(fiyat: UrunFiyati) -> None:
    tutar_dogrula(fiyat.psf, "PSF")
    if fiyat.psf == 0:
        raise GorunurHata("PSF: sıfırdan büyük olmalıdır.")
    if fiyat.kamu_fiyati is not None:
        tutar_dogrula(fiyat.kamu_fiyati, "Kamu fiyatı")
    oran_dogrula(fiyat.kdv_orani, "KDV")


def _arama_alani(bilgi: UrunBilgisi) -> str:
    parcalar = (
        bilgi.ad,
        bilgi.etken_madde,
        bilgi.farmasotik_form,
        bilgi.atc_kodu,
        bilgi.uretici_firma,
        bilgi.gtin,
    )
    return arama_metni(" ".join(parca for parca in parcalar if parca))


def _bilgi_degerleri(bilgi: UrunBilgisi) -> dict[str, object]:
    return {
        "ad": bilgi.ad,
        "arama_metni": _arama_alani(bilgi),
        "gtin": bilgi.gtin,
        "urun_turu": bilgi.urun_turu.value,
        "karekodlu": bilgi.karekodlu,
        "recete_turu": bilgi.recete_turu.value,
        "etken_madde": bilgi.etken_madde,
        "farmasotik_form": bilgi.farmasotik_form,
        "atc_kodu": bilgi.atc_kodu,
        "uretici_firma": bilgi.uretici_firma,
        "soguk_zincir": bilgi.soguk_zincir,
        "raf_yeri": bilgi.raf_yeri,
        "kritik_stok": bilgi.kritik_stok,
    }


def _fiyat_kaydet(
    baglanti: Baglanti, yapan: Kullanici, urun_id: int, fiyat: UrunFiyati
) -> None:
    """Fiyati yazar; PSF veya kamu fiyati degistiyse gecmise o anki stokla birlikte ekler."""
    # Urun satiri kilitlidir: stok yazan islemler bu sirada miktari degistiremez.
    eski = baglanti.execute(
        "SELECT psf, kamu_fiyati FROM urunler WHERE id = %s FOR UPDATE", (urun_id,)
    ).fetchone()
    assert eski is not None
    if eski["psf"] != fiyat.psf or eski["kamu_fiyati"] != fiyat.kamu_fiyati:
        baglanti.execute(
            "INSERT INTO fiyat_gecmisi (urun_id, eski_psf, yeni_psf, eski_kamu_fiyati, "
            "yeni_kamu_fiyati, stok_miktari, kullanici_id) "
            "SELECT %s, %s, %s, %s, %s, COALESCE(SUM(miktar), 0), %s "
            "FROM stok_partileri WHERE urun_id = %s",
            (
                urun_id,
                eski["psf"],
                fiyat.psf,
                eski["kamu_fiyati"],
                fiyat.kamu_fiyati,
                yapan.id,
                urun_id,
            ),
        )
    baglanti.execute(
        "UPDATE urunler SET psf = %s, kamu_fiyati = %s, kdv_orani = %s WHERE id = %s",
        (fiyat.psf, fiyat.kamu_fiyati, fiyat.kdv_orani, urun_id),
    )


def urun_ekle(
    baglanti: Baglanti, yapan: Kullanici, bilgi: UrunBilgisi, fiyat: UrunFiyati | None
) -> int:
    """Yeni kart acar. Eczaci fiyat girmek zorundadir, personel giremez."""
    with baglanti.transaction():
        rol = aktif_rol_getir(baglanti, yapan)
        if rol is Rol.ECZACI and fiyat is None:
            raise GorunurHata("PSF ve KDV girilmelidir.")
        if rol is not Rol.ECZACI and fiyat is not None:
            raise YetkiHatasi(_FIYAT_YETKI_MESAJI)
        duzenli = _bilgiyi_duzenle(bilgi)
        if fiyat is not None:
            _fiyati_dogrula(fiyat)
        try:
            satir = baglanti.execute(
                "INSERT INTO urunler (ad, arama_metni, gtin, urun_turu, karekodlu, recete_turu, "
                "etken_madde, farmasotik_form, atc_kodu, uretici_firma, soguk_zincir, raf_yeri, "
                "kritik_stok, onay_bekliyor) VALUES (%(ad)s, %(arama_metni)s, %(gtin)s, "
                "%(urun_turu)s, %(karekodlu)s, %(recete_turu)s, %(etken_madde)s, "
                "%(farmasotik_form)s, %(atc_kodu)s, %(uretici_firma)s, %(soguk_zincir)s, "
                "%(raf_yeri)s, %(kritik_stok)s, %(onay_bekliyor)s) RETURNING id",
                {**_bilgi_degerleri(duzenli), "onay_bekliyor": rol is not Rol.ECZACI},
            ).fetchone()
        except psycopg.errors.UniqueViolation as hata:
            raise GorunurHata("Bu barkod başka bir üründe kayıtlı.") from hata
        assert satir is not None
        urun_id: int = satir["id"]
        if fiyat is not None:
            _fiyat_kaydet(baglanti, yapan, urun_id, fiyat)
        islem_kaydet(baglanti, yapan.id, "urun_ekleme", urun_id, kayit_turu=_KAYIT_TURU)
    return urun_id


def _kayit_degeri(deger: object) -> object:
    """Erisim kaydina yazilacak degeri JSON'a uygun hale getirir."""
    if isinstance(deger, Enum):
        return deger.value
    if isinstance(deger, Decimal):
        return f"{deger:.2f}"
    return deger


def urun_guncelle(
    baglanti: Baglanti,
    yapan: Kullanici,
    urun_id: int,
    bilgi: UrunBilgisi,
    fiyat: UrunFiyati | None,
) -> None:
    """Karti duzenler. fiyat None ise fiyatlara dokunulmaz. Degisiklik varsa kaydedilir."""
    with baglanti.transaction():
        rol = aktif_rol_getir(baglanti, yapan)
        if rol is not Rol.ECZACI and fiyat is not None:
            raise YetkiHatasi(_FIYAT_YETKI_MESAJI)
        duzenli = _bilgiyi_duzenle(bilgi)
        if fiyat is not None:
            _fiyati_dogrula(fiyat)
        eski_satir = baglanti.execute(
            "SELECT * FROM urunler WHERE id = %s FOR UPDATE", (urun_id,)
        ).fetchone()
        if eski_satir is None:
            raise GorunurHata(_BULUNAMADI_MESAJI)
        eski_bilgi = _satirdan_bilgi(eski_satir)

        eski: dict[str, object] = {f.name: getattr(eski_bilgi, f.name) for f in fields(UrunBilgisi)}
        yeni: dict[str, object] = {f.name: getattr(duzenli, f.name) for f in fields(UrunBilgisi)}
        if fiyat is not None:
            eski.update(
                psf=eski_satir["psf"],
                kamu_fiyati=eski_satir["kamu_fiyati"],
                kdv_orani=eski_satir["kdv_orani"],
            )
            yeni.update(psf=fiyat.psf, kamu_fiyati=fiyat.kamu_fiyati, kdv_orani=fiyat.kdv_orani)
        degisen = sorted(alan for alan in yeni if yeni[alan] != eski[alan])

        if rol is not Rol.ECZACI and _ECZACI_ALANLARI.intersection(degisen):
            raise YetkiHatasi(
                "Reçete türü, barkod, karekod ve ürün türünü yalnızca eczacı değiştirebilir. "
                "Kart bu arada değiştiyse kapatıp yeniden açın."
            )
        if not degisen:
            return

        try:
            baglanti.execute(
                "UPDATE urunler SET ad = %(ad)s, arama_metni = %(arama_metni)s, gtin = %(gtin)s, "
                "urun_turu = %(urun_turu)s, karekodlu = %(karekodlu)s, "
                "recete_turu = %(recete_turu)s, etken_madde = %(etken_madde)s, "
                "farmasotik_form = %(farmasotik_form)s, atc_kodu = %(atc_kodu)s, "
                "uretici_firma = %(uretici_firma)s, soguk_zincir = %(soguk_zincir)s, "
                "raf_yeri = %(raf_yeri)s, kritik_stok = %(kritik_stok)s "
                "WHERE id = %(urun_id)s",
                {**_bilgi_degerleri(duzenli), "urun_id": urun_id},
            )
        except psycopg.errors.UniqueViolation as hata:
            raise GorunurHata("Bu barkod başka bir üründe kayıtlı.") from hata
        if fiyat is not None:
            _fiyat_kaydet(baglanti, yapan, urun_id, fiyat)

        kritik = {
            alan: {"eski": _kayit_degeri(eski[alan]), "yeni": _kayit_degeri(yeni[alan])}
            for alan in _DEGERI_KAYDEDILEN_ALANLAR
            if alan in degisen
        }
        islem_kaydet(
            baglanti,
            yapan.id,
            "urun_guncelleme",
            urun_id,
            kayit_turu=_KAYIT_TURU,
            ayrinti={"degisen": degisen, "kritik": kritik},
        )


def _durum_degistir(
    baglanti: Baglanti,
    yapan: Kullanici,
    urun_id: int,
    sorgu: LiteralString,
    islem: str,
    hata_mesaji: str,
) -> None:
    with baglanti.transaction():
        eczaci_dogrula(baglanti, yapan)
        if baglanti.execute(sorgu, (urun_id,)).fetchone() is None:
            raise GorunurHata(hata_mesaji)
        islem_kaydet(baglanti, yapan.id, islem, urun_id, kayit_turu=_KAYIT_TURU)


def urun_pasif_yap(baglanti: Baglanti, yapan: Kullanici, urun_id: int) -> None:
    _durum_degistir(
        baglanti,
        yapan,
        urun_id,
        "UPDATE urunler SET aktif = FALSE WHERE id = %s AND aktif RETURNING id",
        "urun_pasif_yapma",
        "Ürün bulunamadı veya zaten pasif.",
    )


def urun_aktif_yap(baglanti: Baglanti, yapan: Kullanici, urun_id: int) -> None:
    _durum_degistir(
        baglanti,
        yapan,
        urun_id,
        "UPDATE urunler SET aktif = TRUE WHERE id = %s AND NOT aktif RETURNING id",
        "urun_aktif_yapma",
        "Ürün bulunamadı veya zaten aktif.",
    )


def urun_onayla(baglanti: Baglanti, yapan: Kullanici, urun_id: int) -> None:
    """Personelin actigi karti eczaci onaylar."""
    _durum_degistir(
        baglanti,
        yapan,
        urun_id,
        "UPDATE urunler SET onay_bekliyor = FALSE WHERE id = %s AND onay_bekliyor RETURNING id",
        "urun_onaylama",
        "Bu ürün eczacı onayı beklemiyor.",
    )


def _satirdan_bilgi(satir: DictRow) -> UrunBilgisi:
    return UrunBilgisi(
        ad=satir["ad"],
        gtin=satir["gtin"],
        urun_turu=UrunTuru(satir["urun_turu"]),
        karekodlu=satir["karekodlu"],
        recete_turu=ReceteTuru(satir["recete_turu"]),
        kritik_stok=satir["kritik_stok"],
        raf_yeri=satir["raf_yeri"],
        etken_madde=satir["etken_madde"],
        farmasotik_form=satir["farmasotik_form"],
        atc_kodu=satir["atc_kodu"],
        uretici_firma=satir["uretici_firma"],
        soguk_zincir=satir["soguk_zincir"],
    )


def _satirdan_urun(satir: DictRow) -> Urun:
    return Urun(
        id=satir["id"],
        bilgi=_satirdan_bilgi(satir),
        psf=satir["psf"],
        kamu_fiyati=satir["kamu_fiyati"],
        kdv_orani=satir["kdv_orani"],
        aktif=satir["aktif"],
        onay_bekliyor=satir["onay_bekliyor"],
        stok_miktari=int(satir["stok_miktari"]),
        en_yakin_skt=satir["en_yakin_skt"],
    )


def urun_getir(baglanti: Baglanti, yapan: Kullanici, urun_id: int) -> Urun:
    aktif_rol_getir(baglanti, yapan)
    satir = baglanti.execute(_URUN_SORGUSU + " WHERE u.id = %s", (urun_id,)).fetchone()
    if satir is None:
        raise GorunurHata(_BULUNAMADI_MESAJI)
    return _satirdan_urun(satir)


def _like_kalibi(kelime: str) -> str:
    kacisli = kelime.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{kacisli}%"


def urun_ara(
    baglanti: Baglanti,
    yapan: Kullanici,
    aranan: str,
    *,
    pasifler_dahil: bool = False,
    yalnizca_onay_bekleyen: bool = False,
    limit: int = ARAMA_SINIRI,
) -> list[Urun]:
    """Ad, etken madde, form, ATC, firma ve barkodda arar. Her kelime gecmelidir."""
    aktif_rol_getir(baglanti, yapan)
    kaliplar = [_like_kalibi(kelime) for kelime in arama_metni(aranan).split()]
    satirlar = baglanti.execute(
        _URUN_SORGUSU
        + " WHERE u.arama_metni LIKE ALL (%s::text[]) AND (u.aktif OR %s)"
        " AND (u.onay_bekliyor OR NOT %s)"
        " ORDER BY u.arama_metni, u.id LIMIT %s",
        (kaliplar, pasifler_dahil, yalnizca_onay_bekleyen, limit),
    ).fetchall()
    return [_satirdan_urun(satir) for satir in satirlar]
