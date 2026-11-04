"""Parola degistirme penceresi ve eczacinin kullanici yonetimi ekranlari."""

import logging
from collections.abc import Callable

import psycopg
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from arayuz.giris_penceresi import (
    PAROLALAR_AYNI_DEGIL_MESAJI,
    VERITABANI_HATA_MESAJI,
    hata_etiketi_olustur,
    parola_alani_olustur,
)
from ayarlar import VeritabaniAyari
from moduller.kullanici.servis import (
    Kullanici,
    KullaniciHatasi,
    KullaniciOzeti,
    Rol,
    aktif_yap,
    kilit_ac,
    kullanicilari_listele,
    parola_degistir,
    parola_sifirla,
    pasif_yap,
    personel_ekle,
)
from veritabani.baglanti import Baglanti, baglanti_ac

_log = logging.getLogger(__name__)

_SUTUNLAR = ("Ad soyad", "Kullanıcı adı", "Rol", "Durum")


def _islemi_calistir(
    ayar: VeritabaniAyari, hata_etiketi: QLabel, islem: Callable[[Baglanti], object]
) -> bool:
    """Veritabani islemini yapar; hatayi etikette Turkce gosterir, teknik ayrinti loga gider."""
    try:
        with baglanti_ac(ayar) as baglanti:
            islem(baglanti)
    except KullaniciHatasi as hata:
        hata_etiketi.setText(str(hata))
        return False
    except psycopg.Error:
        _log.exception("Kullanici isleminde veritabani hatasi")
        hata_etiketi.setText(VERITABANI_HATA_MESAJI)
        return False
    return True


def _dugmeler_olustur(iptal: QPushButton, kaydet: QPushButton) -> QHBoxLayout:
    kaydet.setDefault(True)
    iptal.setAutoDefault(False)
    dugmeler = QHBoxLayout()
    dugmeler.addStretch()
    dugmeler.addWidget(iptal)
    dugmeler.addWidget(kaydet)
    return dugmeler


class ParolaDegistirPenceresi(QDialog):
    def __init__(
        self,
        veritabani_ayari: VeritabaniAyari,
        kullanici: Kullanici,
        *,
        zorunlu: bool = False,
    ) -> None:
        super().__init__()
        self._veritabani_ayari = veritabani_ayari
        self.kullanici = kullanici
        self.zorunlu = zorunlu
        self.setWindowTitle("MezgilPharma - Parola Değiştir")

        self.aciklama_etiketi = QLabel(
            "Programı kullanmadan önce kendi parolanızı belirlemelisiniz." if zorunlu else ""
        )
        self.aciklama_etiketi.setWordWrap(True)
        self.aciklama_etiketi.setVisible(zorunlu)
        self.mevcut_parola_alani = parola_alani_olustur()
        self.yeni_parola_alani = parola_alani_olustur()
        self.yeni_parola_tekrar_alani = parola_alani_olustur()
        self.hata_etiketi = hata_etiketi_olustur()
        self.kaydet_dugmesi = QPushButton("Kaydet")
        iptal_dugmesi = QPushButton("Çıkış" if zorunlu else "Vazgeç")

        form = QFormLayout()
        form.addRow("Mevcut parola:", self.mevcut_parola_alani)
        form.addRow("Yeni parola:", self.yeni_parola_alani)
        form.addRow("Yeni parola (tekrar):", self.yeni_parola_tekrar_alani)
        duzen = QVBoxLayout(self)
        duzen.addWidget(self.aciklama_etiketi)
        duzen.addLayout(form)
        duzen.addWidget(self.hata_etiketi)
        duzen.addLayout(_dugmeler_olustur(iptal_dugmesi, self.kaydet_dugmesi))

        self.kaydet_dugmesi.clicked.connect(self._kaydet)
        iptal_dugmesi.clicked.connect(self.reject)

    def _kaydet(self) -> None:
        yeni = self.yeni_parola_alani.text()
        if yeni != self.yeni_parola_tekrar_alani.text():
            self.hata_etiketi.setText(PAROLALAR_AYNI_DEGIL_MESAJI)
            return
        mevcut = self.mevcut_parola_alani.text()
        tamam = _islemi_calistir(
            self._veritabani_ayari,
            self.hata_etiketi,
            lambda baglanti: parola_degistir(baglanti, self.kullanici, mevcut, yeni),
        )
        if tamam:
            self.accept()
        else:
            self.mevcut_parola_alani.clear()
            self.mevcut_parola_alani.setFocus()


