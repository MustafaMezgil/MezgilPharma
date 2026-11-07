"""Kullanici hesaplari: olusturma, giris, hatali giris kilidi ve eczaci islemleri."""

import logging
from dataclasses import dataclass
from enum import Enum

import psycopg
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from moduller.hatalar import GorunurHata
from moduller.kullanici.parola import parola_dogru_mu, parola_ozetle
from veritabani.baglanti import Baglanti

ASGARI_PAROLA_UZUNLUGU = 8
AZAMI_HATALI_GIRIS = 5
KILIT_SURESI_DAKIKA = 15

_KAYIT_TURU = "kullanici"
_BULUNAMADI_MESAJI = "Kullanıcı bulunamadı veya pasif."

_log = logging.getLogger(__name__)


class KullaniciHatasi(GorunurHata):
    """Mesaji kullaniciya gosterilebilecek, Turkce bir kullanici hatasi."""


class HesapKilitliHatasi(KullaniciHatasi):
    """Hesap, hatali denemeler nedeniyle gecici olarak kilitli."""


class YetkiHatasi(KullaniciHatasi):
    """Islemi yapan kisinin yetkisi yok."""


class Rol(Enum):
    ECZACI = "eczaci"
    PERSONEL = "personel"

    @property
    def gorunen_ad(self) -> str:
        return "Eczacı" if self is Rol.ECZACI else "Personel"


@dataclass(frozen=True)
class Kullanici:
    id: int
    kullanici_adi: str
    ad_soyad: str
    rol: Rol
    parola_degismeli: bool = False


@dataclass(frozen=True)
class KullaniciOzeti:
    """Kullanicilar ekraninda gosterilen bilgiler. Parola ozeti tasimaz."""

    id: int
    kullanici_adi: str
    ad_soyad: str
    rol: Rol
    aktif: bool
    kilitli: bool


def aktif_kullanici_var_mi(baglanti: Baglanti) -> bool:
    satir = baglanti.execute("SELECT 1 FROM kullanicilar WHERE aktif LIMIT 1").fetchone()
    return satir is not None


def parola_kurali_dogrula(parola: str) -> None:
    if len(parola) < ASGARI_PAROLA_UZUNLUGU:
        raise KullaniciHatasi(
            f"Parola en az {ASGARI_PAROLA_UZUNLUGU} karakter olmalıdır."
        )


def kullanici_olustur(
    baglanti: Baglanti,
    kullanici_adi: str,
    ad_soyad: str,
    parola: str,
    rol: Rol,
    *,
    parola_degismeli: bool = False,
) -> int:
    """Hesap olusturur ve numarasini dondurur. Yetki kontrolu yapmaz: ilk kurulum icindir."""
    kullanici_adi = kullanici_adi.strip()
    ad_soyad = ad_soyad.strip()
    if not kullanici_adi:
        raise KullaniciHatasi("Kullanıcı adı boş olamaz.")
    if not ad_soyad:
        raise KullaniciHatasi("Ad soyad boş olamaz.")
    parola_kurali_dogrula(parola)

    try:
        satir = baglanti.execute(
            "INSERT INTO kullanicilar "
            "(kullanici_adi, ad_soyad, parola_ozeti, rol, parola_degismeli) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (kullanici_adi, ad_soyad, parola_ozetle(parola), rol.value, parola_degismeli),
        ).fetchone()
    except psycopg.errors.UniqueViolation as hata:
        raise KullaniciHatasi("Bu kullanıcı adı zaten kullanılıyor.") from hata
    assert satir is not None
    return satir["id"]


def _satirdan_kullanici(satir: DictRow) -> Kullanici:
    return Kullanici(
        id=satir["id"],
        kullanici_adi=satir["kullanici_adi"],
        ad_soyad=satir["ad_soyad"],
        rol=Rol(satir["rol"]),
        parola_degismeli=satir["parola_degismeli"],
    )


def _hatali_denemeyi_say(baglanti: Baglanti, kullanici_id: int) -> bool:
    """Sayaci artirir; sinira ulasildiysa hesabi kilitler ve True dondurur."""
    satir = baglanti.execute(
        "UPDATE kullanicilar SET "
        "hatali_giris_sayisi = CASE WHEN hatali_giris_sayisi + 1 >= %(sinir)s "
        "THEN 0 ELSE hatali_giris_sayisi + 1 END, "
        "kilit_bitis = CASE WHEN hatali_giris_sayisi + 1 >= %(sinir)s "
        "THEN now() + make_interval(mins => %(dakika)s) ELSE kilit_bitis END "
        "WHERE id = %(id)s RETURNING hatali_giris_sayisi = 0 AS kilitlendi",
        {"sinir": AZAMI_HATALI_GIRIS, "dakika": KILIT_SURESI_DAKIKA, "id": kullanici_id},
    ).fetchone()
    assert satir is not None
    return satir["kilitlendi"]


