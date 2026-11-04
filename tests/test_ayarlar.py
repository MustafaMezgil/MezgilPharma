from pathlib import Path

import pytest

from ayarlar import AyarHatasi, Ortam, ayarlari_yukle

ZORUNLU = (
    "ECZANE_DB_SUNUCU=sahte-sunucu\n"
    "ECZANE_DB_PORT=5433\n"
    "ECZANE_DB_KULLANICI=sahte_uygulama\n"
    "ECZANE_DB_PAROLA=sahte-parola-1\n"
)
SAHIP = "ECZANE_DB_SAHIP_KULLANICI=sahte_sahip\nECZANE_DB_SAHIP_PAROLA=sahte-parola-2\n"


def _env_yaz(klasor: Path, icerik: str, kodlama: str = "utf-8") -> Path:
    dosya = klasor / ".env"
    dosya.write_text(icerik, encoding=kodlama)
    return dosya


def test_tam_olarak_canli_yazilirsa_ortam_canli_olur(tmp_path: Path) -> None:
    dosya = _env_yaz(tmp_path, "ECZANE_ORTAM=CANLI\n" + ZORUNLU)
    assert ayarlari_yukle(dosya).ortam is Ortam.CANLI


@pytest.mark.parametrize("deger", ["", "canli", "Canli", "CANLİ", "PROD", "TEST", "CANLI2"])
def test_baska_her_deger_test_ortamidir(tmp_path: Path, deger: str) -> None:
    dosya = _env_yaz(tmp_path, f"ECZANE_ORTAM={deger}\n" + ZORUNLU)
    assert ayarlari_yukle(dosya).ortam is Ortam.TEST


def test_ortam_satiri_yoksa_test_olur(tmp_path: Path) -> None:
    assert ayarlari_yukle(_env_yaz(tmp_path, ZORUNLU)).ortam is Ortam.TEST


def test_bilgisayar_ortam_degiskeni_canliya_cikaramaz(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ECZANE_ORTAM", "CANLI")
    assert ayarlari_yukle(_env_yaz(tmp_path, ZORUNLU)).ortam is Ortam.TEST


def test_bom_ile_kaydedilmis_env_dosyasi_okunur(tmp_path: Path) -> None:
    dosya = _env_yaz(tmp_path, "ECZANE_ORTAM=CANLI\n" + ZORUNLU, kodlama="utf-8-sig")
    assert ayarlari_yukle(dosya).ortam is Ortam.CANLI


def test_test_ve_canli_ayri_veritabani_kullanir(tmp_path: Path) -> None:
    test_ayari = ayarlari_yukle(_env_yaz(tmp_path, ZORUNLU))
    canli_ayari = ayarlari_yukle(_env_yaz(tmp_path, "ECZANE_ORTAM=CANLI\n" + ZORUNLU))
    assert test_ayari.veritabani.veritabani == "eczane_test"
    assert canli_ayari.veritabani.veritabani == "eczane"


def test_baglanti_bilgileri_okunur(tmp_path: Path) -> None:
    ayar = ayarlari_yukle(_env_yaz(tmp_path, ZORUNLU)).veritabani
    assert ayar.sunucu == "sahte-sunucu"
    assert ayar.port == 5433
    assert ayar.kullanici == "sahte_uygulama"
    assert ayar.parola == "sahte-parola-1"


def test_sahip_hesabi_yoksa_kasa_bilgisayaridir(tmp_path: Path) -> None:
    assert ayarlari_yukle(_env_yaz(tmp_path, ZORUNLU)).sahip is None


def test_sahip_hesabi_varsa_ayni_veritabanina_baglanir(tmp_path: Path) -> None:
    ayarlar = ayarlari_yukle(_env_yaz(tmp_path, ZORUNLU + SAHIP))
    assert ayarlar.sahip is not None
    assert ayarlar.sahip.kullanici == "sahte_sahip"
    assert ayarlar.sahip.veritabani == ayarlar.veritabani.veritabani


def test_env_dosyasi_yoksa_turkce_hata_verir(tmp_path: Path) -> None:
    with pytest.raises(AyarHatasi, match="eksik"):
        ayarlari_yukle(tmp_path / "olmayan.env")


def test_eksik_ayar_adi_soylenir_ama_degerler_soylenmez(tmp_path: Path) -> None:
    dosya = _env_yaz(tmp_path, ZORUNLU.replace("ECZANE_DB_SUNUCU=sahte-sunucu\n", ""))
    with pytest.raises(AyarHatasi) as hata:
        ayarlari_yukle(dosya)
    assert "ECZANE_DB_SUNUCU" in str(hata.value)
    assert "sahte-parola-1" not in str(hata.value)


def test_gecersiz_port_turkce_hata_verir(tmp_path: Path) -> None:
    dosya = _env_yaz(tmp_path, ZORUNLU.replace("5433", "bes"))
    with pytest.raises(AyarHatasi, match="ECZANE_DB_PORT"):
        ayarlari_yukle(dosya)


def test_parola_nesne_yazdirilinca_gorunmez(tmp_path: Path) -> None:
    ayarlar = ayarlari_yukle(_env_yaz(tmp_path, ZORUNLU + SAHIP))
    assert "sahte-parola" not in repr(ayarlar)