class KullaniciEklePenceresi(QDialog):
    def __init__(self, veritabani_ayari: VeritabaniAyari, yapan: Kullanici) -> None:
        super().__init__()
        self._veritabani_ayari = veritabani_ayari
        self._yapan = yapan
        self.setWindowTitle("MezgilPharma - Yeni Kullanıcı")

        aciklama = QLabel(
            "Geçici parolayı kişiye iletin. İlk girişte kendi parolasını belirlemesi istenir."
        )
        aciklama.setWordWrap(True)
        self.ad_soyad_alani = QLineEdit()
        self.kullanici_adi_alani = QLineEdit()
        self.rol_secimi = QComboBox()
        self.rol_secimi.addItem(Rol.PERSONEL.gorunen_ad, Rol.PERSONEL)
        self.rol_secimi.addItem(Rol.ECZACI.gorunen_ad, Rol.ECZACI)
        self.parola_alani = parola_alani_olustur()
        self.parola_tekrar_alani = parola_alani_olustur()
        self.hata_etiketi = hata_etiketi_olustur()
        self.kaydet_dugmesi = QPushButton("Kullanıcıyı Ekle")
        iptal_dugmesi = QPushButton("Vazgeç")

        form = QFormLayout()
        form.addRow("Ad soyad:", self.ad_soyad_alani)
        form.addRow("Kullanıcı adı:", self.kullanici_adi_alani)
        form.addRow("Rol:", self.rol_secimi)
        form.addRow("Geçici parola:", self.parola_alani)
        form.addRow("Geçici parola (tekrar):", self.parola_tekrar_alani)
        duzen = QVBoxLayout(self)
        duzen.addWidget(aciklama)
        duzen.addLayout(form)
        duzen.addWidget(self.hata_etiketi)
        duzen.addLayout(_dugmeler_olustur(iptal_dugmesi, self.kaydet_dugmesi))

        self.kaydet_dugmesi.clicked.connect(self._kaydet)
        iptal_dugmesi.clicked.connect(self.reject)

    def _kaydet(self) -> None:
        parola = self.parola_alani.text()
        if parola != self.parola_tekrar_alani.text():
            self.hata_etiketi.setText(PAROLALAR_AYNI_DEGIL_MESAJI)
            return
        rol: Rol = self.rol_secimi.currentData()
        tamam = _islemi_calistir(
            self._veritabani_ayari,
            self.hata_etiketi,
            lambda baglanti: personel_ekle(
                baglanti,
                self._yapan,
                self.kullanici_adi_alani.text(),
                self.ad_soyad_alani.text(),
                parola,
                rol,
            ),
        )
        if tamam:
            self.accept()


class ParolaSifirlaPenceresi(QDialog):
    def __init__(
        self, veritabani_ayari: VeritabaniAyari, yapan: Kullanici, hedef: KullaniciOzeti
    ) -> None:
        super().__init__()
        self._veritabani_ayari = veritabani_ayari
        self._yapan = yapan
        self.hedef = hedef
        self.setWindowTitle("MezgilPharma - Parola Sıfırla")

        aciklama = QLabel(
            f"{hedef.ad_soyad} için geçici parola belirleyin. "
            "İlk girişte kendi parolasını belirlemesi istenir."
        )
        aciklama.setWordWrap(True)
        self.parola_alani = parola_alani_olustur()
        self.parola_tekrar_alani = parola_alani_olustur()
        self.hata_etiketi = hata_etiketi_olustur()
        self.kaydet_dugmesi = QPushButton("Parolayı Sıfırla")
        iptal_dugmesi = QPushButton("Vazgeç")

        form = QFormLayout()
        form.addRow("Geçici parola:", self.parola_alani)
        form.addRow("Geçici parola (tekrar):", self.parola_tekrar_alani)
        duzen = QVBoxLayout(self)
        duzen.addWidget(aciklama)
        duzen.addLayout(form)
        duzen.addWidget(self.hata_etiketi)
        duzen.addLayout(_dugmeler_olustur(iptal_dugmesi, self.kaydet_dugmesi))

        self.kaydet_dugmesi.clicked.connect(self._kaydet)
        iptal_dugmesi.clicked.connect(self.reject)

    def _kaydet(self) -> None:
        parola = self.parola_alani.text()
        if parola != self.parola_tekrar_alani.text():
            self.hata_etiketi.setText(PAROLALAR_AYNI_DEGIL_MESAJI)
            return
        tamam = _islemi_calistir(
            self._veritabani_ayari,
            self.hata_etiketi,
            lambda baglanti: parola_sifirla(baglanti, self._yapan, self.hedef.id, parola),
        )
        if tamam:
            self.accept()


def _durum_metni(ozet: KullaniciOzeti) -> str:
    if not ozet.aktif:
        return "Pasif"
    return "Kilitli" if ozet.kilitli else "Aktif"


