import sqlite3
from pathlib import Path

import pytest

from veritabani.baglanti import baglanti_ac
from veritabani.migration import (
    MIGRATIONS_KLASORU,
    MigrationHatasi,
    guncel_surum,
    migrationlari_uygula,
)

TABLO_A = "CREATE TABLE a (id INTEGER PRIMARY KEY, ad TEXT);\n"
TABLO_B = "CREATE TABLE b (id INTEGER PRIMARY KEY);\n"


@pytest.fixture
def klasor(tmp_path: Path) -> Path:
    yol = tmp_path / "migrations"
    yol.mkdir()
    return yol


@pytest.fixture
def yedekler(tmp_path: Path) -> Path:
    return tmp_path / "yedekler"


@pytest.fixture
def baglanti(tmp_path: Path) -> sqlite3.Connection:
    return baglanti_ac(tmp_path / "deneme.db")


def _yaz(klasor: Path, ad: str, sql: str) -> None:
    (klasor / ad).write_bytes(sql.encode("utf-8"))


def _tablo_var_mi(baglanti: sqlite3.Connection, ad: str) -> bool:
    satir = baglanti.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (ad,)
    ).fetchone()
    return satir is not None


def test_bos_veritabaninin_surumu_sifirdir(baglanti: sqlite3.Connection) -> None:
    assert guncel_surum(baglanti) == 0


def test_migrationlar_sirayla_uygulanir(
    baglanti: sqlite3.Connection, klasor: Path, yedekler: Path
) -> None:
    _yaz(klasor, "002_iki.sql", "ALTER TABLE a ADD COLUMN not_alani TEXT;\n")
    _yaz(klasor, "001_bir.sql", TABLO_A)

    uygulananlar = migrationlari_uygula(baglanti, klasor=klasor, yedek_klasoru=yedekler)

    assert uygulananlar == [1, 2]
    assert guncel_surum(baglanti) == 2


def test_ikinci_calistirmada_tekrar_uygulanmaz(
    baglanti: sqlite3.Connection, klasor: Path, yedekler: Path
) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    migrationlari_uygula(baglanti, klasor=klasor, yedek_klasoru=yedekler)

    assert migrationlari_uygula(baglanti, klasor=klasor, yedek_klasoru=yedekler) == []
    assert guncel_surum(baglanti) == 1


def test_hatali_migration_tamamen_geri_alinir(
    baglanti: sqlite3.Connection, klasor: Path, yedekler: Path
) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    _yaz(klasor, "002_hatali.sql", TABLO_B + "BU GECERLI SQL DEGIL;\n")

    with pytest.raises(MigrationHatasi, match="002_hatali.sql"):
        migrationlari_uygula(baglanti, klasor=klasor, yedek_klasoru=yedekler)

    assert guncel_surum(baglanti) == 1
    assert _tablo_var_mi(baglanti, "a")
    assert not _tablo_var_mi(baglanti, "b")
    assert not baglanti.in_transaction


def test_hatadan_sonra_duzeltilen_migration_uygulanir(
    baglanti: sqlite3.Connection, klasor: Path, yedekler: Path
) -> None:
    _yaz(klasor, "001_bir.sql", "BU GECERLI SQL DEGIL;\n")
    with pytest.raises(MigrationHatasi):
        migrationlari_uygula(baglanti, klasor=klasor, yedek_klasoru=yedekler)

    _yaz(klasor, "001_bir.sql", TABLO_A)

    assert migrationlari_uygula(baglanti, klasor=klasor, yedek_klasoru=yedekler) == [1]


def test_uygulanmis_dosya_degistirilirse_program_durur(
    baglanti: sqlite3.Connection, klasor: Path, yedekler: Path
) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    migrationlari_uygula(baglanti, klasor=klasor, yedek_klasoru=yedekler)

    _yaz(klasor, "001_bir.sql", TABLO_B)

    with pytest.raises(MigrationHatasi, match="değiştirilmiş"):
        migrationlari_uygula(baglanti, klasor=klasor, yedek_klasoru=yedekler)


def test_yalnizca_satir_sonu_farki_degisiklik_sayilmaz(
    baglanti: sqlite3.Connection, klasor: Path, yedekler: Path
) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    migrationlari_uygula(baglanti, klasor=klasor, yedek_klasoru=yedekler)

    _yaz(klasor, "001_bir.sql", TABLO_A.replace("\n", "\r\n"))

    assert migrationlari_uygula(baglanti, klasor=klasor, yedek_klasoru=yedekler) == []


