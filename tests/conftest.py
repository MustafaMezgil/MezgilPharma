"""Testlerin ortak hazirliklari. Testler yalnizca eczane_pytest veritabanina dokunur."""

import logging
import os
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

# Pencereler testlerde ekranda acilmasin; PyQt6 yuklenmeden once ayarlanmalidir.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from psycopg import sql  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from ayarlar import AyarHatasi, Ayarlar, VeritabaniAyari, ayarlari_yukle  # noqa: E402
from moduller.kullanici import parola as parola_modulu  # noqa: E402
from veritabani.baglanti import Baglanti, baglanti_ac  # noqa: E402
from veritabani.guncelle import yetkileri_ver  # noqa: E402
from veritabani.migration import migrationlari_uygula  # noqa: E402

PYTEST_VERITABANI = "eczane_pytest"


@pytest.fixture(scope="session")
def qt_uygulamasi() -> QApplication:
    mevcut = QApplication.instance()
    if isinstance(mevcut, QApplication):
        return mevcut
    return QApplication([])


@pytest.fixture
def temiz_gunluk() -> Iterator[None]:
    """Test bitince log ayarlarini eski haline getirir ve log dosyasini kapatir."""
    kok = logging.getLogger()
    eski_isleyiciler = kok.handlers[:]
    eski_seviye = kok.level
    yield
    for isleyici in kok.handlers[:]:
        kok.removeHandler(isleyici)
        if isleyici not in eski_isleyiciler:
            isleyici.close()
    for isleyici in eski_isleyiciler:
        kok.addHandler(isleyici)
    kok.setLevel(eski_seviye)


@pytest.fixture(scope="session")
def gercek_ayarlar() -> Ayarlar:
    try:
        return ayarlari_yukle()
    except AyarHatasi as hata:
        pytest.fail(f"Veritabani testleri icin .env gerekli: {hata}")


@pytest.fixture(scope="session")
def uygulama_ayari(gercek_ayarlar: Ayarlar) -> VeritabaniAyari:
    return replace(gercek_ayarlar.veritabani, veritabani=PYTEST_VERITABANI)


@pytest.fixture(scope="session")
def sahip_ayari(gercek_ayarlar: Ayarlar) -> VeritabaniAyari:
    if gercek_ayarlar.sahip is None:
        pytest.fail("Veritabani testleri icin .env icinde sahip hesabi gerekli.")
    return replace(gercek_ayarlar.sahip, veritabani=PYTEST_VERITABANI)


@pytest.fixture(autouse=True)
def hizli_parola(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Testlerde parola ozetleme hafif ayarla calisir; gercek ayar test_parola.py'de denenir.

    Ayar ozetin icine yazildigi icin dogrulama yine dogru calisir.
    """
    if request.node.get_closest_marker("gercek_parola") is None:
        monkeypatch.setattr(parola_modulu, "_N", 2**4)


class _SemaDurumu:
    """Gercek sema bu test calistirmasinda kuruldu mu? Bozan test bunu sifirlar."""

    hazir = False


def _guvenli_baglanti(sahip_ayari: VeritabaniAyari) -> Baglanti:
    baglanti = baglanti_ac(sahip_ayari)
    satir = baglanti.execute("SELECT current_database() AS ad").fetchone()
    assert satir is not None
    if satir["ad"] != PYTEST_VERITABANI:
        baglanti.close()
        pytest.fail("Guvenlik: testler yalnizca eczane_pytest uzerinde calisabilir.")
    return baglanti


def _semayi_sil(sahip_ayari: VeritabaniAyari) -> None:
    _SemaDurumu.hazir = False
    with _guvenli_baglanti(sahip_ayari) as baglanti:
        baglanti.execute("DROP SCHEMA public CASCADE")
        baglanti.execute("CREATE SCHEMA public")
        baglanti.execute("GRANT USAGE ON SCHEMA public TO PUBLIC")


@pytest.fixture
def temiz_veritabani(sahip_ayari: VeritabaniAyari) -> None:
    """eczane_pytest icindeki her seyi siler. Baska veritabaninda calismayi reddeder."""
    _semayi_sil(sahip_ayari)


@pytest.fixture
def hazir_veritabani(sahip_ayari: VeritabaniAyari, uygulama_ayari: VeritabaniAyari) -> None:
    """Gercek migration'lar ve yetkilerle kurulu, verisi bos veritabani.

    Sema her calistirmada bir kez kurulur; testler arasinda yalnizca tablolar bosaltilir.
    Semayi silen bir test (temiz_veritabani) sonraki testte yeniden kurulmasini saglar.
    """

    def _yedek_alma(_surum: int) -> None:
        pytest.fail("Bos veritabaninda yedek alinmamali.")

    if not _SemaDurumu.hazir:
        _semayi_sil(sahip_ayari)
        with _guvenli_baglanti(sahip_ayari) as baglanti:
            migrationlari_uygula(baglanti, yedek_al=_yedek_alma)
            yetkileri_ver(baglanti, uygulama_ayari.kullanici)
        _SemaDurumu.hazir = True
        return

    with _guvenli_baglanti(sahip_ayari) as baglanti:
        tablolar = [
            sql.Identifier(satir["tablename"])
            for satir in baglanti.execute(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename <> 'schema_surum'"
            )
        ]
        if tablolar:
            baglanti.execute(
                sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(sql.SQL(", ").join(tablolar))
            )


@pytest.fixture
def sahip_baglanti(
    temiz_veritabani: None, sahip_ayari: VeritabaniAyari
) -> Iterator[Baglanti]:
    with baglanti_ac(sahip_ayari) as baglanti:
        yield baglanti


@pytest.fixture
def uygulama_baglanti(
    hazir_veritabani: None, uygulama_ayari: VeritabaniAyari
) -> Iterator[Baglanti]:
    with baglanti_ac(uygulama_ayari) as baglanti:
        yield baglanti


@pytest.fixture
def yedek_klasoru(tmp_path: Path) -> Path:
    return tmp_path / "yedekler"