def giris_dogrula(
    baglanti: Baglanti, kullanici_adi: str, parola: str
) -> Kullanici | None:
    """Bilgiler dogruysa kullaniciyi, degilse None dondurur.

    Hesap kilitliyse (veya bu deneme kilitlediyse) HesapKilitliHatasi firlatir.
    """
    # Satir kilidi ayni anda gelen denemeleri siraya sokar: hicbiri sayactan kacamaz.
    # Hata, islem kaydedildikten sonra firlatilir; yoksa sayac geri alinirdi.
    with baglanti.transaction():
        satir = baglanti.execute(
            "SELECT id, kullanici_adi, ad_soyad, rol, parola_ozeti, parola_degismeli, "
            "CEIL(EXTRACT(EPOCH FROM kilit_bitis - now()) / 60)::INTEGER AS kalan_dakika "
            "FROM kullanicilar WHERE kullanici_adi = %s AND aktif FOR UPDATE",
            (kullanici_adi.strip(),),
        ).fetchone()
        if satir is None:
            return None

        kalan = satir["kalan_dakika"]
        if kalan is None or kalan <= 0:
            if parola_dogru_mu(parola, satir["parola_ozeti"]):
                baglanti.execute(
                    "UPDATE kullanicilar SET hatali_giris_sayisi = 0, kilit_bitis = NULL "
                    "WHERE id = %s",
                    (satir["id"],),
                )
                return _satirdan_kullanici(satir)
            if not _hatali_denemeyi_say(baglanti, satir["id"]):
                return None
            _log.warning("Hesap kilitlendi: kullanici_id=%s", satir["id"])
            kalan = KILIT_SURESI_DAKIKA

    dakika = min(kalan, KILIT_SURESI_DAKIKA)
    raise HesapKilitliHatasi(f"Hesap kilitli. {dakika} dakika sonra tekrar deneyin.")


def islem_kaydet(
    baglanti: Baglanti,
    yapan_id: int,
    islem: str,
    hedef_id: int,
    *,
    kayit_turu: str = _KAYIT_TURU,
    ayrinti: dict[str, object] | None = None,
) -> None:
    """Islemi denetim kaydina yazar. Parola veya hasta bilgisi yazilmaz."""
    baglanti.execute(
        "INSERT INTO erisim_log (kullanici_id, islem, kayit_turu, kayit_id, ayrinti) "
        "VALUES (%s, %s, %s, %s, %s)",
        (yapan_id, islem, kayit_turu, hedef_id, Jsonb(ayrinti) if ayrinti is not None else None),
    )


def gecici_parola_yaz(baglanti: Baglanti, kullanici_id: int, parola: str) -> bool:
    """Gecici parola belirler, kilidi kaldirir. Aktif hesap yoksa False dondurur."""
    satir = baglanti.execute(
        "UPDATE kullanicilar SET parola_ozeti = %s, parola_degismeli = TRUE, "
        "hatali_giris_sayisi = 0, kilit_bitis = NULL "
        "WHERE id = %s AND aktif RETURNING id",
        (parola_ozetle(parola), kullanici_id),
    ).fetchone()
    return satir is not None


def aktif_rol_getir(baglanti: Baglanti, yapan: Kullanici) -> Rol:
    """Rolu her islemde veritabanindan okur: program acikken degismis olabilir."""
    satir = baglanti.execute(
        "SELECT rol FROM kullanicilar WHERE id = %s AND aktif FOR SHARE", (yapan.id,)
    ).fetchone()
    if satir is None:
        raise YetkiHatasi("Hesabınız artık aktif değil.")
    return Rol(satir["rol"])


def eczaci_dogrula(baglanti: Baglanti, yapan: Kullanici) -> None:
    if aktif_rol_getir(baglanti, yapan) is not Rol.ECZACI:
        raise YetkiHatasi("Bu işlem için eczacı yetkisi gerekir.")


def personel_ekle(
    baglanti: Baglanti,
    yapan: Kullanici,
    kullanici_adi: str,
    ad_soyad: str,
    gecici_parola: str,
    rol: Rol,
) -> int:
    """Eczaci yeni hesap acar. Kisi ilk giriste kendi parolasini belirler."""
    with baglanti.transaction():
        eczaci_dogrula(baglanti, yapan)
        yeni_id = kullanici_olustur(
            baglanti, kullanici_adi, ad_soyad, gecici_parola, rol, parola_degismeli=True
        )
        islem_kaydet(baglanti, yapan.id, "personel_ekleme", yeni_id)
    return yeni_id


