"""Programin ana penceresi. Ortami, veritabani surumunu ve kullaniciyi gosterir."""

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QLabel, QMainWindow, QMenu, QMenuBar, QVBoxLayout, QWidget

from arayuz.kullanici_penceresi import KullanicilarPenceresi, ParolaDegistirPenceresi
from arayuz.urun_penceresi import UrunlerPenceresi
from ayarlar import Ortam, VeritabaniAyari
from moduller.kullanici.servis import Kullanici, Rol


class AnaPencere(QMainWindow):
    def __init__(
        self,
        ortam: Ortam,
        veritabani_surumu: int,
        kullanici: Kullanici,
        veritabani_ayari: VeritabaniAyari,
    ) -> None:
        super().__init__()
        self._kullanici = kullanici
        self._veritabani_ayari = veritabani_ayari
        self.setWindowTitle("MezgilPharma")
        self.resize(800, 500)

        ortam_etiketi = QLabel(f"Ortam: {ortam.value}")
        ortam_etiketi.setObjectName("ortam_etiketi")
        surum_etiketi = QLabel(f"Veritabanı sürümü: {veritabani_surumu}")
        surum_etiketi.setObjectName("surum_etiketi")
        kullanici_etiketi = QLabel(
            f"Kullanıcı: {kullanici.ad_soyad} ({kullanici.rol.gorunen_ad})"
        )
        kullanici_etiketi.setObjectName("kullanici_etiketi")

        icerik = QWidget()
        duzen = QVBoxLayout(icerik)
        duzen.addWidget(ortam_etiketi)
        duzen.addWidget(surum_etiketi)
        duzen.addWidget(kullanici_etiketi)
        duzen.addStretch()
        self.setCentralWidget(icerik)

        menu = QMenu("Hesap", self)
        self.parola_degistir_eylemi = QAction("Parolamı Değiştir", self)
        self.parola_degistir_eylemi.triggered.connect(self._parola_degistir)
        menu.addAction(self.parola_degistir_eylemi)

        # Rol kisitlarindan ayri: personel eczacinin parolasini sifirlayamamalidir.
        self.kullanicilar_eylemi: QAction | None = None
        if kullanici.rol is Rol.ECZACI:
            self.kullanicilar_eylemi = QAction("Kullanıcılar", self)
            self.kullanicilar_eylemi.triggered.connect(self._kullanicilar)
            menu.addAction(self.kullanicilar_eylemi)

        stok_menusu = QMenu("Stok", self)
        self.urunler_eylemi = QAction("Ürünler", self)
        self.urunler_eylemi.triggered.connect(self._urunler)
        stok_menusu.addAction(self.urunler_eylemi)

        cubuk = QMenuBar(self)
        cubuk.addMenu(stok_menusu)
        cubuk.addMenu(menu)
        self.setMenuBar(cubuk)

    def _urunler(self) -> None:
        UrunlerPenceresi(self._veritabani_ayari, self._kullanici).exec()

    def _parola_degistir(self) -> None:
        ParolaDegistirPenceresi(self._veritabani_ayari, self._kullanici).exec()

    def _kullanicilar(self) -> None:
        KullanicilarPenceresi(self._veritabani_ayari, self._kullanici).exec()
