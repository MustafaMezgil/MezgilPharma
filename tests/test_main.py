from pathlib import Path

import pytest
from PyQt6.QtWidgets import QMessageBox, QWidget

import main
from ayarlar import Ayarlar, Ortam
from veritabani.baglanti import baglanti_ac
from veritabani.migration import guncel_surum


def _ayarlar(klasor: Path) -> Ayarlar:
    return Ayarlar(
        ortam=Ortam.TEST,
        veritabani_yolu=klasor / "veri" / "eczane_test.db",
        yedek_klasoru=klasor / "yedekler",
        log_klasoru=klasor / "logs",
    )


def test_veritabani_son_surume_hazirlanir(tmp_path: Path) -> None:
    ayarlar = _ayarlar(tmp_path)

    surum = main.veritabanini_hazirla(ayarlar)

    assert surum >= 1
    baglanti = baglanti_ac(ayarlar.veritabani_yolu)
    assert guncel_surum(baglanti) == surum
    baglanti.close()


@pytest.mark.usefixtures("qt_uygulamasi", "temiz_gunluk")
def test_bozuk_veritabaninda_turkce_mesaj_gosterilir_ve_acilmaz(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ayarlar = _ayarlar(tmp_path)
    ayarlar.veritabani_yolu.parent.mkdir(parents=True)
    ayarlar.veritabani_yolu.write_bytes(b"bu bir veritabani dosyasi degil" * 100)
    mesajlar: list[str] = []

    def _kaydet(_ust: QWidget | None, _baslik: str, metin: str) -> None:
        mesajlar.append(metin)

    monkeypatch.setattr(QMessageBox, "critical", _kaydet)

    assert main.baslat(ayarlar) == 1
    assert len(mesajlar) == 1
    assert "Veritabanı açılamadı" in mesajlar[0]
    assert "file is not a database" not in mesajlar[0]
    assert "file is not a database" in (ayarlar.log_klasoru / "eczane.log").read_text(
        encoding="utf-8"
    )
