import pytest
from PyQt6.QtWidgets import QLabel

from arayuz.ana_pencere import AnaPencere
from ayarlar import Ortam
from moduller.kullanici.servis import Kullanici, Rol

KULLANICI = Kullanici(id=1, kullanici_adi="test", ad_soyad="Test Kişi", rol=Rol.ECZACI)


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
    pencere = AnaPencere(ortam, 1, KULLANICI)
    assert _etiket_metni(pencere, "ortam_etiketi") == beklenen


@pytest.mark.usefixtures("qt_uygulamasi")
def test_pencere_veritabani_surumunu_gosterir() -> None:
    pencere = AnaPencere(Ortam.TEST, 7, KULLANICI)
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
    pencere = AnaPencere(Ortam.TEST, 1, kullanici)
    assert _etiket_metni(pencere, "kullanici_etiketi") == beklenen
