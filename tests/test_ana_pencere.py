import pytest
from PyQt6.QtWidgets import QLabel

from arayuz.ana_pencere import AnaPencere
from ayarlar import Ortam


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
    pencere = AnaPencere(ortam, veritabani_surumu=1)
    assert _etiket_metni(pencere, "ortam_etiketi") == beklenen


@pytest.mark.usefixtures("qt_uygulamasi")
def test_pencere_veritabani_surumunu_gosterir() -> None:
    pencere = AnaPencere(Ortam.TEST, veritabani_surumu=7)
    assert _etiket_metni(pencere, "surum_etiketi") == "Veritabanı sürümü: 7"
