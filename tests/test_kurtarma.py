"""Tek eczaci parolasini unutunca ana makinede calisan kurtarma komutu."""

from pathlib import Path

import pytest

from ayarlar import Ayarlar, Ortam, VeritabaniAyari
from moduller.kullanici import kurtarma
from moduller.kullanici.kurtarma import eczaci_parolasi_kurtar
from moduller.kullanici.servis import (
    AZAMI_HATALI_GIRIS,
    HesapKilitliHatasi,
    KullaniciHatasi,
    Rol,
    giris_dogrula,
    kullanici_olustur,
)
from veritabani.baglanti import Baglanti, baglanti_ac

PAROLA = "Deneme-Parola1"
GECICI = "Gecici-Parola1"


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


@pytest.fixture
def eczaci_baglanti(uygulama_baglanti: Baglanti) -> Baglanti:
    kullanici_olustur(uygulama_baglanti, "eczaci1", "Birinci Eczacı", PAROLA, Rol.ECZACI)
    return uygulama_baglanti


def _yanitlari_ayarla(
    monkeypatch: pytest.MonkeyPatch, kullanici_adi: str, parolalar: list[str]
) -> None:
    kalan = iter(parolalar)

    def _getpass(_soru: str = "") -> str:
        return next(kalan)

    def _input(_soru: str = "") -> str:
        return kullanici_adi

    monkeypatch.setattr(kurtarma, "getpass", _getpass)
    monkeypatch.setattr("builtins.input", _input)


def test_kurtarma_gecici_parola_belirler_ve_degistirmeyi_zorunlu_kilar(
    eczaci_baglanti: Baglanti, sahip_ayari: VeritabaniAyari
) -> None:
    with baglanti_ac(sahip_ayari) as sahip:
        eczaci_parolasi_kurtar(sahip, "eczaci1", GECICI)

    assert giris_dogrula(eczaci_baglanti, "eczaci1", PAROLA) is None
    giren = giris_dogrula(eczaci_baglanti, "eczaci1", GECICI)
    assert giren is not None
    assert giren.parola_degismeli


def test_kurtarma_kilidi_kaldirir(
    eczaci_baglanti: Baglanti, sahip_ayari: VeritabaniAyari
) -> None:
    for _ in range(AZAMI_HATALI_GIRIS - 1):
        giris_dogrula(eczaci_baglanti, "eczaci1", "yanlis-parola")
    with pytest.raises(HesapKilitliHatasi):
        giris_dogrula(eczaci_baglanti, "eczaci1", "yanlis-parola")

    with baglanti_ac(sahip_ayari) as sahip:
        eczaci_parolasi_kurtar(sahip, "eczaci1", GECICI)

    assert giris_dogrula(eczaci_baglanti, "eczaci1", GECICI) is not None


def test_kurtarma_erisim_kaydina_yazilir(
    eczaci_baglanti: Baglanti, sahip_ayari: VeritabaniAyari
) -> None:
    with baglanti_ac(sahip_ayari) as sahip:
        eczaci_parolasi_kurtar(sahip, "eczaci1", GECICI)

    satir = eczaci_baglanti.execute(
        "SELECT islem, kayit_turu FROM erisim_log"
    ).fetchone()
    assert satir is not None
    assert satir["islem"] == "parola_kurtarma_ana_makine"
    assert satir["kayit_turu"] == "kullanici"


def test_kurtarma_personel_hesabina_uygulanmaz(
    eczaci_baglanti: Baglanti, sahip_ayari: VeritabaniAyari
) -> None:
    kullanici_olustur(eczaci_baglanti, "personel1", "Personel", PAROLA, Rol.PERSONEL)
    with baglanti_ac(sahip_ayari) as sahip:
        with pytest.raises(KullaniciHatasi, match="eczacı"):
            eczaci_parolasi_kurtar(sahip, "personel1", GECICI)
    assert giris_dogrula(eczaci_baglanti, "personel1", PAROLA) is not None


def test_kurtarma_kisa_parolayi_kabul_etmez(
    eczaci_baglanti: Baglanti, sahip_ayari: VeritabaniAyari
) -> None:
    with baglanti_ac(sahip_ayari) as sahip:
        with pytest.raises(KullaniciHatasi, match="en az 8"):
            eczaci_parolasi_kurtar(sahip, "eczaci1", "kisa")
    assert giris_dogrula(eczaci_baglanti, "eczaci1", PAROLA) is not None


@pytest.mark.usefixtures("temiz_gunluk")
def test_komut_kasa_bilgisayarinda_calismaz(
    uygulama_ayari: VeritabaniAyari,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        kurtarma, "ayarlari_yukle", lambda: _ayarlar(uygulama_ayari, None, tmp_path)
    )

    assert kurtarma.calistir() == 1
    assert "ana makinede" in capsys.readouterr().out


@pytest.mark.usefixtures("temiz_gunluk")
def test_komut_parolayi_degistirir_parolayi_ekrana_ve_loga_yazmaz(
    eczaci_baglanti: Baglanti,
    uygulama_ayari: VeritabaniAyari,
    sahip_ayari: VeritabaniAyari,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ayarlar = _ayarlar(uygulama_ayari, sahip_ayari, tmp_path)
    monkeypatch.setattr(kurtarma, "ayarlari_yukle", lambda: ayarlar)
    _yanitlari_ayarla(monkeypatch, "eczaci1", [GECICI, GECICI])

    assert kurtarma.calistir() == 0

    assert giris_dogrula(eczaci_baglanti, "eczaci1", GECICI) is not None
    assert GECICI not in capsys.readouterr().out
    assert GECICI not in (ayarlar.log_klasoru / "eczane.log").read_text(encoding="utf-8")


@pytest.mark.usefixtures("temiz_gunluk")
def test_komutta_parolalar_uyusmazsa_degisiklik_yapilmaz(
    eczaci_baglanti: Baglanti,
    uygulama_ayari: VeritabaniAyari,
    sahip_ayari: VeritabaniAyari,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ayarlar = _ayarlar(uygulama_ayari, sahip_ayari, tmp_path)
    monkeypatch.setattr(kurtarma, "ayarlari_yukle", lambda: ayarlar)
    _yanitlari_ayarla(monkeypatch, "eczaci1", [GECICI, "Baska-Parola1"])

    assert kurtarma.calistir() == 1

    assert "aynı değil" in capsys.readouterr().out
    assert giris_dogrula(eczaci_baglanti, "eczaci1", PAROLA) is not None


@pytest.mark.usefixtures("temiz_gunluk", "eczaci_baglanti")
def test_komutta_olmayan_kullanici_turkce_hata_verir(
    uygulama_ayari: VeritabaniAyari,
    sahip_ayari: VeritabaniAyari,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ayarlar = _ayarlar(uygulama_ayari, sahip_ayari, tmp_path)
    monkeypatch.setattr(kurtarma, "ayarlari_yukle", lambda: ayarlar)
    _yanitlari_ayarla(monkeypatch, "olmayan", [GECICI, GECICI])

    assert kurtarma.calistir() == 1
    assert "HATA" in capsys.readouterr().out
