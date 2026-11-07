"""Stok girisi, parti takibi, uyarilar, depolar ve miat uyari ayari."""

import threading
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any

import psycopg
import pytest

from ayarlar import VeritabaniAyari
from moduller.hatalar import GorunurHata
from moduller.ilac.servis import (
    ReceteTuru,
    UrunBilgisi,
    UrunFiyati,
    UrunTuru,
    urun_ara,
    urun_ekle,
    urun_guncelle,
    urun_pasif_yap,
)
from moduller.kullanici.servis import (
    Kullanici,
    Rol,
    YetkiHatasi,
    giris_dogrula,
    kullanici_olustur,
    pasif_yap,
)
from moduller.stok.kurallar import ay_ekle
from moduller.stok.servis import (
    VARSAYILAN_MIAT_UYARI_AYI,
    HareketTuru,
    OnayGerekli,
    StokGirisi,
    hareketleri_getir,
    miat_uyari_ayi,
    miat_uyari_ayi_ayarla,
    partileri_getir,
    stok_girisi_yap,
    tedarikci_aktif_yap,
    tedarikci_ekle,
    tedarikci_pasif_yap,
    tedarikcileri_listele,
)
from veritabani.baglanti import Baglanti, baglanti_ac

PAROLA = "Deneme-Parola1"
FIYAT = UrunFiyati(Decimal("125.50"), Decimal("99.90"), Decimal("10"))
BUGUN = date.today()
UZAK_SKT = ay_ekle(BUGUN, 24)


def _giris(baglanti: Baglanti, kullanici_adi: str) -> Kullanici:
    kullanici = giris_dogrula(baglanti, kullanici_adi, PAROLA)
    assert kullanici is not None
    return kullanici


@pytest.fixture
def eczaci(uygulama_baglanti: Baglanti) -> Kullanici:
    kullanici_olustur(uygulama_baglanti, "eczaci1", "Test Eczacı", PAROLA, Rol.ECZACI)
    return _giris(uygulama_baglanti, "eczaci1")


@pytest.fixture
def personel(uygulama_baglanti: Baglanti, eczaci: Kullanici) -> Kullanici:
    kullanici_olustur(uygulama_baglanti, "personel1", "Test Personel", PAROLA, Rol.PERSONEL)
    return _giris(uygulama_baglanti, "personel1")


def _bilgi(**degisen: Any) -> UrunBilgisi:
    temel = UrunBilgisi(
        ad="Deneme İlaç",
        gtin="08691234567890",
        urun_turu=UrunTuru.ILAC,
        karekodlu=True,
        recete_turu=ReceteTuru.NORMAL,
        kritik_stok=0,
        raf_yeri=None,
        etken_madde=None,
        farmasotik_form=None,
        atc_kodu=None,
        uretici_firma=None,
        soguk_zincir=False,
    )
    return replace(temel, **degisen)


@pytest.fixture
def ilac(uygulama_baglanti: Baglanti, eczaci: Kullanici) -> int:
    return urun_ekle(uygulama_baglanti, eczaci, _bilgi(), FIYAT)


@pytest.fixture
def diger(uygulama_baglanti: Baglanti, eczaci: Kullanici) -> int:
    bilgi = _bilgi(
        ad="Deneme Krem",
        gtin=None,
        urun_turu=UrunTuru.DIGER,
        karekodlu=False,
        recete_turu=ReceteTuru.RECETESIZ,
    )
    return urun_ekle(uygulama_baglanti, eczaci, bilgi, FIYAT)


@pytest.fixture
def depo(uygulama_baglanti: Baglanti, eczaci: Kullanici) -> int:
    return tedarikci_ekle(uygulama_baglanti, eczaci, "Deneme Ecza Deposu")


def _giris_bilgisi(urun_id: int, depo_id: int | None, **degisen: Any) -> StokGirisi:
    temel = StokGirisi(
        urun_id=urun_id,
        tur=HareketTuru.GIRIS,
        parti_no="ABC123",
        skt=UZAK_SKT,
        alinan_adet=10,
        mf_adet=1,
        toplam_tutar=Decimal("1000.00"),
        tedarikci_id=depo_id,
        fatura_no="FTR-2026-001",
    )
    return replace(temel, **degisen)


