"""Veritabanini gunceller. YALNIZCA ana makinede calistirilir.

Calistirmak icin: .venv\\Scripts\\python -m veritabani.guncelle
"""

import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import LiteralString

import psycopg
from psycopg import sql

from ayarlar import AyarHatasi, Ayarlar, VeritabaniAyari, ayarlari_yukle
from gunluk import gunlugu_baslat
from veritabani.baglanti import Baglanti, baglanti_ac, ssl_modu
from veritabani.migration import MigrationHatasi, migrationlari_uygula

_POSTGRESQL_KLASORU = Path(r"C:\Program Files\PostgreSQL")

_log = logging.getLogger(__name__)


def pg_arac_yolu(ad: str) -> str:
    """pg_dump gibi PostgreSQL araclarini bulur; varsa en yeni surumu secer."""
    bulunan = shutil.which(ad)
    if bulunan is not None:
        return bulunan
    surumler = [k for k in _POSTGRESQL_KLASORU.glob("*") if k.name.isdigit()]
    for surum in sorted(surumler, key=lambda k: int(k.name), reverse=True):
        aday = surum / "bin" / f"{ad}.exe"
        if aday.exists():
            return str(aday)
    raise MigrationHatasi(f"PostgreSQL aracı bulunamadı: {ad}. Yedek alınamadı.")


def yedek_al(ayar: VeritabaniAyari, klasor: Path, surum: int) -> None:
    """Veritabaninin tam yedegini alir. Basarisiz olursa guncelleme baslamaz."""
    klasor.mkdir(parents=True, exist_ok=True)
    zaman = datetime.now().strftime("%Y%m%dT%H%M%S")
    hedef = klasor / f"{ayar.veritabani}_surum{surum:03d}_{zaman}.dump"
    # Parola komut satirinda gorunmesin diye ortam degiskeniyle verilir.
    ortam = {
        **os.environ,
        "PGPASSWORD": ayar.parola,
        "PGSSLMODE": ssl_modu(ayar.sunucu),
    }
    sonuc = subprocess.run(
        [
            pg_arac_yolu("pg_dump"),
            "--format=custom",
            "--no-password",
            f"--file={hedef}",
            f"--host={ayar.sunucu}",
            f"--port={ayar.port}",
            f"--username={ayar.kullanici}",
            f"--dbname={ayar.veritabani}",
        ],
        env=ortam,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if sonuc.returncode != 0:
        hedef.unlink(missing_ok=True)
        _log.error("pg_dump basarisiz: %s", sonuc.stderr)
        raise MigrationHatasi("Yedek alınamadı, güncelleme yapılmadı.")
    _log.info("Guncelleme oncesi yedek alindi: %s", hedef.name)


def yetkileri_ver(baglanti: Baglanti, kullanici: str) -> None:
    """Uygulama hesabina yalnizca gereken yetkileri verir. Tekrar calistirilabilir."""
    hesap = sql.Identifier(kullanici)
    komutlar: tuple[LiteralString, ...] = (
        "GRANT USAGE ON SCHEMA public TO {}",
        "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {}",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}",
        "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}",
        # Surum kayitlarina yalnizca ana makinedeki guncelleme yazabilir.
        "REVOKE INSERT, UPDATE, DELETE ON schema_surum FROM {}",
        # Erisim kayitlari denetim icindir: eklenir ve okunur, degistirilemez.
        "REVOKE UPDATE, DELETE ON erisim_log FROM {}",
    )
    with baglanti.transaction():
        for komut in komutlar:
            baglanti.execute(sql.SQL(komut).format(hesap))


def guncelle(ayarlar: Ayarlar) -> list[int]:
    """Bekleyen migration'lari uygular ve uygulama hesabinin yetkilerini yeniler."""
    sahip = ayarlar.sahip
    if sahip is None:
        raise MigrationHatasi(
            "Veritabanı güncellemesi yalnızca ana makinede yapılabilir: "
            "bu bilgisayarda sahip hesabı tanımlı değil."
        )

    def _yedek(surum: int) -> None:
        yedek_al(sahip, ayarlar.yedek_klasoru, surum)

    with baglanti_ac(sahip) as baglanti:
        uygulananlar = migrationlari_uygula(baglanti, yedek_al=_yedek)
        yetkileri_ver(baglanti, ayarlar.veritabani.kullanici)
    return uygulananlar


def calistir() -> int:
    try:
        ayarlar = ayarlari_yukle()
        gunlugu_baslat(ayarlar.log_klasoru)
        print(f"Ortam: {ayarlar.ortam.value}, veritabanı: {ayarlar.veritabani.veritabani}")
        uygulananlar = guncelle(ayarlar)
    except (AyarHatasi, MigrationHatasi) as hata:
        _log.exception("Veritabani guncellenemedi")
        print(f"HATA: {hata}")
        return 1
    except (psycopg.Error, OSError):
        _log.exception("Veritabani guncellenirken baglanti hatasi")
        print("HATA: Veritabanına ulaşılamadı. Ayrıntı log dosyasında.")
        return 1

    if uygulananlar:
        print(f"Güncelleme tamamlandı. Uygulanan sürümler: {uygulananlar}")
    else:
        print("Veritabanı zaten güncel.")
    return 0


if __name__ == "__main__":
    sys.exit(calistir())
