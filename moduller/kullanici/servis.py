"""Kullanici olusturma ve giris dogrulama."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from moduller.kullanici.parola import parola_dogru_mu, parola_ozetle

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


def aktif_kullanici_var_mi(baglanti: sqlite3.Connection) -> bool:
    satir = baglanti.execute(
        "SELECT 1 FROM kullanicilar WHERE aktif = ? LIMIT 1", (1,)
    ).fetchone()
    return satir is not None


def kullanici_olustur(
    baglanti: sqlite3.Connection,
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
        with baglanti:
            baglanti.execute(
                "INSERT INTO kullanicilar "
                "(kullanici_adi, ad_soyad, parola_ozeti, rol, olusturma_tarihi) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    kullanici_adi,
                    ad_soyad,
                    parola_ozetle(parola),
                    rol.value,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
    except sqlite3.IntegrityError as hata:
        raise KullaniciHatasi("Bu kullanıcı adı zaten kullanılıyor.") from hata


def giris_dogrula(
    baglanti: sqlite3.Connection, kullanici_adi: str, parola: str
) -> Kullanici | None:
    """Bilgiler dogruysa kullaniciyi, degilse None dondurur."""
    satir = baglanti.execute(
        "SELECT id, kullanici_adi, ad_soyad, rol, parola_ozeti FROM kullanicilar "
        "WHERE kullanici_adi = ? AND aktif = ?",
        (kullanici_adi.strip(), 1),
    ).fetchone()
    if satir is None or not parola_dogru_mu(parola, satir["parola_ozeti"]):
        return None
    return Kullanici(
        id=satir["id"],
        kullanici_adi=satir["kullanici_adi"],
        ad_soyad=satir["ad_soyad"],
        rol=Rol(satir["rol"]),
    )
