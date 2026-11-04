"""Programin ayarlari: ortam secimi (TEST/CANLI), veritabani hesaplari, dosya konumlari."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from dotenv import dotenv_values

PROJE_KOKU = Path(__file__).resolve().parent

_ZORUNLU_AYARLAR = (
    "ECZANE_DB_SUNUCU",
    "ECZANE_DB_PORT",
    "ECZANE_DB_KULLANICI",
    "ECZANE_DB_PAROLA",
)


class AyarHatasi(Exception):
    """Mesaji kullaniciya gosterilebilecek, Turkce bir ayar hatasi. Deger icermez."""


class Ortam(Enum):
    TEST = "TEST"
    CANLI = "CANLI"


@dataclass(frozen=True)
class VeritabaniAyari:
    sunucu: str
    port: int
    veritabani: str
    kullanici: str
    parola: str = field(repr=False)


@dataclass(frozen=True)
class Ayarlar:
    ortam: Ortam
    veritabani: VeritabaniAyari
    # Tablo yapisini degistirebilen hesap; yalnizca ana makinede tanimlidir.
    sahip: VeritabaniAyari | None
    yedek_klasoru: Path
    log_klasoru: Path


def ayarlari_yukle(env_dosyasi: Path = PROJE_KOKU / ".env") -> Ayarlar:
    """Ayarlari okur. Canli ortam yalnizca .env icindeki tam "CANLI" degeriyle acilir."""
    # utf-8-sig: Windows araclarinin dosya basina ekledigi BOM isaretini yok sayar.
    degerler = dotenv_values(env_dosyasi, encoding="utf-8-sig")

    eksikler = [ad for ad in _ZORUNLU_AYARLAR if not degerler.get(ad)]
    if eksikler:
        raise AyarHatasi(
            ".env dosyasında ayarlar eksik: " + ", ".join(eksikler)
        )
    try:
        port = int(degerler["ECZANE_DB_PORT"] or "")
    except ValueError as hata:
        raise AyarHatasi("ECZANE_DB_PORT bir sayı olmalıdır.") from hata

    ortam = Ortam.CANLI if degerler.get("ECZANE_ORTAM") == "CANLI" else Ortam.TEST
    veritabani_adi = "eczane" if ortam is Ortam.CANLI else "eczane_test"
    sunucu = degerler["ECZANE_DB_SUNUCU"] or ""

    sahip: VeritabaniAyari | None = None
    sahip_kullanici = degerler.get("ECZANE_DB_SAHIP_KULLANICI")
    sahip_parola = degerler.get("ECZANE_DB_SAHIP_PAROLA")
    if sahip_kullanici and sahip_parola:
        sahip = VeritabaniAyari(sunucu, port, veritabani_adi, sahip_kullanici, sahip_parola)

    return Ayarlar(
        ortam=ortam,
        veritabani=VeritabaniAyari(
            sunucu,
            port,
            veritabani_adi,
            degerler["ECZANE_DB_KULLANICI"] or "",
            degerler["ECZANE_DB_PAROLA"] or "",
        ),
        sahip=sahip,
        yedek_klasoru=PROJE_KOKU / "yedekler",
        log_klasoru=PROJE_KOKU / "logs",
    )