def _partiler(baglanti: Baglanti) -> list[dict[str, Any]]:
    return [
        dict(s)
        for s in baglanti.execute(
            "SELECT id, urun_id, parti_no, skt, miktar, birim_maliyet FROM stok_partileri ORDER BY id"
        ).fetchall()
    ]


def _hareketler(baglanti: Baglanti) -> list[dict[str, Any]]:
    return [
        dict(s)
        for s in baglanti.execute("SELECT * FROM stok_hareketleri ORDER BY id").fetchall()
    ]


# --- Temel giris ---


def test_giris_parti_ve_hareket_olusturur(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    parti_id = stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo))

    partiler = _partiler(uygulama_baglanti)
    assert len(partiler) == 1
    assert partiler[0]["id"] == parti_id
    assert partiler[0]["parti_no"] == "ABC123"
    assert partiler[0]["skt"] == UZAK_SKT
    assert partiler[0]["miktar"] == 11
    assert partiler[0]["birim_maliyet"] == Decimal("90.9091")

    hareket = _hareketler(uygulama_baglanti)[0]
    assert hareket["parti_id"] == parti_id
    assert hareket["tur"] == "giris"
    assert hareket["miktar"] == 11
    assert hareket["alinan_adet"] == 10
    assert hareket["mf_adet"] == 1
    assert hareket["toplam_tutar"] == Decimal("1000.00")
    assert hareket["tedarikci_id"] == depo
    assert hareket["fatura_no"] == "FTR-2026-001"
    assert hareket["kullanici_id"] == eczaci.id
    assert hareket["tarih"] is not None


def test_ayni_parti_skt_ve_maliyet_tek_satirda_toplanir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    ilk = stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo))
    ikinci = stok_girisi_yap(
        uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo, fatura_no="FTR-2")
    )

    assert ilk == ikinci
    assert [p["miktar"] for p in _partiler(uygulama_baglanti)] == [22]
    assert len(_hareketler(uygulama_baglanti)) == 2


def test_maliyet_farkliysa_ayri_parti_satiri_olur(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo))
    stok_girisi_yap(
        uygulama_baglanti,
        eczaci,
        _giris_bilgisi(ilac, depo, mf_adet=0, fatura_no="FTR-2"),
    )

    maliyetler = sorted(p["birim_maliyet"] for p in _partiler(uygulama_baglanti))
    assert maliyetler == [Decimal("90.9091"), Decimal("100.0000")]


def test_hareket_toplami_her_zaman_parti_miktarina_esittir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, diger: int, depo: int
) -> None:
    girisler = [
        _giris_bilgisi(ilac, depo),
        _giris_bilgisi(ilac, depo, fatura_no="F2", alinan_adet=5, mf_adet=0,
                       toplam_tutar=Decimal("500.00")),
        _giris_bilgisi(ilac, depo, fatura_no="F3", parti_no="XYZ9", alinan_adet=3, mf_adet=0,
                       toplam_tutar=Decimal("270.00")),
        _giris_bilgisi(diger, depo, fatura_no="F4", parti_no=None),
    ]
    for giris in girisler:
        stok_girisi_yap(uygulama_baglanti, eczaci, giris)

    tutarsiz = uygulama_baglanti.execute(
        "SELECT p.id FROM stok_partileri p LEFT JOIN stok_hareketleri h ON h.parti_id = p.id "
        "GROUP BY p.id, p.miktar HAVING p.miktar <> COALESCE(SUM(h.miktar), 0)"
    ).fetchall()
    assert tutarsiz == []


def test_toplam_maliyet_fatura_tutarindan_kurusu_kurusuna_hesaplanir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    # 1000 / 11 = 90,9091 x 11 = 1000,0001; dogru toplam hareketteki fatura tutaridir.
    stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo))
    satir = uygulama_baglanti.execute(
        "SELECT SUM(toplam_tutar) AS toplam FROM stok_hareketleri"
    ).fetchone()
    assert satir is not None
    assert satir["toplam"] == Decimal("1000.00")