def test_veritabani_programdan_yeniyse_program_durur(
    baglanti: sqlite3.Connection, klasor: Path, yedekler: Path
) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    _yaz(klasor, "002_iki.sql", TABLO_B)
    migrationlari_uygula(baglanti, klasor=klasor, yedek_klasoru=yedekler)

    (klasor / "002_iki.sql").unlink()

    with pytest.raises(MigrationHatasi, match="daha yeni"):
        migrationlari_uygula(baglanti, klasor=klasor, yedek_klasoru=yedekler)


def test_numara_atlanirsa_hata_verir(
    baglanti: sqlite3.Connection, klasor: Path, yedekler: Path
) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    _yaz(klasor, "003_uc.sql", TABLO_B)

    with pytest.raises(MigrationHatasi, match="sıra"):
        migrationlari_uygula(baglanti, klasor=klasor, yedek_klasoru=yedekler)
    assert guncel_surum(baglanti) == 0


def test_ayni_numara_iki_kez_kullanilirsa_hata_verir(
    baglanti: sqlite3.Connection, klasor: Path, yedekler: Path
) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    _yaz(klasor, "001_iki.sql", TABLO_B)

    with pytest.raises(MigrationHatasi, match="sıra"):
        migrationlari_uygula(baglanti, klasor=klasor, yedek_klasoru=yedekler)


def test_gecersiz_dosya_adi_hata_verir(
    baglanti: sqlite3.Connection, klasor: Path, yedekler: Path
) -> None:
    _yaz(klasor, "yeni_tablo.sql", TABLO_A)

    with pytest.raises(MigrationHatasi, match="yeni_tablo.sql"):
        migrationlari_uygula(baglanti, klasor=klasor, yedek_klasoru=yedekler)


def test_yeni_migrationdan_once_yedek_alinir(
    baglanti: sqlite3.Connection, klasor: Path, yedekler: Path
) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    migrationlari_uygula(baglanti, klasor=klasor, yedek_klasoru=yedekler)
    baglanti.execute("INSERT INTO a (ad) VALUES (?)", ("yedekte olmali",))
    baglanti.commit()

    _yaz(klasor, "002_iki.sql", "DELETE FROM a;\n")
    migrationlari_uygula(baglanti, klasor=klasor, yedek_klasoru=yedekler)

    dosyalar = list(yedekler.glob("*.db"))
    assert len(dosyalar) == 1
    yedek = sqlite3.connect(dosyalar[0])
    assert yedek.execute("SELECT ad FROM a").fetchall() == [("yedekte olmali",)]
    yedek.close()
    assert baglanti.execute("SELECT COUNT(*) FROM a").fetchone()[0] == 0


def test_bos_veritabani_ve_degisiklik_yoksa_yedek_alinmaz(
    baglanti: sqlite3.Connection, klasor: Path, yedekler: Path
) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    migrationlari_uygula(baglanti, klasor=klasor, yedek_klasoru=yedekler)
    migrationlari_uygula(baglanti, klasor=klasor, yedek_klasoru=yedekler)

    assert not yedekler.exists() or not list(yedekler.iterdir())


def test_gercek_ilk_sema_uygulanir(baglanti: sqlite3.Connection, yedekler: Path) -> None:
    migrationlari_uygula(baglanti, klasor=MIGRATIONS_KLASORU, yedek_klasoru=yedekler)

    assert _tablo_var_mi(baglanti, "kullanicilar")
    assert _tablo_var_mi(baglanti, "erisim_log")


def test_erisim_kaydi_olmayan_kullaniciya_baglanamaz(
    baglanti: sqlite3.Connection, yedekler: Path
) -> None:
    migrationlari_uygula(baglanti, klasor=MIGRATIONS_KLASORU, yedek_klasoru=yedekler)

    with pytest.raises(sqlite3.IntegrityError):
        baglanti.execute(
            "INSERT INTO erisim_log (kullanici_id, tarih, islem, kayit_turu, kayit_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (999, "2026-01-01T10:00:00", "goruntuleme", "hasta", 1),
        )
