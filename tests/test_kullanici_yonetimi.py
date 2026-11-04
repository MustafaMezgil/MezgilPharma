"""Eczacinin yaptigi kullanici islemleri: ekleme, sifirlama, kilit acma, pasif yapma."""

from collections.abc import Callable
from dataclasses import replace

import pytest

from moduller.kullanici.servis import (
    AZAMI_HATALI_GIRIS,
    HesapKilitliHatasi,
    Kullanici,
    KullaniciHatasi,
    Rol,
    YetkiHatasi,
    aktif_yap,
    giris_dogrula,
    kilit_ac,
    kullanici_olustur,
    kullanicilari_listele,
    parola_degistir,
    parola_sifirla,
    pasif_yap,
    personel_ekle,
)
from veritabani.baglanti import Baglanti

PAROLA = "Deneme-Parola1"
GECICI = "Gecici-Parola1"
YENI = "Yeni-Parola-123"


def _giris(baglanti: Baglanti, kullanici_adi: str, parola: str = PAROLA) -> Kullanici:
    kullanici = giris_dogrula(baglanti, kullanici_adi, parola)
    assert kullanici is not None
    return kullanici


@pytest.fixture
def eczaci(uygulama_baglanti: Baglanti) -> Kullanici:
    kullanici_olustur(uygulama_baglanti, "eczaci1", "Birinci Eczacı", PAROLA, Rol.ECZACI)
    return _giris(uygulama_baglanti, "eczaci1")


@pytest.fixture
def personel(uygulama_baglanti: Baglanti, eczaci: Kullanici) -> Kullanici:
    kullanici_olustur(uygulama_baglanti, "personel1", "Birinci Personel", PAROLA, Rol.PERSONEL)
    return _giris(uygulama_baglanti, "personel1")


def _erisim_kayitlari(baglanti: Baglanti) -> list[tuple[int, str, str, int]]:
    satirlar = baglanti.execute(
        "SELECT kullanici_id, islem, kayit_turu, kayit_id FROM erisim_log ORDER BY id"
    ).fetchall()
    return [
        (s["kullanici_id"], s["islem"], s["kayit_turu"], s["kayit_id"]) for s in satirlar
    ]


def _kilitle(baglanti: Baglanti, kullanici_adi: str) -> None:
    for _ in range(AZAMI_HATALI_GIRIS - 1):
        giris_dogrula(baglanti, kullanici_adi, "yanlis-parola")
    with pytest.raises(HesapKilitliHatasi):
        giris_dogrula(baglanti, kullanici_adi, "yanlis-parola")


# --- Personel ekleme ---


def test_eczaci_personel_ekler_ve_ilk_giriste_parola_degismelidir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    yeni_id = personel_ekle(
        uygulama_baglanti, eczaci, "yeni", "Yeni Kişi", GECICI, Rol.PERSONEL
    )

    giren = _giris(uygulama_baglanti, "yeni", GECICI)
    assert giren.id == yeni_id
    assert giren.rol is Rol.PERSONEL
    assert giren.parola_degismeli


def test_eczaci_ikinci_eczaci_ekleyebilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    personel_ekle(uygulama_baglanti, eczaci, "ikinci", "İkinci Eczacı", GECICI, Rol.ECZACI)
    assert _giris(uygulama_baglanti, "ikinci", GECICI).rol is Rol.ECZACI


def test_personel_ekleme_erisim_kaydina_yazilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    yeni_id = personel_ekle(
        uygulama_baglanti, eczaci, "yeni", "Yeni Kişi", GECICI, Rol.PERSONEL
    )
    assert _erisim_kayitlari(uygulama_baglanti) == [
        (eczaci.id, "personel_ekleme", "kullanici", yeni_id)
    ]


def test_ayni_kullanici_adi_eklenemez_ve_kayit_birakmaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    with pytest.raises(KullaniciHatasi, match="kullanılıyor"):
        personel_ekle(uygulama_baglanti, eczaci, "eczaci1", "Kopya", GECICI, Rol.PERSONEL)
    assert _erisim_kayitlari(uygulama_baglanti) == []


def test_ilk_hesap_parola_degistirmek_zorunda_degildir(eczaci: Kullanici) -> None:
    assert not eczaci.parola_degismeli


# --- Yetki ---

Islem = Callable[[Baglanti, Kullanici, int], object]

_ECZACI_ISLEMLERI: list[Islem] = [
    lambda b, y, h: personel_ekle(b, y, "izinsiz", "İzinsiz", GECICI, Rol.PERSONEL),
    lambda b, y, h: parola_sifirla(b, y, h, GECICI),
    lambda b, y, h: kilit_ac(b, y, h),
    lambda b, y, h: pasif_yap(b, y, h),
    lambda b, y, h: aktif_yap(b, y, h),
    lambda b, y, h: kullanicilari_listele(b, y),
]


@pytest.mark.parametrize("islem", _ECZACI_ISLEMLERI)
def test_personel_eczaci_islemlerini_yapamaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici, islem: Islem
) -> None:
    with pytest.raises(YetkiHatasi, match="eczacı"):
        islem(uygulama_baglanti, personel, eczaci.id)
    assert _erisim_kayitlari(uygulama_baglanti) == []


