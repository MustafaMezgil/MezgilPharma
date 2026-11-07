"""Stok girisi, parti takibi, depolar ve miat uyari ayari.

Roller: Personel faturali giris yapar ve depo ekler; alis fiyatini yazar ama kaydettikten
sonra goremez. Acilis stogu, depo pasif yapma ve miat ayari eczacinindir.
Yetki her islemde veritabanindan okunur.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

import psycopg

from moduller.hatalar import GorunurHata
from moduller.ilac.servis import arama_metni
from moduller.kullanici.servis import Kullanici, Rol, YetkiHatasi, aktif_rol_getir, eczaci_dogrula
from moduller.para import tutar_dogrula
from moduller.stok.kurallar import ay_ekle, net_birim_maliyet, parti_no_duzenle
from veritabani.baglanti import Baglanti

VARSAYILAN_MIAT_UYARI_AYI = 6
_MIAT_ANAHTARI = "miat_uyari_ay"
_EN_AZ_MIAT_AYI = 1
_EN_COK_MIAT_AYI = 60
# ITS hata kodu 11038: SKT uretim tarihinden itibaren 7 yili gecemez.
_AZAMI_SKT_AYI = 84


class HareketTuru(Enum):
    GIRIS = "giris"
    ACILIS = "acilis"

    @property
    def gorunen_ad(self) -> str:
        return "Faturalı giriş" if self is HareketTuru.GIRIS else "Açılış stoğu"


class OnayGerekli(GorunurHata):
    """Kayit oncesi kullanicinin onayini isteyen uyarilar. Bu durumda hicbir sey yazilmaz."""

    def __init__(self, uyarilar: list[str]) -> None:
        super().__init__("\n".join(uyarilar))
        self.uyarilar = uyarilar


@dataclass(frozen=True)
class StokGirisi:
    urun_id: int
    tur: HareketTuru
    parti_no: str | None
    skt: date
    alinan_adet: int
    mf_adet: int
    # Faturadaki satir tutari: KDV haric, iskontolu.
    toplam_tutar: Decimal
    tedarikci_id: int | None
    fatura_no: str | None


@dataclass(frozen=True)
class Parti:
    id: int
    parti_no: str | None
    skt: date
    miktar: int
    birim_maliyet: Decimal | None  # personelde gizli


@dataclass(frozen=True)
class Hareket:
    id: int
    tarih: datetime
    tur: HareketTuru
    parti_no: str | None
    skt: date
    miktar: int
    alinan_adet: int | None
    mf_adet: int | None
    tedarikci_adi: str | None
    fatura_no: str | None
    kullanici_adi: str
    toplam_tutar: Decimal | None  # personelde gizli


@dataclass(frozen=True)
class Tedarikci:
    id: int
    ad: str
    aktif: bool


# --- Miat uyari ayari ---


def _miat_ayini_oku(baglanti: Baglanti) -> int:
    satir = baglanti.execute(
        "SELECT deger FROM eczane_ayarlari WHERE anahtar = %s", (_MIAT_ANAHTARI,)
    ).fetchone()
    return int(satir["deger"]) if satir is not None else VARSAYILAN_MIAT_UYARI_AYI


def miat_uyari_ayi(baglanti: Baglanti, yapan: Kullanici) -> int:
    """Yakin miat uyarisinin kac ay kala verilecegi. 5. adimdaki miat raporu da bunu kullanir."""
    aktif_rol_getir(baglanti, yapan)
    return _miat_ayini_oku(baglanti)


def miat_uyari_ayi_ayarla(baglanti: Baglanti, yapan: Kullanici, ay: int) -> None:
    if not _EN_AZ_MIAT_AYI <= ay <= _EN_COK_MIAT_AYI:
        raise GorunurHata(
            f"Miat uyarı süresi {_EN_AZ_MIAT_AYI} ile {_EN_COK_MIAT_AYI} ay arasında olmalıdır."
        )
    with baglanti.transaction():
        eczaci_dogrula(baglanti, yapan)
        baglanti.execute(
            "INSERT INTO eczane_ayarlari (anahtar, deger) VALUES (%s, %s) "
            "ON CONFLICT (anahtar) DO UPDATE SET deger = EXCLUDED.deger",
            (_MIAT_ANAHTARI, str(ay)),
        )


# --- Depolar ---


def _depo_arama_adi(ad: str) -> str:
    return re.sub(r"\s+", " ", arama_metni(ad)).strip()


def tedarikci_ekle(baglanti: Baglanti, yapan: Kullanici, ad: str) -> int:
    temiz = re.sub(r"\s+", " ", ad).strip()
    if not temiz:
        raise GorunurHata("Depo adı boş olamaz.")
    with baglanti.transaction():
        aktif_rol_getir(baglanti, yapan)
        try:
            satir = baglanti.execute(
                "INSERT INTO tedarikciler (ad, arama_adi) VALUES (%s, %s) RETURNING id",
                (temiz, _depo_arama_adi(temiz)),
            ).fetchone()
        except psycopg.errors.UniqueViolation as hata:
            raise GorunurHata("Bu depo zaten kayıtlı.") from hata
    assert satir is not None
    return satir["id"]


def tedarikcileri_listele(
    baglanti: Baglanti, yapan: Kullanici, *, pasifler_dahil: bool = False
) -> list[Tedarikci]:
    aktif_rol_getir(baglanti, yapan)
    satirlar = baglanti.execute(
        "SELECT id, ad, aktif FROM tedarikciler WHERE aktif OR %s ORDER BY arama_adi, id",
        (pasifler_dahil,),
    ).fetchall()
    return [Tedarikci(id=s["id"], ad=s["ad"], aktif=s["aktif"]) for s in satirlar]


def _tedarikci_durumu(baglanti: Baglanti, yapan: Kullanici, tedarikci_id: int, aktif: bool) -> None:
    with baglanti.transaction():
        eczaci_dogrula(baglanti, yapan)
        satir = baglanti.execute(
            "UPDATE tedarikciler SET aktif = %s WHERE id = %s AND aktif <> %s RETURNING id",
            (aktif, tedarikci_id, aktif),
        ).fetchone()
        if satir is None:
            raise GorunurHata("Depo bulunamadı veya durumu zaten böyle.")


def tedarikci_pasif_yap(baglanti: Baglanti, yapan: Kullanici, tedarikci_id: int) -> None:
    _tedarikci_durumu(baglanti, yapan, tedarikci_id, False)


def tedarikci_aktif_yap(baglanti: Baglanti, yapan: Kullanici, tedarikci_id: int) -> None:
    _tedarikci_durumu(baglanti, yapan, tedarikci_id, True)


# --- Stok girisi ---


def _adet_ve_tutari_dogrula(giris: StokGirisi) -> None:
    if giris.alinan_adet < 0 or giris.mf_adet < 0:
        raise GorunurHata("Adet eksi olamaz.")
    if giris.alinan_adet + giris.mf_adet < 1:
        raise GorunurHata("Miktar en az 1 kutu olmalıdır.")
    tutar_dogrula(giris.toplam_tutar, "Tutar")
    if giris.alinan_adet == 0 and giris.toplam_tutar != 0:
        raise GorunurHata("Yalnızca mal fazlası (bedelsiz) girişte tutar 0 olmalıdır.")


def _belgeyi_dogrula(baglanti: Baglanti, rol: Rol, giris: StokGirisi) -> str | None:
    """Giris turune gore depo ve fatura kurallarini denetler; duzenli fatura no dondurur."""
    fatura_no = (giris.fatura_no or "").strip() or None
    if giris.tur is HareketTuru.ACILIS:
        if rol is not Rol.ECZACI:
            raise YetkiHatasi("Açılış stoğunu yalnızca eczacı girebilir.")
        if giris.tedarikci_id is not None or fatura_no is not None or giris.mf_adet != 0:
            raise GorunurHata("Açılış stoğunda depo, fatura ve mal fazlası girilmez.")
        return None
    if giris.tedarikci_id is None:
        raise GorunurHata("Depo seçilmelidir.")
    if fatura_no is None:
        raise GorunurHata("Fatura numarası girilmelidir.")
    depo = baglanti.execute(
        "SELECT aktif FROM tedarikciler WHERE id = %s FOR SHARE", (giris.tedarikci_id,)
    ).fetchone()
    if depo is None or not depo["aktif"]:
        raise GorunurHata("Depo bulunamadı veya pasif.")
    return fatura_no


def _uyarilari_bul(
    baglanti: Baglanti,
    giris: StokGirisi,
    parti_no: str | None,
    fatura_no: str | None,
    bugun: date,
) -> list[str]:
    uyarilar: list[str] = []
    miat_ayi = _miat_ayini_oku(baglanti)
    if giris.skt < ay_ekle(bugun, miat_ayi):
        uyarilar.append(f"SKT'ye {miat_ayi} aydan az kaldı ({giris.skt:%d.%m.%Y}).")
    if giris.skt > ay_ekle(bugun, _AZAMI_SKT_AYI):
        uyarilar.append(
            "SKT bugünden 7 yıldan uzak. Yazım hatası olabilir (ITS: SKT üretimden "
            "itibaren 7 yılı geçemez)."
        )
    if parti_no is not None:
        farkli = baglanti.execute(
            "SELECT 1 FROM stok_partileri WHERE urun_id = %s AND parti_no = %s AND skt <> %s "
            "LIMIT 1",
            (giris.urun_id, parti_no, giris.skt),
        ).fetchone()
        if farkli is not None:
            uyarilar.append(f"{parti_no} partisi daha önce farklı SKT ile girilmiş.")
    if fatura_no is not None:
        mukerrer = baglanti.execute(
            "SELECT 1 FROM stok_hareketleri h JOIN stok_partileri p ON p.id = h.parti_id "
            "WHERE h.tedarikci_id = %s AND h.fatura_no = %s AND p.urun_id = %s "
            "AND p.parti_no IS NOT DISTINCT FROM %s LIMIT 1",
            (giris.tedarikci_id, fatura_no, giris.urun_id, parti_no),
        ).fetchone()
        if mukerrer is not None:
            uyarilar.append(
                f"Bu ürün ve parti, {fatura_no} numaralı faturadan daha önce girilmiş."
            )
    return uyarilar


def stok_girisi_yap(
    baglanti: Baglanti,
    yapan: Kullanici,
    giris: StokGirisi,
    *,
    uyarilar_onaylandi: bool = False,
) -> int:
    """Stok girer ve parti numarasini dondurur.

    Uyari varsa ve onaylanmadiysa OnayGerekli firlatir; bu durumda hicbir sey yazilmaz.
    Parti, hareket ve miktar tek islemde yazilir.
    """
    _adet_ve_tutari_dogrula(giris)
    with baglanti.transaction():
        rol = aktif_rol_getir(baglanti, yapan)
        fatura_no = _belgeyi_dogrula(baglanti, rol, giris)
        # Urun satiri paylasimli kilitlenir: fiyat degisikligi (FOR UPDATE) bu girisi bekler,
        # boylece fiyat gecmisine yazilan stok miktari tutarli olur.
        urun = baglanti.execute(
            "SELECT urun_turu, karekodlu, aktif FROM urunler WHERE id = %s FOR SHARE",
            (giris.urun_id,),
        ).fetchone()
        if urun is None:
            raise GorunurHata("Ürün bulunamadı.")
        if not urun["aktif"]:
            raise GorunurHata("Ürün pasif; stok girilemez.")
        parti_no = parti_no_duzenle(giris.parti_no, karekodlu=urun["karekodlu"])
        if parti_no is None and urun["urun_turu"] == "ilac":
            raise GorunurHata("Parti numarası ilaçta zorunludur.")

        bugun_satiri = baglanti.execute("SELECT CURRENT_DATE AS bugun").fetchone()
        assert bugun_satiri is not None
        bugun: date = bugun_satiri["bugun"]
        if giris.skt < bugun:
            raise GorunurHata("SKT'si geçmiş ürün girilemez.")

        uyarilar = _uyarilari_bul(baglanti, giris, parti_no, fatura_no, bugun)
        if uyarilar and not uyarilar_onaylandi:
            raise OnayGerekli(uyarilar)

        miktar = giris.alinan_adet + giris.mf_adet
        maliyet = net_birim_maliyet(giris.toplam_tutar, giris.alinan_adet, giris.mf_adet)
        parti = baglanti.execute(
            "INSERT INTO stok_partileri (urun_id, parti_no, skt, miktar, birim_maliyet) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (urun_id, parti_no, skt, birim_maliyet) "
            "DO UPDATE SET miktar = stok_partileri.miktar + EXCLUDED.miktar RETURNING id",
            (giris.urun_id, parti_no, giris.skt, miktar, maliyet),
        ).fetchone()
        assert parti is not None
        baglanti.execute(
            "INSERT INTO stok_hareketleri (parti_id, tur, miktar, alinan_adet, mf_adet, "
            "toplam_tutar, tedarikci_id, fatura_no, kullanici_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                parti["id"],
                giris.tur.value,
                miktar,
                giris.alinan_adet,
                giris.mf_adet,
                giris.toplam_tutar,
                giris.tedarikci_id,
                fatura_no,
                yapan.id,
            ),
        )
    return parti["id"]


# --- Gorunum ---


def partileri_getir(
    baglanti: Baglanti, yapan: Kullanici, urun_id: int, *, bitenler_dahil: bool = False
) -> list[Parti]:
    """Partileri SKT sirasiyla verir. Personelde birim maliyet gizlenir."""
    eczaci = aktif_rol_getir(baglanti, yapan) is Rol.ECZACI
    satirlar = baglanti.execute(
        "SELECT id, parti_no, skt, miktar, birim_maliyet FROM stok_partileri "
        "WHERE urun_id = %s AND (miktar > 0 OR %s) ORDER BY skt, id",
        (urun_id, bitenler_dahil),
    ).fetchall()
    return [
        Parti(
            id=s["id"],
            parti_no=s["parti_no"],
            skt=s["skt"],
            miktar=s["miktar"],
            birim_maliyet=s["birim_maliyet"] if eczaci else None,
        )
        for s in satirlar
    ]


def hareketleri_getir(baglanti: Baglanti, yapan: Kullanici, urun_id: int) -> list[Hareket]:
    """Urunun stok hareketlerini yeniden eskiye verir. Personelde tutar gizlenir."""
    eczaci = aktif_rol_getir(baglanti, yapan) is Rol.ECZACI
    satirlar = baglanti.execute(
        "SELECT h.id, h.tarih, h.tur, p.parti_no, p.skt, h.miktar, h.alinan_adet, h.mf_adet, "
        "t.ad AS tedarikci_adi, h.fatura_no, k.ad_soyad AS kullanici_adi, h.toplam_tutar "
        "FROM stok_hareketleri h "
        "JOIN stok_partileri p ON p.id = h.parti_id "
        "JOIN kullanicilar k ON k.id = h.kullanici_id "
        "LEFT JOIN tedarikciler t ON t.id = h.tedarikci_id "
        "WHERE p.urun_id = %s ORDER BY h.tarih DESC, h.id DESC",
        (urun_id,),
    ).fetchall()
    return [
        Hareket(
            id=s["id"],
            tarih=s["tarih"],
            tur=HareketTuru(s["tur"]),
            parti_no=s["parti_no"],
            skt=s["skt"],
            miktar=s["miktar"],
            alinan_adet=s["alinan_adet"],
            mf_adet=s["mf_adet"],
            tedarikci_adi=s["tedarikci_adi"],
            fatura_no=s["fatura_no"],
            kullanici_adi=s["kullanici_adi"],
            toplam_tutar=s["toplam_tutar"] if eczaci else None,
        )
        for s in satirlar
    ]
