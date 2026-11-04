from pathlib import Path

import pytest

from ayarlar import Ortam, ayarlari_yukle


def _env_yaz(klasor: Path, icerik: str, kodlama: str = "utf-8") -> Path:
    dosya = klasor / ".env"
    dosya.write_text(icerik, encoding=kodlama)
    return dosya


def test_env_dosyasi_yoksa_ortam_test_olur(tmp_path: Path) -> None:
    assert ayarlari_yukle(tmp_path / "olmayan.env").ortam is Ortam.TEST


def test_tam_olarak_canli_yazilirsa_ortam_canli_olur(tmp_path: Path) -> None:
    dosya = _env_yaz(tmp_path, "ECZANE_ORTAM=CANLI\n")
    assert ayarlari_yukle(dosya).ortam is Ortam.CANLI


@pytest.mark.parametrize("deger", ["", "canli", "Canli", "CANLİ", "PROD", "TEST", "CANLI2"])
def test_baska_her_deger_test_ortamidir(tmp_path: Path, deger: str) -> None:
    dosya = _env_yaz(tmp_path, f"ECZANE_ORTAM={deger}\n")
    assert ayarlari_yukle(dosya).ortam is Ortam.TEST


def test_ayar_satiri_yoksa_ortam_test_olur(tmp_path: Path) -> None:
    dosya = _env_yaz(tmp_path, "BASKA_AYAR=CANLI\n")
    assert ayarlari_yukle(dosya).ortam is Ortam.TEST


def test_bilgisayar_ortam_degiskeni_canliya_cikaramaz(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ECZANE_ORTAM", "CANLI")
    assert ayarlari_yukle(tmp_path / "olmayan.env").ortam is Ortam.TEST


def test_bom_ile_kaydedilmis_env_dosyasi_okunur(tmp_path: Path) -> None:
    dosya = _env_yaz(tmp_path, "ECZANE_ORTAM=CANLI\n", kodlama="utf-8-sig")
    assert ayarlari_yukle(dosya).ortam is Ortam.CANLI


def test_test_ve_canli_ayri_veritabani_kullanir(tmp_path: Path) -> None:
    test_ayari = ayarlari_yukle(tmp_path / "olmayan.env")
    canli_ayari = ayarlari_yukle(_env_yaz(tmp_path, "ECZANE_ORTAM=CANLI\n"))
    assert test_ayari.veritabani_yolu.name == "eczane_test.db"
    assert canli_ayari.veritabani_yolu.name == "eczane.db"
