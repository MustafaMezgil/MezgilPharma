from collections.abc import Callable
from pathlib import Path
from threading import Thread

import psycopg
import pytest

from ayarlar import VeritabaniAyari
from veritabani.baglanti import Baglanti, baglanti_ac
from veritabani.migration import (
    MIGRATIONS_KLASORU,
    MigrationHatasi,
    guncel_surum,
    migrationlari_uygula,
    surum_dogrula,
)

TABLO_A = "CREATE TABLE a (id BIGINT PRIMARY KEY, ad TEXT);\n"
TABLO_B = "CREATE TABLE b (id BIGINT PRIMARY KEY);\n"

Uygula = Callable[[], list[int]]


@pytest.fixture
def klasor(tmp_path: Path) -> Path:
    yol = tmp_path / "migrations"
    yol.mkdir()
    return yol


@pytest.fixture
def yedekler() -> list[int]:
    return []


@pytest.fixture
def uygula(sahip_baglanti: Baglanti, klasor: Path, yedekler: list[int]) -> Uygula:
    def _uygula() -> list[int]:
        return migrationlari_uygula(sahip_baglanti, yedek_al=yedekler.append, klasor=klasor)

    return _uygula


def _yaz(klasor: Path, ad: str, sql: str) -> None:
    (klasor / ad).write_bytes(sql.encode("utf-8"))


def _tablo_var_mi(baglanti: Baglanti, ad: str) -> bool:
    satir = baglanti.execute("SELECT to_regclass(%s) AS tablo", (ad,)).fetchone()
    assert satir is not None
    return satir["tablo"] is not None


def test_002_mevcut_kullanicilari_bozmaz(sahip_baglanti: Baglanti, klasor: Path) -> None:
    """Eski surumden gelen hesap kilitsiz kalir, parola degistirmeye zorlanmaz."""
    (klasor / "001_ilk_sema.sql").write_bytes(
        (MIGRATIONS_KLASORU / "001_ilk_sema.sql").read_bytes()
    )
    migrationlari_uygula(sahip_baglanti, yedek_al=lambda _s: None, klasor=klasor)
    sahip_baglanti.execute(
        "INSERT INTO kullanicilar (kullanici_adi, ad_soyad, parola_ozeti) VALUES (%s, %s, %s)",
        ("eski", "Eski Kişi", "ozet"),
    )
    (klasor / "002_kullanici_guvenligi.sql").write_bytes(
        (MIGRATIONS_KLASORU / "002_kullanici_guvenligi.sql").read_bytes()
    )

    migrationlari_uygula(sahip_baglanti, yedek_al=lambda _s: None, klasor=klasor)

    satir = sahip_baglanti.execute(
        "SELECT hatali_giris_sayisi, kilit_bitis, parola_degismeli, parola_ozeti "
        "FROM kullanicilar"
    ).fetchone()
    assert satir is not None
    assert satir["hatali_giris_sayisi"] == 0
    assert satir["kilit_bitis"] is None
    assert satir["parola_degismeli"] is False
    assert satir["parola_ozeti"] == "ozet"


def test_bos_veritabaninin_surumu_sifirdir(sahip_baglanti: Baglanti) -> None:
    assert guncel_surum(sahip_baglanti) == 0


def test_migrationlar_sirayla_uygulanir(
    sahip_baglanti: Baglanti, klasor: Path, uygula: Uygula
) -> None:
    _yaz(klasor, "002_iki.sql", "ALTER TABLE a ADD COLUMN not_alani TEXT;\n")
    _yaz(klasor, "001_bir.sql", TABLO_A)

    assert uygula() == [1, 2]
    assert guncel_surum(sahip_baglanti) == 2


def test_ikinci_calistirmada_tekrar_uygulanmaz(
    sahip_baglanti: Baglanti, klasor: Path, uygula: Uygula
) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    uygula()

    assert uygula() == []
    assert guncel_surum(sahip_baglanti) == 1


def test_hatali_migration_tamamen_geri_alinir(
    sahip_baglanti: Baglanti, klasor: Path, uygula: Uygula
) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    _yaz(klasor, "002_hatali.sql", TABLO_B + "BU GECERLI SQL DEGIL;\n")

    with pytest.raises(MigrationHatasi, match="002_hatali.sql"):
        uygula()

    assert guncel_surum(sahip_baglanti) == 1
    assert _tablo_var_mi(sahip_baglanti, "a")
    assert not _tablo_var_mi(sahip_baglanti, "b")


def test_hatadan_sonra_duzeltilen_migration_uygulanir(klasor: Path, uygula: Uygula) -> None:
    _yaz(klasor, "001_bir.sql", "BU GECERLI SQL DEGIL;\n")
    with pytest.raises(MigrationHatasi):
        uygula()

    _yaz(klasor, "001_bir.sql", TABLO_A)

    assert uygula() == [1]


def test_uygulanmis_dosya_degistirilirse_durur(klasor: Path, uygula: Uygula) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    uygula()

    _yaz(klasor, "001_bir.sql", TABLO_B)

    with pytest.raises(MigrationHatasi, match="değiştirilmiş"):
        uygula()


def test_yalnizca_satir_sonu_farki_degisiklik_sayilmaz(klasor: Path, uygula: Uygula) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    uygula()

    _yaz(klasor, "001_bir.sql", TABLO_A.replace("\n", "\r\n"))

    assert uygula() == []


