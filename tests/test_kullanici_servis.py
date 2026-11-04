import psycopg
import pytest

from moduller.kullanici.servis import (
    KullaniciHatasi,
    Rol,
    aktif_kullanici_var_mi,
    giris_dogrula,
    kullanici_olustur,
)
from veritabani.baglanti import Baglanti

PAROLA = "Deneme-Parola1"


def _olustur(baglanti: Baglanti, kullanici_adi: str = "test_eczaci") -> None:
    kullanici_olustur(baglanti, kullanici_adi, "Test Kişi", PAROLA, Rol.ECZACI)


def test_bos_veritabaninda_aktif_kullanici_yoktur(uygulama_baglanti: Baglanti) -> None:
    assert not aktif_kullanici_var_mi(uygulama_baglanti)


def test_olusturulan_kullanici_giris_yapabilir(uygulama_baglanti: Baglanti) -> None:
    _olustur(uygulama_baglanti)

    kullanici = giris_dogrula(uygulama_baglanti, "test_eczaci", PAROLA)

    assert aktif_kullanici_var_mi(uygulama_baglanti)
    assert kullanici is not None
    assert kullanici.ad_soyad == "Test Kişi"
    assert kullanici.rol is Rol.ECZACI


def test_varsayilan_rol_personeldir(uygulama_baglanti: Baglanti) -> None:
    uygulama_baglanti.execute(
        "INSERT INTO kullanicilar (kullanici_adi, ad_soyad, parola_ozeti) VALUES (%s, %s, %s)",
        ("eski_kayit", "Test", "x"),
    )
    satir = uygulama_baglanti.execute(
        "SELECT rol, olusturma_tarihi FROM kullanicilar WHERE kullanici_adi = %s",
        ("eski_kayit",),
    ).fetchone()
    assert satir is not None
    assert satir["rol"] == "personel"
    assert satir["olusturma_tarihi"] is not None


def test_tanimsiz_rol_veritabanina_yazilamaz(uygulama_baglanti: Baglanti) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        uygulama_baglanti.execute(
            "INSERT INTO kullanicilar (kullanici_adi, ad_soyad, parola_ozeti, rol) "
            "VALUES (%s, %s, %s, %s)",
            ("biri", "Test", "x", "yonetici"),
        )


def test_parola_duz_metin_olarak_saklanmaz(uygulama_baglanti: Baglanti) -> None:
    _olustur(uygulama_baglanti)
    satir = uygulama_baglanti.execute("SELECT parola_ozeti FROM kullanicilar").fetchone()
    assert satir is not None
    assert PAROLA not in satir["parola_ozeti"]


def test_yanlis_parola_ile_giris_yapilamaz(uygulama_baglanti: Baglanti) -> None:
    _olustur(uygulama_baglanti)
    assert giris_dogrula(uygulama_baglanti, "test_eczaci", "yanlis-parola") is None


def test_olmayan_kullanici_ile_giris_yapilamaz(uygulama_baglanti: Baglanti) -> None:
    assert giris_dogrula(uygulama_baglanti, "olmayan", PAROLA) is None


def test_pasif_kullanici_giris_yapamaz(uygulama_baglanti: Baglanti) -> None:
    _olustur(uygulama_baglanti)
    uygulama_baglanti.execute("UPDATE kullanicilar SET aktif = FALSE")

    assert giris_dogrula(uygulama_baglanti, "test_eczaci", PAROLA) is None
    assert not aktif_kullanici_var_mi(uygulama_baglanti)


def test_ayni_kullanici_adi_iki_kez_kullanilamaz(uygulama_baglanti: Baglanti) -> None:
    _olustur(uygulama_baglanti)
    with pytest.raises(KullaniciHatasi, match="kullanılıyor"):
        _olustur(uygulama_baglanti)


def test_kullanici_adi_bosluklari_temizlenir(uygulama_baglanti: Baglanti) -> None:
    _olustur(uygulama_baglanti, "  test_eczaci  ")
    assert giris_dogrula(uygulama_baglanti, " test_eczaci ", PAROLA) is not None


@pytest.mark.parametrize(
    ("kullanici_adi", "ad_soyad", "parola", "beklenen"),
    [
        ("   ", "Test Kişi", PAROLA, "Kullanıcı adı"),
        ("test", "   ", PAROLA, "Ad soyad"),
        ("test", "Test Kişi", "kisa", "en az 8"),
    ],
)
def test_eksik_bilgiyle_kullanici_olusturulamaz(
    uygulama_baglanti: Baglanti,
    kullanici_adi: str,
    ad_soyad: str,
    parola: str,
    beklenen: str,
) -> None:
    with pytest.raises(KullaniciHatasi, match=beklenen):
        kullanici_olustur(uygulama_baglanti, kullanici_adi, ad_soyad, parola, Rol.ECZACI)
    assert not aktif_kullanici_var_mi(uygulama_baglanti)
