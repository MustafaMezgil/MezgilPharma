"""Kullanici olusturma ve giris dogrulama."""

from dataclasses import dataclass
from enum import Enum

import psycopg

from moduller.kullanici.parola import parola_dogru_mu, parola_ozetle
from veritabani.baglanti import Baglanti

ASGARI_PAROLA_UZUNLUGU = 8


class KullaniciHatasi(Exception):
    """Mesaji kullaniciya gosterilebilecek, Turkce bir kullanici hatasi."""


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


def aktif_kullanici_var_mi(baglanti: Baglanti) -> bool:
    satir = baglanti.execute("SELECT 1 FROM kullanicilar WHERE aktif LIMIT 1").fetchone()
    return satir is not None


def kullanici_olustur(
    baglanti: Baglanti,
    kullanici_adi: str,
    ad_soyad: str,
    parola: str,
    rol: Rol,
) -> None:
    kullanici_adi = kullanici_adi.strip()
    ad_soyad = ad_soyad.strip()
    if not kullanici_adi:
        raise KullaniciHatasi("Kullanıcı adı boş olamaz.")
    if not ad_soyad:
        raise KullaniciHatasi("Ad soyad boş olamaz.")
    if len(parola) < ASGARI_PAROLA_UZUNLUGU:
        raise KullaniciHatasi(
            f"Parola en az {ASGARI_PAROLA_UZUNLUGU} karakter olmalıdır."
        )

    try:
        baglanti.execute(
            "INSERT INTO kullanicilar (kullanici_adi, ad_soyad, parola_ozeti, rol) "
            "VALUES (%s, %s, %s, %s)",
            (kullanici_adi, ad_soyad, parola_ozetle(parola), rol.value),
        )
    except psycopg.errors.UniqueViolation as hata:
        raise KullaniciHatasi("Bu kullanıcı adı zaten kullanılıyor.") from hata


def giris_dogrula(
    baglanti: Baglanti, kullanici_adi: str, parola: str
) -> Kullanici | None:
    """Bilgiler dogruysa kullaniciyi, degilse None dondurur."""
    satir = baglanti.execute(
        "SELECT id, kullanici_adi, ad_soyad, rol, parola_ozeti FROM kullanicilar "
        "WHERE kullanici_adi = %s AND aktif",
        (kullanici_adi.strip(),),
    ).fetchone()
    if satir is None or not parola_dogru_mu(parola, satir["parola_ozeti"]):
        return None
    return Kullanici(
        id=satir["id"],
        kullanici_adi=satir["kullanici_adi"],
        ad_soyad=satir["ad_soyad"],
        rol=Rol(satir["rol"]),
    )
