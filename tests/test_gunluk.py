import logging
from pathlib import Path

import pytest

from gunluk import gunlugu_baslat


@pytest.mark.usefixtures("temiz_gunluk")
def test_mesaj_log_dosyasina_turkce_karakterle_yazilir(tmp_path: Path) -> None:
    klasor = tmp_path / "logs"
    gunlugu_baslat(klasor)

    logging.getLogger("deneme").error("şğıİçöü bağlantı hatası")

    icerik = (klasor / "eczane.log").read_text(encoding="utf-8")
    assert "şğıİçöü bağlantı hatası" in icerik
