import pytest

from moduller.kullanici.parola import parola_dogru_mu, parola_ozetle

pytestmark = pytest.mark.gercek_parola


def test_gercek_ozet_guclu_ayarla_uretilir() -> None:
    assert parola_ozetle("DenemeParola").startswith("scrypt$32768$8$1$")


def test_dogru_parola_kabul_edilir() -> None:
    assert parola_dogru_mu("Şifre-Deneme1", parola_ozetle("Şifre-Deneme1"))


def test_yanlis_parola_reddedilir() -> None:
    assert not parola_dogru_mu("yanlis-parola", parola_ozetle("Şifre-Deneme1"))


def test_ozet_parolanin_kendisini_icermez() -> None:
    assert "DenemeParola" not in parola_ozetle("DenemeParola")


def test_ayni_parolanin_ozetleri_farkli_olur() -> None:
    assert parola_ozetle("DenemeParola") != parola_ozetle("DenemeParola")


def test_bozuk_ozet_hata_vermeden_reddedilir() -> None:
    assert not parola_dogru_mu("DenemeParola", "bozuk-ozet")
    assert not parola_dogru_mu("DenemeParola", "scrypt$x$y$z$zz$zz")
    assert not parola_dogru_mu("DenemeParola", "")
