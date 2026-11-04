"""Kullanici giris penceresi ve ilk acilista eczaci hesabi olusturma penceresi."""

import logging

import psycopg
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ayarlar import VeritabaniAyari
from moduller.kullanici.servis import (
    Kullanici,
    KullaniciHatasi,
    Rol,
    giris_dogrula,
    kullanici_olustur,
)
from veritabani.baglanti import baglanti_ac

_log = logging.getLogger(__name__)

_VERITABANI_HATA_MESAJI = "Ana makineye ulaşılamadı. Lütfen tekrar deneyin."


def _parola_alani_olustur() -> QLineEdit:
    alan = QLineEdit()
    alan.setEchoMode(QLineEdit.EchoMode.Password)
    return alan


def _hata_etiketi_olustur() -> QLabel:
    etiket = QLabel()
    etiket.setStyleSheet("color: #b00020;")
    etiket.setWordWrap(True)
    return etiket


class GirisPenceresi(QDialog):
    def __init__(self, veritabani_ayari: VeritabaniAyari) -> None:
        super().__init__()
        self.veritabani_ayari = veritabani_ayari
        self.kullanici: Kullanici | None = None
        self.setWindowTitle("MezgilPharma - Giriş")

        self.kullanici_adi_alani = QLineEdit()
        self.parola_alani = _parola_alani_olustur()
        self.hata_etiketi = _hata_etiketi_olustur()
        self.giris_dugmesi = QPushButton("Giriş Yap")
        self.giris_dugmesi.setDefault(True)
        cikis_dugmesi = QPushButton("Çıkış")
        cikis_dugmesi.setAutoDefault(False)

        form = QFormLayout()
        form.addRow("Kullanıcı adı:", self.kullanici_adi_alani)
        form.addRow("Parola:", self.parola_alani)
        dugmeler = QHBoxLayout()
        dugmeler.addStretch()
        dugmeler.addWidget(cikis_dugmesi)
        dugmeler.addWidget(self.giris_dugmesi)
        duzen = QVBoxLayout(self)
        duzen.addLayout(form)
        duzen.addWidget(self.hata_etiketi)
        duzen.addLayout(dugmeler)

        self.giris_dugmesi.clicked.connect(self._giris_yap)
        cikis_dugmesi.clicked.connect(self.reject)

    def _giris_yap(self) -> None:
        try:
            # Her denemede yeni baglanti: ag kopup geri gelince tekrar denenebilsin.
            with baglanti_ac(self.veritabani_ayari) as baglanti:
                kullanici = giris_dogrula(
                    baglanti,
                    self.kullanici_adi_alani.text(),
                    self.parola_alani.text(),
                )
        except psycopg.Error:
            _log.exception("Giris sirasinda veritabani hatasi")
            self.hata_etiketi.setText(_VERITABANI_HATA_MESAJI)
            return

        if kullanici is None:
            # Kullanici adi loga yazilmaz: yanlislikla parola yazilmis olabilir.
            _log.warning("Basarisiz giris denemesi")
            self.hata_etiketi.setText("Kullanıcı adı veya parola hatalı.")
            self.parola_alani.clear()
            self.parola_alani.setFocus()
            return

        _log.info("Giris yapildi: kullanici_id=%s", kullanici.id)
        self.kullanici = kullanici
        self.accept()


class IlkKullaniciPenceresi(QDialog):
    def __init__(self, veritabani_ayari: VeritabaniAyari) -> None:
        super().__init__()
        self._veritabani_ayari = veritabani_ayari
        self.setWindowTitle("MezgilPharma - İlk Kurulum")

        aciklama = QLabel(
            "Programda henüz kullanıcı yok. Lütfen eczacı hesabını oluşturun.\n"
            "Parolayı unutmayın: şu an parola sıfırlama özelliği yoktur."
        )
        aciklama.setWordWrap(True)
        self.ad_soyad_alani = QLineEdit()
        self.kullanici_adi_alani = QLineEdit()
        self.parola_alani = _parola_alani_olustur()
        self.parola_tekrar_alani = _parola_alani_olustur()
        self.hata_etiketi = _hata_etiketi_olustur()
        self.kaydet_dugmesi = QPushButton("Hesabı Oluştur")
        self.kaydet_dugmesi.setDefault(True)
        cikis_dugmesi = QPushButton("Çıkış")
        cikis_dugmesi.setAutoDefault(False)

        form = QFormLayout()
        form.addRow("Ad soyad:", self.ad_soyad_alani)
        form.addRow("Kullanıcı adı:", self.kullanici_adi_alani)
        form.addRow("Parola:", self.parola_alani)
        form.addRow("Parola (tekrar):", self.parola_tekrar_alani)
        dugmeler = QHBoxLayout()
        dugmeler.addStretch()
        dugmeler.addWidget(cikis_dugmesi)
        dugmeler.addWidget(self.kaydet_dugmesi)
        duzen = QVBoxLayout(self)
        duzen.addWidget(aciklama)
        duzen.addLayout(form)
        duzen.addWidget(self.hata_etiketi)
        duzen.addLayout(dugmeler)

        self.kaydet_dugmesi.clicked.connect(self._kaydet)
        cikis_dugmesi.clicked.connect(self.reject)

    def _kaydet(self) -> None:
        if self.parola_alani.text() != self.parola_tekrar_alani.text():
            self.hata_etiketi.setText("Parolalar aynı değil.")
            return
        try:
            with baglanti_ac(self._veritabani_ayari) as baglanti:
                kullanici_olustur(
                    baglanti,
                    self.kullanici_adi_alani.text(),
                    self.ad_soyad_alani.text(),
                    self.parola_alani.text(),
                    Rol.ECZACI,
                )
        except KullaniciHatasi as hata:
            self.hata_etiketi.setText(str(hata))
            return
        except psycopg.Error:
            _log.exception("Ilk kullanici olusturulurken veritabani hatasi")
            self.hata_etiketi.setText(_VERITABANI_HATA_MESAJI)
            return
        self.accept()
