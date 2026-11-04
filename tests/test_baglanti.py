import sqlite3
from pathlib import Path

import pytest

from veritabani.baglanti import baglanti_ac


def test_yabanci_anahtar_kontrolu_acik_olur(tmp_path: Path) -> None:
    baglanti = baglanti_ac(tmp_path / "deneme.db")
    baglanti.execute("CREATE TABLE ana (id INTEGER PRIMARY KEY)")
    baglanti.execute("CREATE TABLE cocuk (ana_id INTEGER REFERENCES ana (id))")
    with pytest.raises(sqlite3.IntegrityError):
        baglanti.execute("INSERT INTO cocuk (ana_id) VALUES (?)", (99,))
    baglanti.close()


def test_satirlara_sutun_adiyla_erisilir(tmp_path: Path) -> None:
    baglanti = baglanti_ac(tmp_path / "deneme.db")
    satir = baglanti.execute("SELECT 5 AS sayi").fetchone()
    assert satir["sayi"] == 5
    baglanti.close()


def test_eksik_klasor_olusturulur(tmp_path: Path) -> None:
    yol = tmp_path / "yeni" / "klasor" / "deneme.db"
    baglanti_ac(yol).close()
    assert yol.exists()