def parola_sifirla(
    baglanti: Baglanti, yapan: Kullanici, hedef_id: int, gecici_parola: str
) -> None:
    with baglanti.transaction():
        eczaci_dogrula(baglanti, yapan)
        if hedef_id == yapan.id:
            raise KullaniciHatasi(
                "Kendi parolanızı \"Parolamı Değiştir\" menüsünden değiştirin."
            )
        parola_kurali_dogrula(gecici_parola)
        if not gecici_parola_yaz(baglanti, hedef_id, gecici_parola):
            raise KullaniciHatasi(_BULUNAMADI_MESAJI)
        islem_kaydet(baglanti, yapan.id, "parola_sifirlama", hedef_id)


def kilit_ac(baglanti: Baglanti, yapan: Kullanici, hedef_id: int) -> None:
    with baglanti.transaction():
        eczaci_dogrula(baglanti, yapan)
        satir = baglanti.execute(
            "UPDATE kullanicilar SET hatali_giris_sayisi = 0, kilit_bitis = NULL "
            "WHERE id = %s AND aktif RETURNING id",
            (hedef_id,),
        ).fetchone()
        if satir is None:
            raise KullaniciHatasi(_BULUNAMADI_MESAJI)
        islem_kaydet(baglanti, yapan.id, "kilit_acma", hedef_id)


def parola_degistir(
    baglanti: Baglanti, kullanici: Kullanici, mevcut_parola: str, yeni_parola: str
) -> None:
    """Kisi kendi parolasini degistirir. Yanlis mevcut parola kilit sayacina isler."""
    parola_kurali_dogrula(yeni_parola)
    if yeni_parola == mevcut_parola:
        raise KullaniciHatasi("Yeni parola mevcut parolayla aynı olamaz.")
    if giris_dogrula(baglanti, kullanici.kullanici_adi, mevcut_parola) is None:
        raise KullaniciHatasi("Mevcut parola hatalı.")

    with baglanti.transaction():
        baglanti.execute(
            "UPDATE kullanicilar SET parola_ozeti = %s, parola_degismeli = FALSE "
            "WHERE id = %s",
            (parola_ozetle(yeni_parola), kullanici.id),
        )
        islem_kaydet(baglanti, kullanici.id, "parola_degistirme", kullanici.id)


def pasif_yap(baglanti: Baglanti, yapan: Kullanici, hedef_id: int) -> None:
    """Hesabi kapatir, kaydi silmez. Son aktif eczaci kapatilamaz."""
    with baglanti.transaction():
        # Tum aktif eczacilar kilitlenir: iki eczaci ayni anda birbirini kapatamasin.
        satirlar = baglanti.execute(
            "SELECT id FROM kullanicilar WHERE aktif AND rol = %s ORDER BY id FOR UPDATE",
            (Rol.ECZACI.value,),
        ).fetchall()
        eczacilar = [satir["id"] for satir in satirlar]
        if yapan.id not in eczacilar:
            raise YetkiHatasi("Bu işlem için eczacı yetkisi gerekir.")
        if eczacilar == [hedef_id]:
            raise KullaniciHatasi(
                "Son aktif eczacı pasif yapılamaz. Önce başka bir eczacı hesabı ekleyin."
            )
        satir = baglanti.execute(
            "UPDATE kullanicilar SET aktif = FALSE WHERE id = %s AND aktif RETURNING id",
            (hedef_id,),
        ).fetchone()
        if satir is None:
            raise KullaniciHatasi("Kullanıcı bulunamadı veya zaten pasif.")
        islem_kaydet(baglanti, yapan.id, "pasif_yapma", hedef_id)


def aktif_yap(baglanti: Baglanti, yapan: Kullanici, hedef_id: int) -> None:
    with baglanti.transaction():
        eczaci_dogrula(baglanti, yapan)
        satir = baglanti.execute(
            "UPDATE kullanicilar SET aktif = TRUE, hatali_giris_sayisi = 0, "
            "kilit_bitis = NULL WHERE id = %s AND NOT aktif RETURNING id",
            (hedef_id,),
        ).fetchone()
        if satir is None:
            raise KullaniciHatasi("Kullanıcı bulunamadı veya zaten aktif.")
        islem_kaydet(baglanti, yapan.id, "aktif_yapma", hedef_id)


def kullanicilari_listele(baglanti: Baglanti, yapan: Kullanici) -> list[KullaniciOzeti]:
    with baglanti.transaction():
        eczaci_dogrula(baglanti, yapan)
        satirlar = baglanti.execute(
            "SELECT id, kullanici_adi, ad_soyad, rol, aktif, "
            "COALESCE(kilit_bitis > now(), FALSE) AS kilitli "
            "FROM kullanicilar ORDER BY aktif DESC, ad_soyad, id"
        ).fetchall()
    return [
        KullaniciOzeti(
            id=satir["id"],
            kullanici_adi=satir["kullanici_adi"],
            ad_soyad=satir["ad_soyad"],
            rol=Rol(satir["rol"]),
            aktif=satir["aktif"],
            kilitli=satir["kilitli"],
        )
        for satir in satirlar
    ]