def test_stok_urun_listesinde_gorunur(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo))
    urun = urun_ara(uygulama_baglanti, eczaci, "deneme ilaç")[0]
    assert urun.stok_miktari == 11
    assert urun.en_yakin_skt == UZAK_SKT


def test_fiyat_degisince_gecmise_girilen_stok_yazilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo))

    urun_guncelle(
        uygulama_baglanti, eczaci, ilac, _bilgi(), UrunFiyati(Decimal("110"), None, Decimal("10"))
    )

    satir = uygulama_baglanti.execute(
        "SELECT stok_miktari FROM fiyat_gecmisi ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert satir is not None
    assert satir["stok_miktari"] == 11


def test_fiyat_degisirken_stok_girisi_bekler(
    uygulama_baglanti: Baglanti,
    uygulama_ayari: VeritabaniAyari,
    eczaci: Kullanici,
    ilac: int,
    depo: int,
) -> None:
    """Fiyat degistiren islem urun satirini kilitler; stok girisi araya giremez.

    Var olan partiye ekleme yapilir: yeni partideki yabanci anahtar denetimi de urunu kisa
    sure kilitledigi icin, yalnizca bu durum acik kilidin gercekten alindigini gosterir.
    """
    stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo))
    kilit_alindi = threading.Event()
    birak = threading.Event()

    def _fiyat_islemi() -> None:
        with baglanti_ac(uygulama_ayari) as kasa, kasa.transaction():
            kasa.execute("SELECT 1 FROM urunler WHERE id = %s FOR UPDATE", (ilac,))
            kilit_alindi.set()
            birak.wait(timeout=10)

    is_parcacigi = threading.Thread(target=_fiyat_islemi)
    is_parcacigi.start()
    try:
        assert kilit_alindi.wait(timeout=10)
        uygulama_baglanti.execute("SET lock_timeout = '300ms'")
        with pytest.raises(psycopg.errors.LockNotAvailable):
            stok_girisi_yap(
                uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo, fatura_no="FTR-2")
            )
    finally:
        birak.set()
        is_parcacigi.join()
        uygulama_baglanti.execute("RESET lock_timeout")
    assert [p["miktar"] for p in _partiler(uygulama_baglanti)] == [11]
    assert len(_hareketler(uygulama_baglanti)) == 1


# --- Parti ve SKT kurallari ---


def test_ilacta_parti_zorunludur(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    with pytest.raises(GorunurHata, match="Parti"):
        stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo, parti_no=None))


def test_diger_urunde_parti_bos_olabilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, diger: int, depo: int
) -> None:
    stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(diger, depo, parti_no="  "))
    stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(diger, depo, parti_no=None,
                                                              fatura_no="F2"))
    partiler = _partiler(uygulama_baglanti)
    assert [(p["parti_no"], p["miktar"]) for p in partiler] == [(None, 22)]


def test_karekodlu_ilacta_kucuk_harfli_parti_reddedilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    with pytest.raises(GorunurHata, match="Parti"):
        stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo, parti_no="abc-1"))
    assert _partiler(uygulama_baglanti) == []


def test_karekodsuz_urunde_kucuk_harf_ve_tire_kabul_edilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, diger: int, depo: int
) -> None:
    stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(diger, depo, parti_no="lot-7"))
    assert _partiler(uygulama_baglanti)[0]["parti_no"] == "lot-7"


def test_karekodsuz_ilacta_da_gevsek_kural_uygulanir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, depo: int
) -> None:
    urun_id = urun_ekle(
        uygulama_baglanti, eczaci, _bilgi(gtin=None, karekodlu=False, ad="Karekodsuz"), FIYAT
    )
    stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(urun_id, depo, parti_no="ab-1"))
    assert _partiler(uygulama_baglanti)[0]["parti_no"] == "ab-1"


def test_skt_si_gecmis_urun_girilemez(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    dun = date.fromordinal(BUGUN.toordinal() - 1)
    with pytest.raises(GorunurHata, match="SKT"):
        stok_girisi_yap(
            uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo, skt=dun),
            uyarilar_onaylandi=True,
        )


