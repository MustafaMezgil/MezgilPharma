"""SQLite baglantisi. Programdaki tum baglantilar buradan acilir."""

import sqlite3
from pathlib import Path


def baglanti_ac(yol: Path) -> sqlite3.Connection:
    yol.parent.mkdir(parents=True, exist_ok=True)
    baglanti = sqlite3.connect(yol)
    baglanti.row_factory = sqlite3.Row
    baglanti.execute("PRAGMA foreign_keys = ON")
    return baglanti