@pytest.mark.parametrize("islem", _ECZACI_ISLEMLERI)
def test_yetki_nesneden_degil_veritabanindan_okunur(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici, islem: Islem
) -> None:
    sahte = replace(personel, rol=Rol.ECZACI)
    with pytest.raises(YetkiHatasi):
        islem(uygulama_baglanti, sahte, eczaci.id)


def test_pasif_yapilan_eczaci_artik_islem_yapamaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    personel_ekle(uygulama_baglanti, eczaci, "ikinci", "İkinci Eczacı", GECICI, Rol.ECZACI)
    ikinci = _giris(uygulama_baglanti, "ikinci", GECICI)
    pasif_yap(uygulama_baglanti, ikinci, eczaci.id)

    with pytest.raises(YetkiHatasi):
        parola_sifirla(uygulama_baglanti, eczaci, personel.id, GECICI)


# --- Parola sifirlama ---


def test_sifirlama_sonrasi_yeni_parola_gecerlidir_eskisi_degil(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    parola_sifirla(uygulama_baglanti, eczaci, personel.id, GECICI)

    assert giris_dogrula(uygulama_baglanti, "personel1", PAROLA) is None
    assert _giris(uygulama_baglanti, "personel1", GECICI).parola_degismeli


def test_sifirlama_kilidi_kaldirir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    _kilitle(uygulama_baglanti, "personel1")
    parola_sifirla(uygulama_baglanti, eczaci, personel.id, GECICI)
    assert giris_dogrula(uygulama_baglanti, "personel1", GECICI) is not None


def test_sifirlama_erisim_kaydina_yazilir_parola_yazilmaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    parola_sifirla(uygulama_baglanti, eczaci, personel.id, GECICI)

    kayitlar = _erisim_kayitlari(uygulama_baglanti)
    assert kayitlar == [(eczaci.id, "parola_sifirlama", "kullanici", personel.id)]
    assert GECICI not in str(kayitlar)


def test_eczaci_kendi_parolasini_sifirlama_ile_degistiremez(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    with pytest.raises(KullaniciHatasi, match="Parolamı Değiştir"):
        parola_sifirla(uygulama_baglanti, eczaci, eczaci.id, GECICI)


def test_kisa_gecici_parola_kabul_edilmez(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    with pytest.raises(KullaniciHatasi, match="en az 8"):
        parola_sifirla(uygulama_baglanti, eczaci, personel.id, "kisa")
    assert giris_dogrula(uygulama_baglanti, "personel1", PAROLA) is not None


def test_olmayan_kullanicinin_parolasi_sifirlanamaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    with pytest.raises(KullaniciHatasi, match="bulunamadı"):
        parola_sifirla(uygulama_baglanti, eczaci, 999999, GECICI)
    assert _erisim_kayitlari(uygulama_baglanti) == []


def test_pasif_kullanicinin_parolasi_sifirlanamaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    pasif_yap(uygulama_baglanti, eczaci, personel.id)
    with pytest.raises(KullaniciHatasi, match="pasif"):
        parola_sifirla(uygulama_baglanti, eczaci, personel.id, GECICI)


# --- Kilit acma ---


def test_kilit_acilinca_eski_parola_ile_girilir_ve_kayit_yazilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    _kilitle(uygulama_baglanti, "personel1")

    kilit_ac(uygulama_baglanti, eczaci, personel.id)

    assert _giris(uygulama_baglanti, "personel1") is not None
    assert _erisim_kayitlari(uygulama_baglanti) == [
        (eczaci.id, "kilit_acma", "kullanici", personel.id)
    ]


# --- Parola degistirme ---


def test_kullanici_kendi_parolasini_degistirir_ve_zorunluluk_kalkar(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    parola_sifirla(uygulama_baglanti, eczaci, personel.id, GECICI)
    giren = _giris(uygulama_baglanti, "personel1", GECICI)

    parola_degistir(uygulama_baglanti, giren, GECICI, YENI)

    assert giris_dogrula(uygulama_baglanti, "personel1", GECICI) is None
    assert not _giris(uygulama_baglanti, "personel1", YENI).parola_degismeli
    assert _erisim_kayitlari(uygulama_baglanti)[-1] == (
        personel.id,
        "parola_degistirme",
        "kullanici",
        personel.id,
    )


def test_mevcut_parola_yanlissa_degistirilemez(
    uygulama_baglanti: Baglanti, personel: Kullanici
) -> None:
    with pytest.raises(KullaniciHatasi, match="Mevcut parola"):
        parola_degistir(uygulama_baglanti, personel, "yanlis-parola", YENI)
    assert _giris(uygulama_baglanti, "personel1") is not None


def test_yanlis_mevcut_parola_kilit_sayacina_isler(
    uygulama_baglanti: Baglanti, personel: Kullanici
) -> None:
    for _ in range(AZAMI_HATALI_GIRIS - 1):
        with pytest.raises(KullaniciHatasi, match="Mevcut parola"):
            parola_degistir(uygulama_baglanti, personel, "yanlis-parola", YENI)
    with pytest.raises(HesapKilitliHatasi):
        parola_degistir(uygulama_baglanti, personel, "yanlis-parola", YENI)


def test_yeni_parola_kisaysa_sayac_artmaz(
    uygulama_baglanti: Baglanti, personel: Kullanici
) -> None:
    for _ in range(AZAMI_HATALI_GIRIS):
        with pytest.raises(KullaniciHatasi, match="en az 8"):
            parola_degistir(uygulama_baglanti, personel, "yanlis-parola", "kisa")
    assert _giris(uygulama_baglanti, "personel1") is not None


def test_yeni_parola_eskisiyle_ayni_olamaz(
    uygulama_baglanti: Baglanti, personel: Kullanici
) -> None:
    with pytest.raises(KullaniciHatasi, match="aynı olamaz"):
        parola_degistir(uygulama_baglanti, personel, PAROLA, PAROLA)


# --- Pasif / aktif yapma ---


def test_pasif_yapilan_personel_giris_yapamaz_kayit_yazilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    pasif_yap(uygulama_baglanti, eczaci, personel.id)

    assert giris_dogrula(uygulama_baglanti, "personel1", PAROLA) is None
    assert _erisim_kayitlari(uygulama_baglanti) == [
        (eczaci.id, "pasif_yapma", "kullanici", personel.id)
    ]


def test_son_aktif_eczaci_pasif_yapilamaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    with pytest.raises(KullaniciHatasi, match="Son aktif eczacı"):
        pasif_yap(uygulama_baglanti, eczaci, eczaci.id)

    assert _giris(uygulama_baglanti, "eczaci1") is not None
    assert _erisim_kayitlari(uygulama_baglanti) == []


def test_personel_varken_de_son_eczaci_pasif_yapilamaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    with pytest.raises(KullaniciHatasi, match="Son aktif eczacı"):
        pasif_yap(uygulama_baglanti, eczaci, eczaci.id)


def test_ikinci_eczaci_varsa_biri_pasif_yapilabilir_digeri_kalir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici
) -> None:
    personel_ekle(uygulama_baglanti, eczaci, "ikinci", "İkinci Eczacı", GECICI, Rol.ECZACI)
    ikinci = _giris(uygulama_baglanti, "ikinci", GECICI)

    pasif_yap(uygulama_baglanti, eczaci, ikinci.id)

    with pytest.raises(KullaniciHatasi, match="Son aktif eczacı"):
        pasif_yap(uygulama_baglanti, eczaci, eczaci.id)


def test_zaten_pasif_kullanici_tekrar_pasif_yapilamaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    pasif_yap(uygulama_baglanti, eczaci, personel.id)
    with pytest.raises(KullaniciHatasi, match="pasif"):
        pasif_yap(uygulama_baglanti, eczaci, personel.id)


def test_aktif_yapilan_kullanici_yeniden_girer_kayit_yazilir(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    pasif_yap(uygulama_baglanti, eczaci, personel.id)

    aktif_yap(uygulama_baglanti, eczaci, personel.id)

    assert _giris(uygulama_baglanti, "personel1") is not None
    assert _erisim_kayitlari(uygulama_baglanti)[-1] == (
        eczaci.id,
        "aktif_yapma",
        "kullanici",
        personel.id,
    )


def test_pasif_yapma_kaydi_silmez(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    pasif_yap(uygulama_baglanti, eczaci, personel.id)
    satir = uygulama_baglanti.execute(
        "SELECT aktif FROM kullanicilar WHERE id = %s", (personel.id,)
    ).fetchone()
    assert satir is not None
    assert satir["aktif"] is False


# --- Listeleme ---


def test_liste_durumlari_dogru_gosterir_parola_ozeti_tasimaz(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    kullanici_olustur(uygulama_baglanti, "ayrilan", "Ayrılan Kişi", PAROLA, Rol.PERSONEL)
    ayrilan = _giris(uygulama_baglanti, "ayrilan")
    pasif_yap(uygulama_baglanti, eczaci, ayrilan.id)
    _kilitle(uygulama_baglanti, "personel1")

    liste = {k.kullanici_adi: k for k in kullanicilari_listele(uygulama_baglanti, eczaci)}

    assert set(liste) == {"eczaci1", "personel1", "ayrilan"}
    assert liste["eczaci1"].aktif and not liste["eczaci1"].kilitli
    assert liste["eczaci1"].rol is Rol.ECZACI
    assert liste["personel1"].kilitli
    assert not liste["ayrilan"].aktif
    assert not hasattr(liste["eczaci1"], "parola_ozeti")


def test_sure_dolan_kilit_listede_kilitli_gorunmez(
    uygulama_baglanti: Baglanti, eczaci: Kullanici, personel: Kullanici
) -> None:
    _kilitle(uygulama_baglanti, "personel1")
    uygulama_baglanti.execute(
        "UPDATE kullanicilar SET kilit_bitis = now() - interval '1 second'"
    )
    liste = {k.kullanici_adi: k for k in kullanicilari_listele(uygulama_baglanti, eczaci)}
    assert not liste["personel1"].kilitli
