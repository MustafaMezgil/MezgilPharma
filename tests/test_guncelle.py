import subprocess
from dataclasses import replace
from pathlib import Path

import psycopg
import pytest

from ayarlar import Ayarlar, Ortam, VeritabaniAyari
from veritabani.baglanti import Baglanti, baglanti_ac
from veritabani.guncelle import guncelle, pg_arac_yolu, yedek_al
from veritabani.migration import MigrationHatasi, guncel_surum


def _ayarlar(
    uygulama: VeritabaniAyari, sahip: VeritabaniAyari | None, klasor: Path
) -> Ayarlar:
    return Ayarlar(
        ortam=Ortam.TEST,
        veritabani=uygulama,
        sahip=sahip,
        yedek_klasoru=klasor / "yedekler",
        log_klasoru=klasor / "logs",
    )


def _erisim_kaydi_ekle(baglanti: Baglanti) -> None:
    baglanti.execute(
        "INSERT INTO kullanicilar (kullanici_adi, ad_soyad, parola_ozeti) "
        "VALUES (%s, %s, %s)",
        ("test", "Test Kişi", "ozet"),
    )
    baglanti.execute(
        "INSERT INTO erisim_log (kullanici_id, islem, kayit_turu, kayit_id) "
        "SELECT id, %s, %s, %s FROM kullanicilar",
        ("goruntuleme", "hasta", 1),
    )


@pytest.mark.usefixtures("temiz_veritabani")
def test_guncelle_bos_veritabanini_son_surume_getirir(
    uygulama_ayari: VeritabaniAyari, sahip_ayari: VeritabaniAyari, tmp_path: Path
) -> None:
    uygulananlar = guncelle(_ayarlar(uygulama_ayari, sahip_ayari, tmp_path))

    assert uygulananlar
    with baglanti_ac(uygulama_ayari) as baglanti:
        assert guncel_surum(baglanti) == uygulananlar[-1]


def test_kasa_bilgisayarinda_guncelleme_yapilamaz(
    uygulama_ayari: VeritabaniAyari, tmp_path: Path
) -> None:
    with pytest.raises(MigrationHatasi, match="ana makinede"):
        guncelle(_ayarlar(uygulama_ayari, None, tmp_path))


def test_uygulama_hesabi_tablo_olusturamaz(uygulama_baglanti: Baglanti) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        uygulama_baglanti.execute("CREATE TABLE izinsiz (id BIGINT)")


def test_uygulama_hesabi_tablo_silemez(uygulama_baglanti: Baglanti) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        uygulama_baglanti.execute("DROP TABLE kullanicilar")


def test_uygulama_hesabi_erisim_kaydi_ekleyip_okuyabilir(uygulama_baglanti: Baglanti) -> None:
    _erisim_kaydi_ekle(uygulama_baglanti)

    satir = uygulama_baglanti.execute("SELECT COUNT(*) AS adet FROM erisim_log").fetchone()

    assert satir is not None
    assert satir["adet"] == 1


@pytest.mark.parametrize(
    "komut",
    [
        "UPDATE erisim_log SET islem = 'degisti'",
        "DELETE FROM erisim_log",
        "TRUNCATE erisim_log",
    ],
)
def test_erisim_kaydi_degistirilemez_ve_silinemez(
    uygulama_baglanti: Baglanti, komut: str
) -> None:
    _erisim_kaydi_ekle(uygulama_baglanti)

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        uygulama_baglanti.execute(komut.encode("utf-8"))


@pytest.mark.parametrize(
    "komut",
    [
        "UPDATE fiyat_gecmisi SET stok_miktari = 0",
        "DELETE FROM fiyat_gecmisi",
        "TRUNCATE fiyat_gecmisi",
        "DELETE FROM urunler",
        "DELETE FROM stok_partileri",
    ],
)
def test_fiyat_gecmisi_degistirilemez_urun_ve_parti_silinemez(
    uygulama_baglanti: Baglanti, komut: str
) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        uygulama_baglanti.execute(komut.encode("utf-8"))


def test_uygulama_hesabi_surum_kaydini_degistiremez(uygulama_baglanti: Baglanti) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        uygulama_baglanti.execute("DELETE FROM schema_surum")


def test_yedek_gercek_arac_ile_alinir_ve_veriyi_icerir(
    uygulama_baglanti: Baglanti, sahip_ayari: VeritabaniAyari, yedek_klasoru: Path
) -> None:
    _erisim_kaydi_ekle(uygulama_baglanti)

    yedek_al(sahip_ayari, yedek_klasoru, 1)

    dosyalar = list(yedek_klasoru.glob("*.dump"))
    assert len(dosyalar) == 1
    assert "surum001" in dosyalar[0].name
    icindekiler = subprocess.run(
        [pg_arac_yolu("pg_restore"), "--list", str(dosyalar[0])],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    ).stdout
    assert "kullanicilar" in icindekiler
    assert "erisim_log" in icindekiler


@pytest.mark.yavas
def test_yedek_alinamazsa_turkce_hata_verir_ve_dosya_birakmaz(
    sahip_ayari: VeritabaniAyari, yedek_klasoru: Path
) -> None:
    with pytest.raises(MigrationHatasi, match="Yedek alınamadı"):
        yedek_al(replace(sahip_ayari, port=1), yedek_klasoru, 1)

    assert list(yedek_klasoru.glob("*.dump")) == []
