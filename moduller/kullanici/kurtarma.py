"""Tek eczaci parolasini unutunca gecici parola belirler. YALNIZCA ana makinede calisir.

Calistirmak icin: .venv\\Scripts\\python -m moduller.kullanici.kurtarma
"""

import logging
import sys
from getpass import getpass

import psycopg

from ayarlar import AyarHatasi, ayarlari_yukle
from gunluk import gunlugu_baslat
from moduller.kullanici.servis import (
    KullaniciHatasi,
    Rol,
    gecici_parola_yaz,
    islem_kaydet,
    parola_kurali_dogrula,
)
from veritabani.baglanti import Baglanti, baglanti_ac
from veritabani.migration import MigrationHatasi, surum_dogrula

_log = logging.getLogger(__name__)


def eczaci_parolasi_kurtar(baglanti: Baglanti, kullanici_adi: str, gecici_parola: str) -> None:
    """Aktif eczaciya gecici parola verir; kisi ilk giriste kendi parolasini belirler.

    Personel hesaplari kapsam disidir: onlari eczaci program icinden sifirlar.
    Islemi yapan bir kullanici olmadigindan denetim kaydina hesabin kendisi yazilir;
    islem adi bunun ana makineden yapildigini gosterir.
    """
    parola_kurali_dogrula(gecici_parola)
    with baglanti.transaction():
        satir = baglanti.execute(
            "SELECT id FROM kullanicilar "
            "WHERE kullanici_adi = %s AND aktif AND rol = %s FOR UPDATE",
            (kullanici_adi.strip(), Rol.ECZACI.value),
        ).fetchone()
        if satir is None:
            raise KullaniciHatasi("Bu kullanıcı adıyla aktif bir eczacı bulunamadı.")
        gecici_parola_yaz(baglanti, satir["id"], gecici_parola)
        islem_kaydet(baglanti, satir["id"], "parola_kurtarma_ana_makine", satir["id"])
    _log.warning("Ana makineden parola kurtarma yapildi: kullanici_id=%s", satir["id"])


def _aktif_eczacilari_yaz(baglanti: Baglanti) -> None:
    satirlar = baglanti.execute(
        "SELECT kullanici_adi, ad_soyad FROM kullanicilar "
        "WHERE aktif AND rol = %s ORDER BY kullanici_adi",
        (Rol.ECZACI.value,),
    ).fetchall()
    print("Aktif eczacı hesapları:")
    for satir in satirlar:
        print(f"  {satir['kullanici_adi']} ({satir['ad_soyad']})")


def calistir() -> int:
    try:
        ayarlar = ayarlari_yukle()
        gunlugu_baslat(ayarlar.log_klasoru)
        sahip = ayarlar.sahip
        if sahip is None:
            raise KullaniciHatasi(
                "Parola kurtarma yalnızca ana makinede yapılabilir: "
                "bu bilgisayarda sahip hesabı tanımlı değil."
            )
        print(f"Ortam: {ayarlar.ortam.value}, veritabanı: {sahip.veritabani}")
        with baglanti_ac(sahip) as baglanti:
            surum_dogrula(baglanti)
            _aktif_eczacilari_yaz(baglanti)
            kullanici_adi = input("Kullanıcı adı: ")
            parola = getpass("Geçici parola (yazarken görünmez): ")
            if parola != getpass("Geçici parola (tekrar): "):
                raise KullaniciHatasi("Parolalar aynı değil.")
            eczaci_parolasi_kurtar(baglanti, kullanici_adi, parola)
    except (AyarHatasi, MigrationHatasi, KullaniciHatasi) as hata:
        print(f"HATA: {hata}")
        return 1
    except (psycopg.Error, OSError):
        _log.exception("Parola kurtarma sirasinda baglanti hatasi")
        print("HATA: Veritabanına ulaşılamadı. Ayrıntı log dosyasında.")
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\nİşlem iptal edildi. Değişiklik yapılmadı.")
        return 1

    print("Geçici parola kaydedildi. İlk girişte yeni parola belirlemeniz istenecek.")
    return 0


if __name__ == "__main__":
    sys.exit(calistir())