class KullanicilarPenceresi(QDialog):
    """Yalnizca eczaciya acilir; yetki ayrica her islemde veritabanindan denetlenir."""

    def __init__(self, veritabani_ayari: VeritabaniAyari, yapan: Kullanici) -> None:
        super().__init__()
        self._veritabani_ayari = veritabani_ayari
        self._yapan = yapan
        self._liste: list[KullaniciOzeti] = []
        self.setWindowTitle("MezgilPharma - Kullanıcılar")
        self.resize(640, 400)

        self.tablo = QTableWidget(0, len(_SUTUNLAR))
        self.tablo.setHorizontalHeaderLabels(_SUTUNLAR)
        self.tablo.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tablo.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tablo.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.hata_etiketi = hata_etiketi_olustur()

        self.yeni_dugmesi = QPushButton("Yeni Kullanıcı")
        self.sifirla_dugmesi = QPushButton("Parola Sıfırla")
        self.kilit_ac_dugmesi = QPushButton("Kilidi Aç")
        self.pasif_aktif_dugmesi = QPushButton("Pasif Yap")
        kapat_dugmesi = QPushButton("Kapat")

        dugmeler = QHBoxLayout()
        for dugme in (
            self.yeni_dugmesi,
            self.sifirla_dugmesi,
            self.kilit_ac_dugmesi,
            self.pasif_aktif_dugmesi,
        ):
            dugme.setAutoDefault(False)
            dugmeler.addWidget(dugme)
        dugmeler.addStretch()
        kapat_dugmesi.setAutoDefault(False)
        dugmeler.addWidget(kapat_dugmesi)
        duzen = QVBoxLayout(self)
        duzen.addWidget(self.tablo)
        duzen.addWidget(self.hata_etiketi)
        duzen.addLayout(dugmeler)

        self.tablo.itemSelectionChanged.connect(self._secim_degisti)
        self.yeni_dugmesi.clicked.connect(self._yeni_kullanici)
        self.sifirla_dugmesi.clicked.connect(self._parola_sifirla)
        self.kilit_ac_dugmesi.clicked.connect(self._kilit_ac)
        self.pasif_aktif_dugmesi.clicked.connect(self._pasif_aktif)
        kapat_dugmesi.clicked.connect(self.accept)

        self._yenile()

    def _yenile(self) -> None:
        def _oku(baglanti: Baglanti) -> None:
            self._liste = kullanicilari_listele(baglanti, self._yapan)

        if not _islemi_calistir(self._veritabani_ayari, self.hata_etiketi, _oku):
            return
        self.tablo.clearSelection()
        self.tablo.setRowCount(len(self._liste))
        for satir, ozet in enumerate(self._liste):
            degerler = (
                ozet.ad_soyad,
                ozet.kullanici_adi,
                ozet.rol.gorunen_ad,
                _durum_metni(ozet),
            )
            for sutun, deger in enumerate(degerler):
                self.tablo.setItem(satir, sutun, QTableWidgetItem(deger))
        self.tablo.resizeColumnsToContents()

    def _secili(self) -> KullaniciOzeti | None:
        secilenler = self.tablo.selectedItems()
        return self._liste[secilenler[0].row()] if secilenler else None

    def _secim_degisti(self) -> None:
        ozet = self._secili()
        pasif = ozet is not None and not ozet.aktif
        self.pasif_aktif_dugmesi.setText("Aktif Yap" if pasif else "Pasif Yap")

    def _secileni_al(self) -> KullaniciOzeti | None:
        self.hata_etiketi.clear()
        ozet = self._secili()
        if ozet is None:
            self.hata_etiketi.setText("Lütfen listeden bir kullanıcı seçin.")
        return ozet

    def _yeni_kullanici(self) -> None:
        self.hata_etiketi.clear()
        pencere = KullaniciEklePenceresi(self._veritabani_ayari, self._yapan)
        if pencere.exec() == QDialog.DialogCode.Accepted:
            self._yenile()

    def _parola_sifirla(self) -> None:
        ozet = self._secileni_al()
        if ozet is None:
            return
        pencere = ParolaSifirlaPenceresi(self._veritabani_ayari, self._yapan, ozet)
        if pencere.exec() == QDialog.DialogCode.Accepted:
            self._yenile()

    def _kilit_ac(self) -> None:
        ozet = self._secileni_al()
        if ozet is None:
            return
        if _islemi_calistir(
            self._veritabani_ayari,
            self.hata_etiketi,
            lambda baglanti: kilit_ac(baglanti, self._yapan, ozet.id),
        ):
            self._yenile()

    def _pasif_aktif(self) -> None:
        ozet = self._secileni_al()
        if ozet is None:
            return
        if ozet.aktif and not self._pasif_onayi(ozet):
            return
        islem = pasif_yap if ozet.aktif else aktif_yap
        if _islemi_calistir(
            self._veritabani_ayari,
            self.hata_etiketi,
            lambda baglanti: islem(baglanti, self._yapan, ozet.id),
        ):
            self._yenile()

    def _pasif_onayi(self, ozet: KullaniciOzeti) -> bool:
        yanit = QMessageBox.question(
            self,
            "Kullanıcıyı pasif yap",
            f"{ozet.ad_soyad} pasif yapılsın mı? Bu kişi artık programa giremez.",
        )
        return yanit == QMessageBox.StandardButton.Yes
