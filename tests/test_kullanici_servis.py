import sqlite3
from pathlib import Path

import pytest

from moduller.kullanici.servis import (
    KullaniciHatasi,
    Rol,
    aktif_kullanici_var_mi,
    giris_dogrula,
    kullanici_olustur,
)
from veritabani.baglanti import baglanti_ac
from veritabani.migration import migrationlari_uygula

PAROLA = "Deneme-Parola1"


@pytest.fixture
def baglanti(tmp_path: Path) -> sqlite3.Connection:
    baglanti = baglanti_ac(tmp_path / "deneme.db")
    migrationlari_uygula(baglanti, yedek_klasoru=tmp_path / "yedekler")
    return baglanti


def _olustur(baglanti: sqlite3.Connection, kullanici_adi: str = "test_eczaci") -> None:
    kullanici_olustur(baglanti, kullanici_adi, "Test Kişi", PAROLA, Rol.ECZACI)


def test_bos_veritabaninda_aktif_kullanici_yoktur(baglanti: sqlite3.Connection) -> None:
    assert not aktif_kullanici_var_mi(baglanti)


def test_olusturulan_kullanici_giris_yapabilir(baglanti: sqlite3.Connection) -> None:
    _olustur(baglanti)

    kullanici = giris_dogrula(baglanti, "test_eczaci", PAROLA)

    assert aktif_kullanici_var_mi(baglanti)
    assert kullanici is not None
    assert kullanici.ad_soyad == "Test Kişi"
    assert kullanici.rol is Rol.ECZACI


def test_varsayilan_rol_personeldir(baglanti: sqlite3.Connection) -> None:
    baglanti.execute(
        "INSERT INTO kullanicilar (kullanici_adi, ad_soyad, parola_ozeti, olusturma_tarihi) "
        "VALUES (?, ?, ?, ?)",
        ("eski_kayit", "Test", "x", "2026-01-01T10:00:00"),
    )
    satir = baglanti.execute(
        "SELECT rol FROM kullanicilar WHERE kullanici_adi = ?", ("eski_kayit",)
    ).fetchone()
    assert satir["rol"] == "personel"


def test_tanimsiz_rol_veritabanina_yazilamaz(baglanti: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        baglanti.execute(
            "INSERT INTO kullanicilar "
            "(kullanici_adi, ad_soyad, parola_ozeti, olusturma_tarihi, rol) "
            "VALUES (?, ?, ?, ?, ?)",
            ("biri", "Test", "x", "2026-01-01T10:00:00", "yonetici"),
        )


def test_parola_duz_metin_olarak_saklanmaz(baglanti: sqlite3.Connection) -> None:
    _olustur(baglanti)
    satir = baglanti.execute("SELECT parola_ozeti FROM kullanicilar").fetchone()
    assert PAROLA not in satir["parola_ozeti"]


def test_yanlis_parola_ile_giris_yapilamaz(baglanti: sqlite3.Connection) -> None:
    _olustur(baglanti)
    assert giris_dogrula(baglanti, "test_eczaci", "yanlis-parola") is None


def test_olmayan_kullanici_ile_giris_yapilamaz(baglanti: sqlite3.Connection) -> None:
    assert giris_dogrula(baglanti, "olmayan", PAROLA) is None


def test_pasif_kullanici_giris_yapamaz(baglanti: sqlite3.Connection) -> None:
    _olustur(baglanti)
    baglanti.execute("UPDATE kullanicilar SET aktif = ?", (0,))

    assert giris_dogrula(baglanti, "test_eczaci", PAROLA) is None
    assert not aktif_kullanici_var_mi(baglanti)


def test_ayni_kullanici_adi_iki_kez_kullanilamaz(baglanti: sqlite3.Connection) -> None:
    _olustur(baglanti)
    with pytest.raises(KullaniciHatasi, match="kullanılıyor"):
        _olustur(baglanti)


def test_kullanici_adi_bosluklari_temizlenir(baglanti: sqlite3.Connection) -> None:
    _olustur(baglanti, "  test_eczaci  ")
    assert giris_dogrula(baglanti, " test_eczaci ", PAROLA) is not None


@pytest.mark.parametrize(
    ("kullanici_adi", "ad_soyad", "parola", "beklenen"),
    [
        ("   ", "Test Kişi", PAROLA, "Kullanıcı adı"),
        ("test", "   ", PAROLA, "Ad soyad"),
        ("test", "Test Kişi", "kisa", "en az 8"),
    ],
)
def test_eksik_bilgiyle_kullanici_olusturulamaz(
    baglanti: sqlite3.Connection,
    kullanici_adi: str,
    ad_soyad: str,
    parola: str,
    beklenen: str,
) -> None:
    with pytest.raises(KullaniciHatasi, match=beklenen):
        kullanici_olustur(baglanti, kullanici_adi, ad_soyad, parola, Rol.ECZACI)
    assert not aktif_kullanici_var_mi(baglanti)
