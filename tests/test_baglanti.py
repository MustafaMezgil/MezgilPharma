from dataclasses import replace

import psycopg
import pytest

from ayarlar import VeritabaniAyari
from veritabani.baglanti import baglanti_ac, ssl_modu


def test_satirlara_sutun_adiyla_erisilir(uygulama_ayari: VeritabaniAyari) -> None:
    with baglanti_ac(uygulama_ayari) as baglanti:
        satir = baglanti.execute("SELECT 5 AS sayi").fetchone()
    assert satir is not None
    assert satir["sayi"] == 5


def test_tek_komutlar_acik_islem_birakmaz(uygulama_ayari: VeritabaniAyari) -> None:
    with baglanti_ac(uygulama_ayari) as baglanti:
        baglanti.execute("SELECT 1")
        assert baglanti.info.transaction_status == psycopg.pq.TransactionStatus.IDLE


@pytest.mark.yavas
def test_sunucuya_ulasilamazsa_hata_verir(uygulama_ayari: VeritabaniAyari) -> None:
    with pytest.raises(psycopg.OperationalError):
        baglanti_ac(replace(uygulama_ayari, port=1))


@pytest.mark.parametrize("sunucu", ["localhost", "127.0.0.1", "::1"])
def test_ayni_bilgisayarda_ssl_zorunlu_degildir(sunucu: str) -> None:
    assert ssl_modu(sunucu) == "prefer"


@pytest.mark.parametrize("sunucu", ["192.168.1.10", "ana-makine"])
def test_ag_uzerinden_ssl_zorunludur(sunucu: str) -> None:
    assert ssl_modu(sunucu) == "require"
