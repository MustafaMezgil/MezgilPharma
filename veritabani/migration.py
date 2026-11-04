"""Veritabani semasini numarali SQL dosyalariyla sirayla gunceller."""

import hashlib
import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

MIGRATIONS_KLASORU = Path(__file__).resolve().parent / "migrations"

_DOSYA_ADI_KURALI = re.compile(r"(\d{3})_[a-z0-9_]+\.sql")

_log = logging.getLogger(__name__)


class MigrationHatasi(Exception):
    """Mesaji kullaniciya gosterilebilecek, Turkce bir veritabani guncelleme hatasi."""


@dataclass(frozen=True)
class _Migration:
    surum: int
    dosya_adi: str
    sql: str
    ozet: str


def _surum_tablosunu_hazirla(baglanti: sqlite3.Connection) -> None:
    baglanti.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_surum (
            surum INTEGER PRIMARY KEY,
            dosya_adi TEXT NOT NULL,
            ozet TEXT NOT NULL,
            uygulanma_tarihi TEXT NOT NULL
        )
        """
    )


def _uygulanmis_ozetler(baglanti: sqlite3.Connection) -> dict[int, str]:
    _surum_tablosunu_hazirla(baglanti)
    satirlar = baglanti.execute("SELECT surum, ozet FROM schema_surum ORDER BY surum")
    return {satir["surum"]: satir["ozet"] for satir in satirlar}


def guncel_surum(baglanti: sqlite3.Connection) -> int:
    """Veritabanina uygulanmis son migration numarasini dondurur (bos ise 0)."""
    return max(_uygulanmis_ozetler(baglanti), default=0)


def _migrationlari_oku(klasor: Path) -> list[_Migration]:
    migrationlar: list[_Migration] = []
    for dosya in sorted(klasor.glob("*.sql"), key=lambda yol: yol.name):
        eslesme = _DOSYA_ADI_KURALI.fullmatch(dosya.name)
        if eslesme is None:
            raise MigrationHatasi(
                f"Geçersiz migration dosya adı: {dosya.name}. "
                "Beklenen biçim: 001_kisa_aciklama.sql"
            )
        # Git satir sonlarini degistirebilir; ozet bundan etkilenmemelidir.
        sql = dosya.read_bytes().decode("utf-8").replace("\r\n", "\n")
        migrationlar.append(
            _Migration(
                surum=int(eslesme.group(1)),
                dosya_adi=dosya.name,
                sql=sql,
                ozet=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
            )
        )

    surumler = [migration.surum for migration in migrationlar]
    if surumler != list(range(1, len(surumler) + 1)):
        raise MigrationHatasi(
            "Migration dosyalarının numaraları sıra dışı: "
            "1'den başlamalı, atlanmamalı ve tekrar etmemelidir."
        )
    return migrationlar


def _uygulanmislari_dogrula(
    uygulanmis: dict[int, str], migrationlar: list[_Migration]
) -> None:
    dosyadaki_ozetler = {migration.surum: migration for migration in migrationlar}
    for surum, ozet in uygulanmis.items():
        migration = dosyadaki_ozetler.get(surum)
        if migration is None:
            raise MigrationHatasi(
                "Veritabanı bu program sürümünden daha yeni. "
                "Lütfen programın güncel sürümünü kullanın."
            )
        if migration.ozet != ozet:
            raise MigrationHatasi(
                f"Daha önce uygulanmış {migration.dosya_adi} dosyası değiştirilmiş. "
                "Değişiklik için yeni numaralı bir migration oluşturulmalıdır."
            )


def _yedek_al(baglanti: sqlite3.Connection, klasor: Path, surum: int) -> None:
    klasor.mkdir(parents=True, exist_ok=True)
    zaman = datetime.now().strftime("%Y%m%dT%H%M%S")
    hedef_yolu = klasor / f"yedek_surum{surum:03d}_{zaman}.db"
    hedef = sqlite3.connect(hedef_yolu)
    try:
        baglanti.backup(hedef)
    finally:
        hedef.close()
    _log.info("Migration oncesi yedek alindi: %s", hedef_yolu.name)


def _uygula(baglanti: sqlite3.Connection, migration: _Migration) -> None:
    try:
        # BEGIN ile tum dosya tek islem olur: hata olursa hicbir satiri kalici olmaz.
        baglanti.executescript(f"BEGIN;\n{migration.sql}")
        baglanti.execute(
            "INSERT INTO schema_surum (surum, dosya_adi, ozet, uygulanma_tarihi) "
            "VALUES (?, ?, ?, ?)",
            (
                migration.surum,
                migration.dosya_adi,
                migration.ozet,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        baglanti.commit()
    except sqlite3.Error as hata:
        baglanti.rollback()
        raise MigrationHatasi(
            f"{migration.dosya_adi} uygulanamadı, değişiklikler geri alındı."
        ) from hata
    _log.info("Migration uygulandi: %s", migration.dosya_adi)


def migrationlari_uygula(
    baglanti: sqlite3.Connection,
    *,
    yedek_klasoru: Path,
    klasor: Path = MIGRATIONS_KLASORU,
) -> list[int]:
    """Bekleyen migration'lari sirayla uygular ve uygulanan numaralari dondurur."""
    migrationlar = _migrationlari_oku(klasor)
    uygulanmis = _uygulanmis_ozetler(baglanti)
    _uygulanmislari_dogrula(uygulanmis, migrationlar)

    son_surum = max(uygulanmis, default=0)
    bekleyenler = [m for m in migrationlar if m.surum > son_surum]
    if bekleyenler and uygulanmis:
        _yedek_al(baglanti, yedek_klasoru, son_surum)

    for migration in bekleyenler:
        _uygula(baglanti, migration)
    return [migration.surum for migration in bekleyenler]
