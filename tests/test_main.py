from pathlib import Path

import pytest
from PyQt6.QtWidgets import QDialog, QMessageBox, QWidget

import main
from arayuz.giris_penceresi import GirisPenceresi, IlkKullaniciPenceresi
from ayarlar import Ayarlar, Ortam
from moduller.kullanici.servis import Rol, kullanici_olustur
from veritabani.baglanti import baglanti_ac
from veritabani.migration import guncel_surum

PAROLA = "Deneme-Parola1"


def _ayarlar(klasor: Path) -> Ayarlar:
    return Ayarlar(
        ortam=Ortam.TEST,
        veritabani_yolu=klasor / "veri" / "eczane_test.db",
        yedek_klasoru=klasor / "yedekler",
        log_klasoru=klasor / "logs",
    )


def _kullanici_ekle(ayarlar: Ayarlar) -> None:
    main.veritabanini_hazirla(ayarlar)
    baglanti = baglanti_ac(ayarlar.veritabani_yolu)
    kullanici_olustur(baglanti, "test_eczaci", "Test Kişi", PAROLA, Rol.ECZACI)
    baglanti.close()


def test_veritabani_son_surume_hazirlanir(tmp_path: Path) -> None:
    ayarlar = _ayarlar(tmp_path)

    surum = main.veritabanini_hazirla(ayarlar)

    assert surum >= 1
    baglanti = baglanti_ac(ayarlar.veritabani_yolu)
    assert guncel_surum(baglanti) == surum
    baglanti.close()


@pytest.mark.usefixtures("qt_uygulamasi", "temiz_gunluk")
def test_bozuk_veritabaninda_turkce_mesaj_gosterilir_ve_acilmaz(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ayarlar = _ayarlar(tmp_path)
    ayarlar.veritabani_yolu.parent.mkdir(parents=True)
    ayarlar.veritabani_yolu.write_bytes(b"bu bir veritabani dosyasi degil" * 100)
    mesajlar: list[str] = []

    def _kaydet(_ust: QWidget | None, _baslik: str, metin: str) -> None:
        mesajlar.append(metin)

    monkeypatch.setattr(QMessageBox, "critical", _kaydet)

    assert main.baslat(ayarlar) == 1
    assert len(mesajlar) == 1
    assert "Veritabanı açılamadı" in mesajlar[0]
    assert "file is not a database" not in mesajlar[0]
    assert "file is not a database" in (ayarlar.log_klasoru / "eczane.log").read_text(
        encoding="utf-8"
    )


@pytest.mark.usefixtures("qt_uygulamasi")
def test_kullanici_yoksa_ilk_kullanici_sorulur_ve_iptal_edilebilir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ayarlar = _ayarlar(tmp_path)
    main.veritabanini_hazirla(ayarlar)
    acilanlar: list[str] = []

    def _ilk(_pencere: IlkKullaniciPenceresi) -> int:
        acilanlar.append("ilk")
        return QDialog.DialogCode.Rejected.value

    def _giris(_pencere: GirisPenceresi) -> int:
        acilanlar.append("giris")
        return QDialog.DialogCode.Rejected.value

    monkeypatch.setattr(IlkKullaniciPenceresi, "exec", _ilk)
    monkeypatch.setattr(GirisPenceresi, "exec", _giris)

    assert main.kullanici_girisi(ayarlar) is None
    assert acilanlar == ["ilk"]


@pytest.mark.usefixtures("qt_uygulamasi")
def test_kullanici_varsa_dogrudan_giris_ekrani_acilir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ayarlar = _ayarlar(tmp_path)
    _kullanici_ekle(ayarlar)

    def _giris(pencere: GirisPenceresi) -> int:
        pencere.kullanici_adi_alani.setText("test_eczaci")
        pencere.parola_alani.setText(PAROLA)
        pencere.giris_dugmesi.click()
        return pencere.result()

    monkeypatch.setattr(GirisPenceresi, "exec", _giris)

    kullanici = main.kullanici_girisi(ayarlar)

    assert kullanici is not None
    assert kullanici.kullanici_adi == "test_eczaci"


@pytest.mark.usefixtures("qt_uygulamasi", "temiz_gunluk")
def test_giris_iptal_edilirse_ana_pencere_acilmadan_cikilir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ayarlar = _ayarlar(tmp_path)
    _kullanici_ekle(ayarlar)

    def _iptal(_pencere: GirisPenceresi) -> int:
        return QDialog.DialogCode.Rejected.value

    def _ana_pencere_acilmamali(*_args: object) -> None:
        pytest.fail("Giris yapilmadan ana pencere acildi")

    monkeypatch.setattr(GirisPenceresi, "exec", _iptal)
    monkeypatch.setattr(main, "AnaPencere", _ana_pencere_acilmamali)

    assert main.baslat(ayarlar) == 0
