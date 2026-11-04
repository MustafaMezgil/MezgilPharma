from dataclasses import replace
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QDialog, QMessageBox, QWidget

import main
from arayuz.giris_penceresi import GirisPenceresi, IlkKullaniciPenceresi
from ayarlar import AyarHatasi, Ayarlar, Ortam, VeritabaniAyari
from moduller.kullanici.servis import Rol, kullanici_olustur
from veritabani.baglanti import Baglanti

PAROLA = "Deneme-Parola1"


@pytest.fixture
def ayarlar(uygulama_ayari: VeritabaniAyari, tmp_path: Path) -> Ayarlar:
    return Ayarlar(
        ortam=Ortam.TEST,
        veritabani=uygulama_ayari,
        sahip=None,
        yedek_klasoru=tmp_path / "yedekler",
        log_klasoru=tmp_path / "logs",
    )


@pytest.fixture
def mesajlar(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    toplanan: list[str] = []

    def _kaydet(_ust: QWidget | None, _baslik: str, metin: str) -> None:
        toplanan.append(metin)

    monkeypatch.setattr(QMessageBox, "critical", _kaydet)
    return toplanan


@pytest.fixture
def kayitli_kullanici(uygulama_baglanti: Baglanti) -> None:
    kullanici_olustur(uygulama_baglanti, "test_eczaci", "Test Kişi", PAROLA, Rol.ECZACI)


@pytest.mark.usefixtures("hazir_veritabani")
def test_guncel_veritabaninda_surum_dondurulur(ayarlar: Ayarlar) -> None:
    assert main.veritabanini_dogrula(ayarlar) >= 1


@pytest.mark.usefixtures("qt_uygulamasi", "temiz_gunluk", "temiz_veritabani")
def test_guncellenmemis_veritabaninda_turkce_mesaj_gosterilir(
    ayarlar: Ayarlar, mesajlar: list[str]
) -> None:
    assert main.baslat(ayarlar) == 1
    assert len(mesajlar) == 1
    assert "ana makinede" in mesajlar[0]


@pytest.mark.usefixtures("qt_uygulamasi", "temiz_gunluk")
def test_ana_makineye_ulasilamazsa_turkce_mesaj_gosterilir_parola_loga_yazilmaz(
    ayarlar: Ayarlar, mesajlar: list[str]
) -> None:
    ulasilamaz = replace(
        ayarlar,
        veritabani=replace(ayarlar.veritabani, port=1, parola="sahte-gizli-parola"),
    )

    assert main.baslat(ulasilamaz) == 1

    assert len(mesajlar) == 1
    assert "Ana makine" in mesajlar[0]
    assert "connection" not in mesajlar[0]
    log = (ulasilamaz.log_klasoru / "eczane.log").read_text(encoding="utf-8")
    assert "Veritabanina ulasilamadi" in log
    assert "sahte-gizli-parola" not in log


@pytest.mark.usefixtures("qt_uygulamasi", "hazir_veritabani")
def test_kullanici_yoksa_ilk_kullanici_sorulur_ve_iptal_edilebilir(
    ayarlar: Ayarlar, monkeypatch: pytest.MonkeyPatch
) -> None:
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


@pytest.mark.usefixtures("qt_uygulamasi", "kayitli_kullanici")
def test_kullanici_varsa_dogrudan_giris_ekrani_acilir(
    ayarlar: Ayarlar, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _giris(pencere: GirisPenceresi) -> int:
        pencere.kullanici_adi_alani.setText("test_eczaci")
        pencere.parola_alani.setText(PAROLA)
        pencere.giris_dugmesi.click()
        return pencere.result()

    monkeypatch.setattr(GirisPenceresi, "exec", _giris)

    kullanici = main.kullanici_girisi(ayarlar)

    assert kullanici is not None
    assert kullanici.kullanici_adi == "test_eczaci"


@pytest.mark.usefixtures("qt_uygulamasi", "temiz_gunluk", "kayitli_kullanici")
def test_giris_iptal_edilirse_ana_pencere_acilmadan_cikilir(
    ayarlar: Ayarlar, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _iptal(_pencere: GirisPenceresi) -> int:
        return QDialog.DialogCode.Rejected.value

    def _ana_pencere_acilmamali(*_args: object) -> None:
        pytest.fail("Giris yapilmadan ana pencere acildi")

    monkeypatch.setattr(GirisPenceresi, "exec", _iptal)
    monkeypatch.setattr(main, "AnaPencere", _ana_pencere_acilmamali)

    assert main.baslat(ayarlar) == 0


@pytest.mark.usefixtures("qt_uygulamasi")
def test_ayar_eksikse_turkce_mesaj_gosterilir(
    monkeypatch: pytest.MonkeyPatch, mesajlar: list[str]
) -> None:
    def _hatali_yukleme() -> Ayarlar:
        raise AyarHatasi("Ayarlar eksik: ECZANE_DB_SUNUCU")

    monkeypatch.setattr(main, "ayarlari_yukle", _hatali_yukleme)

    assert main.calistir() == 1
    assert mesajlar == ["Ayarlar eksik: ECZANE_DB_SUNUCU"]