def test_skt_si_bugun_olan_urun_onayla_girilebilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    stok_girisi_yap(
        uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo, skt=BUGUN), uyarilar_onaylandi=True
    )
    assert _partiler(uygulama_baglanti)[0]["skt"] == BUGUN


# --- Adet ve tutar ---


@pytest.mark.parametrize(
    ("degisen", "beklenen"),
    [
        ({"alinan_adet": 0, "mf_adet": 0}, "en az 1"),
        ({"alinan_adet": -1}, "eksi"),
        ({"mf_adet": -1}, "eksi"),
        ({"alinan_adet": 0, "mf_adet": 2, "toplam_tutar": Decimal("5")}, "bedelsiz"),
        ({"toplam_tutar": Decimal("-1")}, "Tutar"),
        ({"toplam_tutar": Decimal("10.001")}, "Tutar"),
    ],
)
def test_hatali_adet_ve_tutar_reddedilir(
    uygulama_baglanti: Baglanti,
    eczaci: Kullanici,
    ilac: int,
    depo: int,
    degisen: dict[str, Any],
    beklenen: str,
) -> None:
    with pytest.raises(GorunurHata, match=beklenen):
        stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo, **degisen))
    assert _partiler(uygulama_baglanti) == []


def test_yalnizca_mal_fazlasi_bedelsiz_girilebilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    stok_girisi_yap(
        uygulama_baglanti,
        eczaci,
        _giris_bilgisi(ilac, depo, alinan_adet=0, mf_adet=2, toplam_tutar=Decimal("0")),
    )
    parti = _partiler(uygulama_baglanti)[0]
    assert (parti["miktar"], parti["birim_maliyet"]) == (2, Decimal("0"))


# --- Depo, fatura, acilis stogu ---


def test_faturali_giriste_depo_ve_fatura_zorunludur(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    with pytest.raises(GorunurHata, match="Depo"):
        stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, None))
    with pytest.raises(GorunurHata, match="Fatura"):
        stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo, fatura_no="  "))


def test_pasif_depoya_giris_yapilamaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    tedarikci_pasif_yap(uygulama_baglanti, eczaci, depo)
    with pytest.raises(GorunurHata, match="Depo"):
        stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo))


def test_pasif_urune_giris_yapilamaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    urun_pasif_yap(uygulama_baglanti, eczaci, ilac)
    with pytest.raises(GorunurHata, match="pasif"):
        stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo))


def test_eczaci_depo_ve_faturasiz_acilis_stogu_girer(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int
) -> None:
    acilis = _giris_bilgisi(
        ilac, None, tur=HareketTuru.ACILIS, fatura_no=None, alinan_adet=7, mf_adet=0,
        toplam_tutar=Decimal("560.00"),
    )

    stok_girisi_yap(uygulama_baglanti, eczaci, acilis)

    hareket = _hareketler(uygulama_baglanti)[0]
    assert hareket["tur"] == "acilis"
    assert hareket["tedarikci_id"] is None
    assert hareket["fatura_no"] is None
    assert _partiler(uygulama_baglanti)[0]["birim_maliyet"] == Decimal("80.0000")


def test_personel_acilis_stogu_giremez(
    uygulama_baglanti: Baglanti, personel: Kullanici, ilac: int
) -> None:
    acilis = _giris_bilgisi(ilac, None, tur=HareketTuru.ACILIS, fatura_no=None, mf_adet=0)
    with pytest.raises(YetkiHatasi):
        stok_girisi_yap(uygulama_baglanti, personel, acilis)


def test_acilis_stogunda_depo_fatura_ve_mal_fazlasi_girilmez(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    with pytest.raises(GorunurHata, match="Açılış"):
        stok_girisi_yap(
            uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo, tur=HareketTuru.ACILIS)
        )


def test_personel_faturali_giris_yapar(
    uygulama_baglanti: Baglanti, personel: Kullanici, ilac: int, depo: int
) -> None:
    stok_girisi_yap(uygulama_baglanti, personel, _giris_bilgisi(ilac, depo))
    assert _hareketler(uygulama_baglanti)[0]["kullanici_id"] == personel.id


