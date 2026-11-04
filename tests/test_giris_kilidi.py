"""Hatali giris siniri: 5 yanlis denemede hesap 15 dakika kilitlenir."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest

from ayarlar import VeritabaniAyari
from moduller.kullanici import servis
from moduller.kullanici.parola import parola_dogru_mu
from moduller.kullanici.servis import (
    AZAMI_HATALI_GIRIS,
    KILIT_SURESI_DAKIKA,
    HesapKilitliHatasi,
    Rol,
    giris_dogrula,
    kullanici_olustur,
)
from veritabani.baglanti import Baglanti, baglanti_ac

ADI = "test_personel"
PAROLA = "Deneme-Parola1"
YANLIS = "yanlis-parola"


@pytest.fixture
def baglanti(uygulama_baglanti: Baglanti) -> Baglanti:
    kullanici_olustur(uygulama_baglanti, ADI, "Test Kişi", PAROLA, Rol.PERSONEL)
    return uygulama_baglanti


def _yanlis_dene(baglanti: Baglanti, adet: int) -> None:
    for _ in range(adet):
        assert giris_dogrula(baglanti, ADI, YANLIS) is None


def _kilitle(baglanti: Baglanti) -> None:
    _yanlis_dene(baglanti, AZAMI_HATALI_GIRIS - 1)
    with pytest.raises(HesapKilitliHatasi):
        giris_dogrula(baglanti, ADI, YANLIS)


def test_sinir_5_deneme_15_dakikadir() -> None:
    assert AZAMI_HATALI_GIRIS == 5
    assert KILIT_SURESI_DAKIKA == 15


def test_besinci_yanlis_denemeye_kadar_hesap_kilitlenmez(baglanti: Baglanti) -> None:
    _yanlis_dene(baglanti, AZAMI_HATALI_GIRIS - 1)
    assert giris_dogrula(baglanti, ADI, PAROLA) is not None


def test_besinci_yanlis_denemede_hesap_kilitlenir(baglanti: Baglanti) -> None:
    _yanlis_dene(baglanti, AZAMI_HATALI_GIRIS - 1)
    with pytest.raises(HesapKilitliHatasi, match="15 dakika"):
        giris_dogrula(baglanti, ADI, YANLIS)


def test_kilit_suresi_sunucu_saatiyle_15_dakikadir(baglanti: Baglanti) -> None:
    _kilitle(baglanti)
    satir = baglanti.execute(
        "SELECT kilit_bitis - now() AS kalan FROM kullanicilar WHERE kullanici_adi = %s",
        (ADI,),
    ).fetchone()
    assert satir is not None
    assert timedelta(minutes=14) < satir["kalan"] <= timedelta(minutes=15)


def test_kilitliyken_dogru_parola_da_kabul_edilmez(baglanti: Baglanti) -> None:
    _kilitle(baglanti)
    with pytest.raises(HesapKilitliHatasi, match="tekrar deneyin"):
        giris_dogrula(baglanti, ADI, PAROLA)


def test_basarili_giris_sayaci_sifirlar(baglanti: Baglanti) -> None:
    _yanlis_dene(baglanti, AZAMI_HATALI_GIRIS - 1)
    assert giris_dogrula(baglanti, ADI, PAROLA) is not None
    _yanlis_dene(baglanti, AZAMI_HATALI_GIRIS - 1)
    assert giris_dogrula(baglanti, ADI, PAROLA) is not None


def test_sure_dolunca_dogru_parola_ile_girilir(baglanti: Baglanti) -> None:
    _kilitle(baglanti)
    baglanti.execute("UPDATE kullanicilar SET kilit_bitis = now() - interval '1 second'")
    assert giris_dogrula(baglanti, ADI, PAROLA) is not None


def test_sure_dolunca_sayac_bastan_baslar(baglanti: Baglanti) -> None:
    _kilitle(baglanti)
    baglanti.execute("UPDATE kullanicilar SET kilit_bitis = now() - interval '1 second'")
    _yanlis_dene(baglanti, AZAMI_HATALI_GIRIS - 1)
    with pytest.raises(HesapKilitliHatasi):
        giris_dogrula(baglanti, ADI, YANLIS)


def test_kilit_baska_kasadan_da_gecerlidir(
    baglanti: Baglanti, uygulama_ayari: VeritabaniAyari
) -> None:
    _kilitle(baglanti)
    with baglanti_ac(uygulama_ayari) as baska_kasa:
        with pytest.raises(HesapKilitliHatasi):
            giris_dogrula(baska_kasa, ADI, PAROLA)


def test_sayac_kasalar_arasinda_birikir(
    baglanti: Baglanti, uygulama_ayari: VeritabaniAyari
) -> None:
    _yanlis_dene(baglanti, AZAMI_HATALI_GIRIS - 1)
    with baglanti_ac(uygulama_ayari) as baska_kasa:
        with pytest.raises(HesapKilitliHatasi):
            giris_dogrula(baska_kasa, ADI, YANLIS)


def test_ayni_anda_yapilan_denemelerde_siniri_asan_parola_denenemez(
    baglanti: Baglanti, uygulama_ayari: VeritabaniAyari, monkeypatch: pytest.MonkeyPatch
) -> None:
    denenen_parolalar: list[str] = []

    def _sayarak_dogrula(parola: str, ozet: str) -> bool:
        denenen_parolalar.append(parola)
        return parola_dogru_mu(parola, ozet)

    monkeypatch.setattr(servis, "parola_dogru_mu", _sayarak_dogrula)
    adet = AZAMI_HATALI_GIRIS * 3
    baslangic = Barrier(adet)

    def _dene(_sira: int) -> bool:
        with baglanti_ac(uygulama_ayari) as kasa:
            baslangic.wait(timeout=30)
            try:
                giris_dogrula(kasa, ADI, YANLIS)
            except HesapKilitliHatasi:
                return True
            return False

    with ThreadPoolExecutor(max_workers=adet) as havuz:
        sonuclar = list(havuz.map(_dene, range(adet)))

    assert len(denenen_parolalar) == AZAMI_HATALI_GIRIS
    assert sonuclar.count(False) == AZAMI_HATALI_GIRIS - 1
    with pytest.raises(HesapKilitliHatasi):
        giris_dogrula(baglanti, ADI, PAROLA)


def test_bir_hesabin_kilidi_digerini_etkilemez(baglanti: Baglanti) -> None:
    kullanici_olustur(baglanti, "diger", "Diğer Kişi", PAROLA, Rol.ECZACI)
    _kilitle(baglanti)
    assert giris_dogrula(baglanti, "diger", PAROLA) is not None


def test_olmayan_kullanicida_kilit_hatasi_olusmaz(baglanti: Baglanti) -> None:
    for _ in range(AZAMI_HATALI_GIRIS + 1):
        assert giris_dogrula(baglanti, "olmayan", YANLIS) is None
