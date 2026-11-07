"""Programin ana penceresi. Ortami, veritabani surumunu ve kullaniciyi gosterir."""

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from arayuz.kullanici_penceresi import KullanicilarPenceresi, ParolaDegistirPenceresi
from arayuz.ortak import islemi_calistir
from arayuz.stok_penceresi import DepolarPenceresi, StokGirisiPenceresi
from arayuz.urun_penceresi import UrunlerPenceresi
from ayarlar import Ortam, VeritabaniAyari
from moduller.kullanici.servis import Kullanici, Rol
from moduller.stok.servis import miat_uyari_ayi, miat_uyari_ayi_ayarla


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
        self.stok_girisi_eylemi = QAction("Stok Girişi", self)
        self.stok_girisi_eylemi.triggered.connect(self._stok_girisi)
        stok_menusu.addAction(self.stok_girisi_eylemi)
        self.depolar_eylemi = QAction("Depolar", self)
        self.depolar_eylemi.triggered.connect(self._depolar)
        stok_menusu.addAction(self.depolar_eylemi)
        self.miat_ayari_eylemi: QAction | None = None
        if kullanici.rol is Rol.ECZACI:
            self.miat_ayari_eylemi = QAction("Miat Uyarı Süresi", self)
            self.miat_ayari_eylemi.triggered.connect(self._miat_ayari)
            stok_menusu.addAction(self.miat_ayari_eylemi)

        cubuk = QMenuBar(self)
        cubuk.addMenu(stok_menusu)
        cubuk.addMenu(menu)
        self.setMenuBar(cubuk)

    def _urunler(self) -> None:
        UrunlerPenceresi(self._veritabani_ayari, self._kullanici).exec()

    def _stok_girisi(self) -> None:
        StokGirisiPenceresi(self._veritabani_ayari, self._kullanici).exec()

    def _depolar(self) -> None:
        DepolarPenceresi(self._veritabani_ayari, self._kullanici).exec()

    def _miat_ayari(self) -> None:
        baslik = "Miat uyarı süresi"
        hata = QLabel()
        mevcut: list[int] = []
        if not islemi_calistir(
            self._veritabani_ayari,
            hata,
            lambda b: mevcut.append(miat_uyari_ayi(b, self._kullanici)),
        ):
            QMessageBox.warning(self, baslik, hata.text())
            return
        ay, tamam = QInputDialog.getInt(
            self, baslik, "Son kullanma tarihine kaç ay kala uyarılsın?", mevcut[0], 1, 60
        )
        if tamam and not islemi_calistir(
            self._veritabani_ayari,
            hata,
            lambda b: miat_uyari_ayi_ayarla(b, self._kullanici, ay),
        ):
            QMessageBox.warning(self, baslik, hata.text())

    def _parola_degistir(self) -> None:
        ParolaDegistirPenceresi(self._veritabani_ayari, self._kullanici).exec()

    def _kullanicilar(self) -> None:
        KullanicilarPenceresi(self._veritabani_ayari, self._kullanici).exec()
