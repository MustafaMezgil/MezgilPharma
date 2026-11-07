import pytest
from PyQt6.QtWidgets import QLabel

from arayuz.ana_pencere import AnaPencere
from arayuz.kullanici_penceresi import KullanicilarPenceresi, ParolaDegistirPenceresi
from arayuz.urun_penceresi import UrunlerPenceresi
from ayarlar import Ortam, VeritabaniAyari
from moduller.kullanici.servis import Kullanici, Rol

KULLANICI = Kullanici(id=1, kullanici_adi="test", ad_soyad="Test Kişi", rol=Rol.ECZACI)
AYAR = VeritabaniAyari("localhost", 1, "eczane_pytest", "sahte", "sahte")


def _listeyi_okuma(_pencere: object) -> None:
    """Menu testleri pencerenin acildigini sinar; veritabanina baglanmaya gerek yoktur."""


def _etiket_metni(pencere: AnaPencere, ad: str) -> str:
    etiket = pencere.findChild(QLabel, ad)
    assert etiket is not None
    return etiket.text()


@pytest.mark.usefixtures("qt_uygulamasi")
@pytest.mark.parametrize(
    ("ortam", "beklenen"),
    [(Ortam.TEST, "Ortam: TEST"), (Ortam.CANLI, "Ortam: CANLI")],
)
def test_pencere_ortami_gosterir(ortam: Ortam, beklenen: str) -> None:
    pencere = AnaPencere(ortam, 1, KULLANICI, AYAR)
    assert _etiket_metni(pencere, "ortam_etiketi") == beklenen


@pytest.mark.usefixtures("qt_uygulamasi")
def test_pencere_veritabani_surumunu_gosterir() -> None:
    pencere = AnaPencere(Ortam.TEST, 7, KULLANICI, AYAR)
    assert _etiket_metni(pencere, "surum_etiketi") == "Veritabanı sürümü: 7"


@pytest.mark.usefixtures("qt_uygulamasi")
@pytest.mark.parametrize(
    ("rol", "beklenen"),
    [
        (Rol.ECZACI, "Kullanıcı: Test Kişi (Eczacı)"),
        (Rol.PERSONEL, "Kullanıcı: Test Kişi (Personel)"),
    ],
)
def test_pencere_giris_yapan_kullaniciyi_gosterir(rol: Rol, beklenen: str) -> None:
    kullanici = Kullanici(id=1, kullanici_adi="test", ad_soyad="Test Kişi", rol=rol)
    pencere = AnaPencere(Ortam.TEST, 1, kullanici, AYAR)
    assert _etiket_metni(pencere, "kullanici_etiketi") == beklenen


@pytest.mark.usefixtures("qt_uygulamasi")
def test_eczaci_kullanicilar_menusunu_gorur() -> None:
    pencere = AnaPencere(Ortam.TEST, 1, KULLANICI, AYAR)
    assert pencere.kullanicilar_eylemi is not None


@pytest.mark.usefixtures("qt_uygulamasi")
def test_personel_kullanicilar_menusunu_goremez_ama_parolasini_degistirebilir() -> None:
    kullanici = Kullanici(id=2, kullanici_adi="p", ad_soyad="Personel", rol=Rol.PERSONEL)
    pencere = AnaPencere(Ortam.TEST, 1, kullanici, AYAR)
    assert pencere.kullanicilar_eylemi is None
    assert pencere.parola_degistir_eylemi.isEnabled()


@pytest.mark.usefixtures("qt_uygulamasi")
@pytest.mark.parametrize("rol", [Rol.ECZACI, Rol.PERSONEL])
def test_urunler_menusu_her_iki_role_de_acilir(
    monkeypatch: pytest.MonkeyPatch, rol: Rol
) -> None:
    acilan: list[int] = []

    def _exec(_pencere: UrunlerPenceresi) -> int:
        acilan.append(1)
        return 0

    monkeypatch.setattr(UrunlerPenceresi, "exec", _exec)
    monkeypatch.setattr(UrunlerPenceresi, "_yenile", _listeyi_okuma)
    kullanici = Kullanici(id=1, kullanici_adi="test", ad_soyad="Test Kişi", rol=rol)
    pencere = AnaPencere(Ortam.TEST, 1, kullanici, AYAR)

    pencere.urunler_eylemi.trigger()

    assert acilan == [1]


@pytest.mark.usefixtures("qt_uygulamasi")
def test_parola_degistir_menusu_pencereyi_acar(monkeypatch: pytest.MonkeyPatch) -> None:
    acilan: list[str] = []

    def _exec(pencere: ParolaDegistirPenceresi) -> int:
        acilan.append(pencere.kullanici.kullanici_adi)
        return 0

    monkeypatch.setattr(ParolaDegistirPenceresi, "exec", _exec)
    pencere = AnaPencere(Ortam.TEST, 1, KULLANICI, AYAR)

    pencere.parola_degistir_eylemi.trigger()

    assert acilan == ["test"]


@pytest.mark.usefixtures("qt_uygulamasi")
def test_kullanicilar_menusu_pencereyi_acar(monkeypatch: pytest.MonkeyPatch) -> None:
    acilan: list[int] = []

    def _exec(_pencere: KullanicilarPenceresi) -> int:
        acilan.append(1)
        return 0

    monkeypatch.setattr(KullanicilarPenceresi, "exec", _exec)
    monkeypatch.setattr(KullanicilarPenceresi, "_yenile", _listeyi_okuma)
    pencere = AnaPencere(Ortam.TEST, 1, KULLANICI, AYAR)
    assert pencere.kullanicilar_eylemi is not None

    pencere.kullanicilar_eylemi.trigger()

    assert acilan == [1]
