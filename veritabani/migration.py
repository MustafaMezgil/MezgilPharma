"""Veritabani semasini numarali SQL dosyalariyla sirayla gunceller."""

import hashlib
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import psycopg

from veritabani.baglanti import Baglanti

MIGRATIONS_KLASORU = Path(__file__).resolve().parent / "migrations"

_DOSYA_ADI_KURALI = re.compile(r"(\d{3})_[a-z0-9_]+\.sql")
# Ayni anda tek guncelleme calissin diye kullanilan kilidin numarasi (rastgele secildi).
_GUNCELLEME_KILIDI = 7203114

_log = logging.getLogger(__name__)


class MigrationHatasi(Exception):
    """Mesaji kullaniciya gosterilebilecek, Turkce bir veritabani guncelleme hatasi."""


@dataclass(frozen=True)
class _Migration:
    surum: int
    dosya_adi: str
    sql: str
    ozet: str


def _uygulanmis_ozetler(baglanti: Baglanti) -> dict[int, str]:
    tablo = baglanti.execute("SELECT to_regclass('schema_surum') AS ad").fetchone()
    if tablo is None or tablo["ad"] is None:
        return {}
    satirlar = baglanti.execute("SELECT surum, ozet FROM schema_surum ORDER BY surum")
    return {satir["surum"]: satir["ozet"] for satir in satirlar}


def guncel_surum(baglanti: Baglanti) -> int:
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


def surum_dogrula(baglanti: Baglanti, *, klasor: Path = MIGRATIONS_KLASORU) -> int:
    """Veritabani bu programla uyumluysa surumunu dondurur. Hicbir sey degistirmez."""
    migrationlar = _migrationlari_oku(klasor)
    uygulanmis = _uygulanmis_ozetler(baglanti)
    _uygulanmislari_dogrula(uygulanmis, migrationlar)
    surum = max(uygulanmis, default=0)
    if surum < len(migrationlar):
        raise MigrationHatasi(
            "Veritabanı güncellenmemiş. Lütfen ana makinede veritabanı "
            "güncellemesini çalıştırın."
        )
    return surum


def _uygula(baglanti: Baglanti, migration: _Migration) -> None:
    try:
        # Tum dosya tek islemdir: hata olursa hicbir satiri kalici olmaz.
        with baglanti.transaction():
            baglanti.execute(migration.sql.encode("utf-8"))
            baglanti.execute(
                "INSERT INTO schema_surum (surum, dosya_adi, ozet) VALUES (%s, %s, %s)",
                (migration.surum, migration.dosya_adi, migration.ozet),
            )
    except psycopg.Error as hata:
        raise MigrationHatasi(
            f"{migration.dosya_adi} uygulanamadı, değişiklikler geri alındı."
        ) from hata
    _log.info("Migration uygulandi: %s", migration.dosya_adi)


def migrationlari_uygula(
    baglanti: Baglanti,
    *,
    yedek_al: Callable[[int], None],
    klasor: Path = MIGRATIONS_KLASORU,
) -> list[int]:
    """Bekleyen migration'lari sirayla uygular ve uygulanan numaralari dondurur.

    Yalnizca sahip hesabiyla calisir. Daha once uygulanmis migration varken yeni
    migration gelirse, once yedek_al mevcut surum numarasiyla cagrilir.
    """
    migrationlar = _migrationlari_oku(klasor)
    baglanti.execute("SELECT pg_advisory_lock(%s)", (_GUNCELLEME_KILIDI,))
    try:
        baglanti.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_surum (
                surum INTEGER PRIMARY KEY,
                dosya_adi TEXT NOT NULL,
                ozet TEXT NOT NULL,
                uygulanma_tarihi TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        uygulanmis = _uygulanmis_ozetler(baglanti)
        _uygulanmislari_dogrula(uygulanmis, migrationlar)

        son_surum = max(uygulanmis, default=0)
        bekleyenler = [m for m in migrationlar if m.surum > son_surum]
        if bekleyenler and uygulanmis:
            yedek_al(son_surum)

        for migration in bekleyenler:
            _uygula(baglanti, migration)
        return [migration.surum for migration in bekleyenler]
    finally:
        baglanti.execute("SELECT pg_advisory_unlock(%s)", (_GUNCELLEME_KILIDI,))