def test_pasif_kullanici_giris_yapamaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici, ilac: int, depo: int
) -> None:
    pasif_yap(uygulama_baglanti, eczaci, personel.id)
    with pytest.raises(YetkiHatasi):
        stok_girisi_yap(uygulama_baglanti, personel, _giris_bilgisi(ilac, depo))


# --- Onay isteyen uyarilar ---


def _uyarilar(baglanti: Baglanti, yapan: Kullanici, giris: StokGirisi) -> list[str]:
    with pytest.raises(OnayGerekli) as hata:
        stok_girisi_yap(baglanti, yapan, giris)
    return hata.value.uyarilar


def test_uyari_yoksa_onay_istenmez(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo))
    assert len(_partiler(uygulama_baglanti)) == 1


def test_yakin_miatli_giriste_onay_istenir_onaysiz_kayit_olmaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    giris = _giris_bilgisi(ilac, depo, skt=ay_ekle(BUGUN, 3))

    uyarilar = _uyarilar(uygulama_baglanti, eczaci, giris)

    assert len(uyarilar) == 1
    assert "6 ay" in uyarilar[0]
    assert _partiler(uygulama_baglanti) == []
    assert _hareketler(uygulama_baglanti) == []

    stok_girisi_yap(uygulama_baglanti, eczaci, giris, uyarilar_onaylandi=True)
    assert len(_partiler(uygulama_baglanti)) == 1


def test_miat_uyari_suresi_ayardan_okunur(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    miat_uyari_ayi_ayarla(uygulama_baglanti, eczaci, 2)
    stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo, skt=ay_ekle(BUGUN, 3)))
    assert len(_partiler(uygulama_baglanti)) == 1


def test_yedi_yildan_uzak_sktde_onay_istenir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    uyarilar = _uyarilar(
        uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo, skt=ay_ekle(BUGUN, 85))
    )
    assert any("7 yıl" in u for u in uyarilar)


def test_ayni_parti_farkli_skt_ile_girilirse_onay_istenir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo))
    uyarilar = _uyarilar(
        uygulama_baglanti,
        eczaci,
        _giris_bilgisi(ilac, depo, skt=ay_ekle(BUGUN, 30), fatura_no="F2"),
    )
    assert any("farklı SKT" in u for u in uyarilar)


def test_ayni_fatura_ve_parti_tekrar_girilirse_onay_istenir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo))
    uyarilar = _uyarilar(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo))
    assert any("daha önce girilmiş" in u for u in uyarilar)
    assert len(_hareketler(uygulama_baglanti)) == 1


def test_birden_cok_uyari_birlikte_gosterilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo))
    uyarilar = _uyarilar(
        uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo, skt=ay_ekle(BUGUN, 2))
    )
    assert len(uyarilar) == 3


# --- Gorunum ve alis fiyati gizliligi ---


def test_eczaci_parti_maliyetini_ve_fatura_tutarini_gorur(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo))

    parti = partileri_getir(uygulama_baglanti, eczaci, ilac)[0]
    hareket = hareketleri_getir(uygulama_baglanti, eczaci, ilac)[0]

    assert (parti.parti_no, parti.skt, parti.miktar) == ("ABC123", UZAK_SKT, 11)
    assert parti.birim_maliyet == Decimal("90.9091")
    assert hareket.tur is HareketTuru.GIRIS
    assert (hareket.alinan_adet, hareket.mf_adet, hareket.miktar) == (10, 1, 11)
    assert hareket.tedarikci_adi == "Deneme Ecza Deposu"
    assert hareket.fatura_no == "FTR-2026-001"
    assert hareket.kullanici_adi == "Test Eczacı"
    assert hareket.toplam_tutar == Decimal("1000.00")


def test_personel_alis_fiyatini_kaydettikten_sonra_goremez(
    uygulama_baglanti: Baglanti, personel: Kullanici, ilac: int, depo: int
) -> None:
    stok_girisi_yap(uygulama_baglanti, personel, _giris_bilgisi(ilac, depo))

    parti = partileri_getir(uygulama_baglanti, personel, ilac)[0]
    hareket = hareketleri_getir(uygulama_baglanti, personel, ilac)[0]

    assert parti.miktar == 11
    assert parti.birim_maliyet is None
    assert hareket.toplam_tutar is None
    assert hareket.alinan_adet == 10