def test_veritabani_programdan_yeniyse_durur(klasor: Path, uygula: Uygula) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    _yaz(klasor, "002_iki.sql", TABLO_B)
    uygula()

    (klasor / "002_iki.sql").unlink()

    with pytest.raises(MigrationHatasi, match="daha yeni"):
        uygula()


def test_numara_atlanirsa_hata_verir(
    sahip_baglanti: Baglanti, klasor: Path, uygula: Uygula
) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    _yaz(klasor, "003_uc.sql", TABLO_B)

    with pytest.raises(MigrationHatasi, match="sıra"):
        uygula()
    assert guncel_surum(sahip_baglanti) == 0


def test_ayni_numara_iki_kez_kullanilirsa_hata_verir(klasor: Path, uygula: Uygula) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    _yaz(klasor, "001_iki.sql", TABLO_B)

    with pytest.raises(MigrationHatasi, match="sıra"):
        uygula()


def test_gecersiz_dosya_adi_hata_verir(klasor: Path, uygula: Uygula) -> None:
    _yaz(klasor, "yeni_tablo.sql", TABLO_A)

    with pytest.raises(MigrationHatasi, match="yeni_tablo.sql"):
        uygula()


def test_bos_veritabaninda_yedek_alinmaz(
    klasor: Path, uygula: Uygula, yedekler: list[int]
) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    uygula()
    assert yedekler == []


def test_yeni_migrationdan_once_yedek_alinir(
    sahip_baglanti: Baglanti, klasor: Path, uygula: Uygula, yedekler: list[int]
) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    uygula()

    _yaz(klasor, "002_iki.sql", TABLO_B)
    uygula()

    assert yedekler == [1]
    assert _tablo_var_mi(sahip_baglanti, "b")


def test_degisiklik_yoksa_yedek_alinmaz(
    klasor: Path, uygula: Uygula, yedekler: list[int]
) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    uygula()
    uygula()
    assert yedekler == []


def test_yedek_alinamazsa_migration_uygulanmaz(
    sahip_baglanti: Baglanti, klasor: Path, uygula: Uygula
) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    uygula()
    _yaz(klasor, "002_iki.sql", TABLO_B)

    def _basarisiz_yedek(_surum: int) -> None:
        raise MigrationHatasi("Yedek alınamadı.")

    with pytest.raises(MigrationHatasi, match="Yedek"):
        migrationlari_uygula(sahip_baglanti, yedek_al=_basarisiz_yedek, klasor=klasor)

    assert guncel_surum(sahip_baglanti) == 1
    assert not _tablo_var_mi(sahip_baglanti, "b")


def test_iki_bilgisayar_ayni_anda_guncellese_de_bir_kez_uygulanir(
    temiz_veritabani: None, sahip_ayari: VeritabaniAyari, klasor: Path
) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    _yaz(klasor, "002_iki.sql", TABLO_B + "SELECT pg_sleep(0.2);\n")
    hatalar: list[Exception] = []
    sonuclar: list[list[int]] = []

    def _calistir() -> None:
        try:
            with baglanti_ac(sahip_ayari) as baglanti:
                sonuclar.append(
                    migrationlari_uygula(baglanti, yedek_al=lambda _s: None, klasor=klasor)
                )
        except Exception as hata:  # Thread icindeki hata testte gorunmelidir.
            hatalar.append(hata)

    kollar = [Thread(target=_calistir) for _ in range(2)]
    for kol in kollar:
        kol.start()
    for kol in kollar:
        kol.join()

    assert hatalar == []
    assert sorted(sonuclar) == [[], [1, 2]]


def test_surum_dogrula_guncel_veritabaninda_surumu_dondurur(
    klasor: Path, uygula: Uygula, sahip_baglanti: Baglanti
) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    uygula()
    assert surum_dogrula(sahip_baglanti, klasor=klasor) == 1


def test_surum_dogrula_hic_guncellenmemis_veritabaninda_uyarir(
    klasor: Path, sahip_baglanti: Baglanti
) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    with pytest.raises(MigrationHatasi, match="ana makinede"):
        surum_dogrula(sahip_baglanti, klasor=klasor)


def test_surum_dogrula_geride_kalan_veritabaninda_uyarir(
    klasor: Path, uygula: Uygula, sahip_baglanti: Baglanti
) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    uygula()
    _yaz(klasor, "002_iki.sql", TABLO_B)

    with pytest.raises(MigrationHatasi, match="ana makinede"):
        surum_dogrula(sahip_baglanti, klasor=klasor)
    assert not _tablo_var_mi(sahip_baglanti, "b")


def test_surum_dogrula_veritabani_yeniyse_uyarir(
    klasor: Path, uygula: Uygula, sahip_baglanti: Baglanti
) -> None:
    _yaz(klasor, "001_bir.sql", TABLO_A)
    _yaz(klasor, "002_iki.sql", TABLO_B)
    uygula()
    (klasor / "002_iki.sql").unlink()

    with pytest.raises(MigrationHatasi, match="daha yeni"):
        surum_dogrula(sahip_baglanti, klasor=klasor)


def test_erisim_kaydi_olmayan_kullaniciya_baglanamaz(uygulama_baglanti: Baglanti) -> None:
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        uygulama_baglanti.execute(
            "INSERT INTO erisim_log (kullanici_id, islem, kayit_turu, kayit_id) "
            "VALUES (%s, %s, %s, %s)",
            (999, "goruntuleme", "hasta", 1),
        )
