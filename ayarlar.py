"""Programin ayarlari: ortam secimi (TEST/CANLI) ve dosya konumlari."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from dotenv import dotenv_values

PROJE_KOKU = Path(__file__).resolve().parent


class Ortam(Enum):
    TEST = "TEST"
    CANLI = "CANLI"


@dataclass(frozen=True)
class Ayarlar:
    ortam: Ortam
    veritabani_yolu: Path
    yedek_klasoru: Path
    log_klasoru: Path


def ayarlari_yukle(env_dosyasi: Path = PROJE_KOKU / ".env") -> Ayarlar:
    """Ayarlari okur. Canli ortam yalnizca .env icindeki tam "CANLI" degeriyle acilir."""
    # utf-8-sig: Windows araclarinin dosya basina ekledigi BOM isaretini yok sayar.
    degerler = dotenv_values(env_dosyasi, encoding="utf-8-sig")
    ortam = Ortam.CANLI if degerler.get("ECZANE_ORTAM") == "CANLI" else Ortam.TEST
    veritabani_adi = "eczane.db" if ortam is Ortam.CANLI else "eczane_test.db"
    return Ayarlar(
        ortam=ortam,
        veritabani_yolu=PROJE_KOKU / veritabani_adi,
        yedek_klasoru=PROJE_KOKU / "yedekler",
        log_klasoru=PROJE_KOKU / "logs",
    )
