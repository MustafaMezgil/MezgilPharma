"""PostgreSQL baglantisi. Programdaki tum baglantilar buradan acilir."""

import psycopg
from psycopg.rows import DictRow, dict_row

from ayarlar import VeritabaniAyari

Baglanti = psycopg.Connection[DictRow]

_BAGLANTI_ZAMAN_ASIMI_SANIYE = 5
_AYNI_BILGISAYAR = {"localhost", "127.0.0.1", "::1"}


def ssl_modu(sunucu: str) -> str:
    """Ag uzerinden giden baglantida sifreleme zorunludur."""
    return "prefer" if sunucu in _AYNI_BILGISAYAR else "require"


def baglanti_ac(ayar: VeritabaniAyari) -> Baglanti:
    """Baglanti acar. Birden cok komutu tek islem yapmak icin transaction() kullanilir."""
    return Baglanti.connect(
        host=ayar.sunucu,
        port=ayar.port,
        dbname=ayar.veritabani,
        user=ayar.kullanici,
        password=ayar.parola,
        sslmode=ssl_modu(ayar.sunucu),
        connect_timeout=_BAGLANTI_ZAMAN_ASIMI_SANIYE,
        application_name="MezgilPharma",
        autocommit=True,
        row_factory=dict_row,
    )