def test_biten_parti_varsayilan_olarak_listelenmez(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo))
    uygulama_baglanti.execute("UPDATE stok_partileri SET miktar = 0")

    assert partileri_getir(uygulama_baglanti, eczaci, ilac) == []
    assert len(partileri_getir(uygulama_baglanti, eczaci, ilac, bitenler_dahil=True)) == 1


def test_partiler_skt_sirasiyla_gelir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ilac: int, depo: int
) -> None:
    stok_girisi_yap(uygulama_baglanti, eczaci, _giris_bilgisi(ilac, depo))
    stok_girisi_yap(
        uygulama_baglanti,
        eczaci,
        _giris_bilgisi(ilac, depo, parti_no="ERKEN1", skt=ay_ekle(BUGUN, 12), fatura_no="F2"),
    )
    assert [p.parti_no for p in partileri_getir(uygulama_baglanti, eczaci, ilac)] == [
        "ERKEN1",
        "ABC123",
    ]


# --- Depolar ---


def test_personel_depo_ekler(uygulama_baglanti: Baglanti, personel: Kullanici) -> None:
    depo_id = tedarikci_ekle(uygulama_baglanti, personel, "  Selçuk Ecza  ")
    depolar = tedarikcileri_listele(uygulama_baglanti, personel)
    assert [(d.id, d.ad) for d in depolar] == [(depo_id, "Selçuk Ecza")]


@pytest.mark.parametrize("ad", ["SELÇUK ECZA", "selcuk ecza", "Selçuk  Ecza"])
def test_ayni_depo_farkli_yazimla_iki_kez_eklenemez(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ad: str
) -> None:
    tedarikci_ekle(uygulama_baglanti, eczaci, "Selçuk Ecza")
    with pytest.raises(GorunurHata, match="kayıtlı"):
        tedarikci_ekle(uygulama_baglanti, eczaci, ad)


def test_bos_depo_adi_reddedilir(uygulama_baglanti: Baglanti, eczaci: Kullanici) -> None:
    with pytest.raises(GorunurHata, match="Depo adı"):
        tedarikci_ekle(uygulama_baglanti, eczaci, "   ")


def test_depoyu_yalnizca_eczaci_pasif_yapar(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici, depo: int
) -> None:
    with pytest.raises(YetkiHatasi):
        tedarikci_pasif_yap(uygulama_baglanti, personel, depo)

    tedarikci_pasif_yap(uygulama_baglanti, eczaci, depo)

    assert tedarikcileri_listele(uygulama_baglanti, eczaci) == []
    pasifler = tedarikcileri_listele(uygulama_baglanti, eczaci, pasifler_dahil=True)
    assert [d.aktif for d in pasifler] == [False]

    tedarikci_aktif_yap(uygulama_baglanti, eczaci, depo)
    assert len(tedarikcileri_listele(uygulama_baglanti, eczaci)) == 1


# --- Miat uyari ayari ---


def test_miat_uyari_suresi_varsayilan_6_aydir(
    uygulama_baglanti: Baglanti, personel: Kullanici
) -> None:
    assert VARSAYILAN_MIAT_UYARI_AYI == 6
    assert miat_uyari_ayi(uygulama_baglanti, personel) == 6


def test_eczaci_miat_uyari_suresini_degistirir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    miat_uyari_ayi_ayarla(uygulama_baglanti, eczaci, 3)
    miat_uyari_ayi_ayarla(uygulama_baglanti, eczaci, 4)
    assert miat_uyari_ayi(uygulama_baglanti, personel) == 4


def test_personel_miat_uyari_suresini_degistiremez(
    uygulama_baglanti: Baglanti, personel: Kullanici
) -> None:
    with pytest.raises(YetkiHatasi):
        miat_uyari_ayi_ayarla(uygulama_baglanti, personel, 3)


@pytest.mark.parametrize("ay", [0, -1, 61])
def test_miat_uyari_suresi_sinir_disi_olamaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, ay: int
) -> None:
    with pytest.raises(GorunurHata, match="1 ile 60"):
        miat_uyari_ayi_ayarla(uygulama_baglanti, eczaci, ay)
