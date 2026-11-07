"""Stok girisi, stok detayi ve depolar ekranlari."""

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from arayuz.ortak import hata_etiketi_olustur, islemi_calistir
from ayarlar import VeritabaniAyari
from moduller.hatalar import GorunurHata
from moduller.ilac.servis import Urun, urun_ara
from moduller.kullanici.servis import Kullanici, Rol
from moduller.para import para_coz, para_metni, yuvarla
from moduller.stok.kurallar import MALIYET_ONDALIGI, skt_coz
from moduller.stok.servis import (
    Hareket,
    HareketTuru,
    OnayGerekli,
    Parti,
    StokGirisi,
    Tedarikci,
    hareketleri_getir,
    partileri_getir,
    stok_girisi_yap,
    tedarikci_aktif_yap,
    tedarikci_ekle,
    tedarikci_pasif_yap,
    tedarikcileri_listele,
)
from veritabani.baglanti import Baglanti

_AZAMI_ADET = 100_000


def _tablo_olustur(basliklar: list[str]) -> QTableWidget:
    tablo = QTableWidget(0, len(basliklar))
    tablo.setHorizontalHeaderLabels(basliklar)
    tablo.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    tablo.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    tablo.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    return tablo


def _tabloyu_doldur(tablo: QTableWidget, satirlar: list[list[str]]) -> None:
    tablo.clearSelection()
    tablo.setRowCount(len(satirlar))
    for satir, degerler in enumerate(satirlar):
        for sutun, deger in enumerate(degerler):
            tablo.setItem(satir, sutun, QTableWidgetItem(deger))
    tablo.resizeColumnsToContents()


def _yeni_depo_sor(ust: QDialog, ayar: VeritabaniAyari, yapan: Kullanici, hata: QLabel) -> int | None:
    """Depo adini sorar ve ekler; eklenen deponun numarasini dondurur."""
    ad, tamam = QInputDialog.getText(ust, "Yeni depo", "Depo adı:")
    if not tamam or not ad.strip():
        return None
    eklenen: list[int] = []
    if islemi_calistir(ayar, hata, lambda b: eklenen.append(tedarikci_ekle(b, yapan, ad))):
        return eklenen[0]
    return None


class StokGirisiPenceresi(QDialog):
    """Faturadan stok girisi. 'Kaydet ve Yeni Satir' depo ve faturayi korur."""

    def __init__(
        self, veritabani_ayari: VeritabaniAyari, yapan: Kullanici, urun: Urun | None = None
    ) -> None:
        super().__init__()
        self._veritabani_ayari = veritabani_ayari
        self._yapan = yapan
        self.setWindowTitle("MezgilPharma - Stok Girişi")

        self.tur_secimi = QComboBox()
        self.tur_secimi.addItem(HareketTuru.GIRIS.gorunen_ad, HareketTuru.GIRIS)
        if yapan.rol is Rol.ECZACI:
            self.tur_secimi.addItem(HareketTuru.ACILIS.gorunen_ad, HareketTuru.ACILIS)
        self.depo_secimi = QComboBox()
        self.yeni_depo_dugmesi = QPushButton("Yeni Depo")
        self.fatura_alani = QLineEdit()
        self.urun_alani = QLineEdit()
        self.urun_alani.setPlaceholderText("Barkod okutun veya ad yazıp Enter'a basın")
        self.urun_secimi = QComboBox()
        self.parti_alani = QLineEdit()
        self.skt_alani = QLineEdit()
        self.skt_alani.setPlaceholderText("31.01.2030 veya 01.2030")
        self.alinan_alani = QSpinBox()
        self.alinan_alani.setRange(0, _AZAMI_ADET)
        self.mf_alani = QSpinBox()
        self.mf_alani.setRange(0, _AZAMI_ADET)
        self.birim_fiyat_alani = QLineEdit()
        self.birim_fiyat_alani.setPlaceholderText("KDV hariç, iskontolu net birim fiyat")
        self.toplam_alani = QLineEdit()
        self.toplam_alani.setPlaceholderText("Faturadaki satır tutarıyla karşılaştırın")
        self.hata_etiketi = hata_etiketi_olustur()
        self.bilgi_etiketi = QLabel()
        self.kaydet_dugmesi = QPushButton("Kaydet")
        self.kaydet_yeni_dugmesi = QPushButton("Kaydet ve Yeni Satır")
        kapat_dugmesi = QPushButton("Kapat")

        depo_satiri = QHBoxLayout()
        depo_satiri.addWidget(self.depo_secimi, 1)
        depo_satiri.addWidget(self.yeni_depo_dugmesi)
        form = QFormLayout()
        form.addRow("Giriş türü:", self.tur_secimi)
        form.addRow("Depo:", depo_satiri)
        form.addRow("Fatura no:", self.fatura_alani)
        form.addRow("Ürün ara:", self.urun_alani)
        form.addRow("Ürün:", self.urun_secimi)
        form.addRow("Parti no:", self.parti_alani)
        form.addRow("SKT:", self.skt_alani)
        form.addRow("Alınan adet:", self.alinan_alani)
        form.addRow("Mal fazlası (MF):", self.mf_alani)
        form.addRow("Birim fiyat (TL):", self.birim_fiyat_alani)
        form.addRow("Satır toplamı (TL):", self.toplam_alani)
        dugmeler = QHBoxLayout()
        dugmeler.addStretch()
        for dugme in (kapat_dugmesi, self.kaydet_yeni_dugmesi, self.kaydet_dugmesi):
            dugme.setAutoDefault(False)
            dugmeler.addWidget(dugme)
        self.yeni_depo_dugmesi.setAutoDefault(False)
        duzen = QVBoxLayout(self)
        duzen.addLayout(form)
        duzen.addWidget(self.hata_etiketi)
        duzen.addWidget(self.bilgi_etiketi)
        duzen.addLayout(dugmeler)

        self.tur_secimi.currentIndexChanged.connect(self._tur_degisti)
        self.yeni_depo_dugmesi.clicked.connect(self._yeni_depo)
        self.urun_alani.returnPressed.connect(self._urun_bul)
        self.birim_fiyat_alani.textChanged.connect(self._toplami_hesapla)
        self.alinan_alani.valueChanged.connect(self._toplami_hesapla)
        self.kaydet_dugmesi.clicked.connect(self._kaydet)
        self.kaydet_yeni_dugmesi.clicked.connect(self._kaydet_ve_yeni)
        kapat_dugmesi.clicked.connect(self.reject)

        self._depolari_yukle()
        if urun is not None:
            self._urunleri_goster([urun])

    def _depolari_yukle(self, secilecek: int | None = None) -> None:
        depolar: list[Tedarikci] = []

        def _oku(baglanti: Baglanti) -> None:
            depolar.extend(tedarikcileri_listele(baglanti, self._yapan))

        if not islemi_calistir(self._veritabani_ayari, self.hata_etiketi, _oku):
            return
        onceki = self.depo_secimi.currentData() if secilecek is None else secilecek
        self.depo_secimi.clear()
        for depo in depolar:
            self.depo_secimi.addItem(depo.ad, depo.id)
        indeks = self.depo_secimi.findData(onceki)
        if indeks >= 0:
            self.depo_secimi.setCurrentIndex(indeks)

    def _yeni_depo(self) -> None:
        self.hata_etiketi.clear()
        depo_id = _yeni_depo_sor(self, self._veritabani_ayari, self._yapan, self.hata_etiketi)
        if depo_id is not None:
            self._depolari_yukle(secilecek=depo_id)

    def _tur_degisti(self) -> None:
        faturali = self.tur_secimi.currentData() is HareketTuru.GIRIS
        for alan in (self.depo_secimi, self.yeni_depo_dugmesi, self.fatura_alani, self.mf_alani):
            alan.setEnabled(faturali)
        if not faturali:
            self.mf_alani.setValue(0)
            self.fatura_alani.clear()

    def _urunleri_goster(self, urunler: list[Urun]) -> None:
        self.urun_secimi.clear()
        for urun in urunler:
            barkod = f" ({urun.gtin})" if urun.gtin else ""
            self.urun_secimi.addItem(f"{urun.ad}{barkod}", urun.id)

    def _urun_bul(self) -> None:
        self.hata_etiketi.clear()
        bulunan: list[Urun] = []

        def _ara(baglanti: Baglanti) -> None:
            bulunan.extend(urun_ara(baglanti, self._yapan, self.urun_alani.text(), limit=50))

        if not islemi_calistir(self._veritabani_ayari, self.hata_etiketi, _ara):
            return
        self._urunleri_goster(bulunan)
        if not bulunan:
            self.hata_etiketi.setText("Ürün bulunamadı. Önce ürün kartını açın.")
        else:
            self.parti_alani.setFocus()

    def _toplami_hesapla(self) -> None:
        """Birim fiyat x alinan adet; kullanici faturadaki rakamla duzeltebilir."""
        try:
            birim = para_coz(self.birim_fiyat_alani.text(), "Birim fiyat", ondalik=MALIYET_ONDALIGI)
        except GorunurHata:
            return
        self.toplam_alani.setText(para_metni(yuvarla(birim * self.alinan_alani.value(), 2)))

    def _giris_oku(self) -> StokGirisi:
        urun_id = self.urun_secimi.currentData()
        if urun_id is None:
            raise GorunurHata("Lütfen bir ürün seçin.")
        tur: HareketTuru = self.tur_secimi.currentData()
        faturali = tur is HareketTuru.GIRIS
        return StokGirisi(
            urun_id=urun_id,
            tur=tur,
            parti_no=self.parti_alani.text(),
            skt=skt_coz(self.skt_alani.text()),
            alinan_adet=self.alinan_alani.value(),
            mf_adet=self.mf_alani.value() if faturali else 0,
            toplam_tutar=para_coz(self.toplam_alani.text(), "Satır toplamı"),
            tedarikci_id=self.depo_secimi.currentData() if faturali else None,
            fatura_no=self.fatura_alani.text() if faturali else None,
        )

    def _yaz(self) -> bool:
        self.hata_etiketi.clear()
        try:
            giris = self._giris_oku()
        except GorunurHata as hata:
            self.hata_etiketi.setText(str(hata))
            return False
        uyarilar: list[str] = []

        def _gir(baglanti: Baglanti, onayli: bool) -> None:
            # OnayGerekli burada yakalanir; yoksa ortak yakalayici onu hata sanip etikete yazar.
            try:
                stok_girisi_yap(baglanti, self._yapan, giris, uyarilar_onaylandi=onayli)
            except OnayGerekli as uyari:
                uyarilar.extend(uyari.uyarilar)

        if not islemi_calistir(self._veritabani_ayari, self.hata_etiketi, lambda b: _gir(b, False)):
            return False
        if not uyarilar:
            return True
        if not self._uyarilari_onayla(uyarilar):
            return False
        uyarilar.clear()
        return islemi_calistir(
            self._veritabani_ayari, self.hata_etiketi, lambda b: _gir(b, True)
        ) and not uyarilar

    def _uyarilari_onayla(self, uyarilar: list[str]) -> bool:
        yanit = QMessageBox.question(
            self,
            "Onay gerekiyor",
            "\n".join(f"• {uyari}" for uyari in uyarilar) + "\n\nYine de kaydedilsin mi?",
        )
        return yanit == QMessageBox.StandardButton.Yes

    def _kaydet(self) -> None:
        if self._yaz():
            self.accept()

    def _kaydet_ve_yeni(self) -> None:
        urun_adi = self.urun_secimi.currentText()
        miktar = self.alinan_alani.value() + self.mf_alani.value()
        if not self._yaz():
            return
        self.bilgi_etiketi.setText(f"Kaydedildi: {urun_adi}, {miktar} kutu.")
        for alan in (
            self.urun_alani,
            self.parti_alani,
            self.skt_alani,
            self.birim_fiyat_alani,
            self.toplam_alani,
        ):
            alan.clear()
        self.urun_secimi.clear()
        self.alinan_alani.setValue(0)
        self.mf_alani.setValue(0)
        self.urun_alani.setFocus()


class StokDetayiPenceresi(QDialog):
    """Urunun partileri ve hareketleri. Personel alis fiyatini goremez."""

    def __init__(self, veritabani_ayari: VeritabaniAyari, yapan: Kullanici, urun: Urun) -> None:
        super().__init__()
        self.setWindowTitle(f"MezgilPharma - Stok Detayı: {urun.ad}")
        self.resize(900, 560)
        eczaci = yapan.rol is Rol.ECZACI

        parti_basliklari = ["Parti no", "SKT", "Miktar"] + (["Birim maliyet"] if eczaci else [])
        hareket_basliklari = [
            "Tarih", "İşlem", "Parti no", "SKT", "Miktar", "Alınan", "MF", "Depo",
            "Fatura no", "Kullanıcı",
        ] + (["Tutar"] if eczaci else [])
        self.parti_tablosu = _tablo_olustur(parti_basliklari)
        self.hareket_tablosu = _tablo_olustur(hareket_basliklari)
        self.hata_etiketi = hata_etiketi_olustur()
        kapat_dugmesi = QPushButton("Kapat")
        kapat_dugmesi.clicked.connect(self.accept)

        duzen = QVBoxLayout(self)
        duzen.addWidget(QLabel("Partiler (en yakın SKT üstte)"))
        duzen.addWidget(self.parti_tablosu)
        duzen.addWidget(QLabel("Hareketler (en yeni üstte)"))
        duzen.addWidget(self.hareket_tablosu, 1)
        duzen.addWidget(self.hata_etiketi)
        duzen.addWidget(kapat_dugmesi)

        partiler: list[Parti] = []
        hareketler: list[Hareket] = []

        def _oku(baglanti: Baglanti) -> None:
            partiler.extend(partileri_getir(baglanti, yapan, urun.id))
            hareketler.extend(hareketleri_getir(baglanti, yapan, urun.id))

        if not islemi_calistir(veritabani_ayari, self.hata_etiketi, _oku):
            return
        _tabloyu_doldur(
            self.parti_tablosu,
            [
                [p.parti_no or "-", f"{p.skt:%d.%m.%Y}", str(p.miktar)]
                + ([para_metni(p.birim_maliyet)] if p.birim_maliyet is not None else [])
                for p in partiler
            ],
        )
        _tabloyu_doldur(
            self.hareket_tablosu,
            [
                [
                    f"{h.tarih:%d.%m.%Y %H:%M}",
                    h.tur.gorunen_ad,
                    h.parti_no or "-",
                    f"{h.skt:%d.%m.%Y}",
                    str(h.miktar),
                    "-" if h.alinan_adet is None else str(h.alinan_adet),
                    "-" if h.mf_adet is None else str(h.mf_adet),
                    h.tedarikci_adi or "-",
                    h.fatura_no or "-",
                    h.kullanici_adi,
                ]
                + ([para_metni(h.toplam_tutar)] if h.toplam_tutar is not None else [])
                for h in hareketler
            ],
        )


class DepolarPenceresi(QDialog):
    """Depo listesi. Herkes ekler; pasif yapmayi yalnizca eczaci yapar."""

    def __init__(self, veritabani_ayari: VeritabaniAyari, yapan: Kullanici) -> None:
        super().__init__()
        self._veritabani_ayari = veritabani_ayari
        self._yapan = yapan
        self._eczaci = yapan.rol is Rol.ECZACI
        self._liste: list[Tedarikci] = []
        self.setWindowTitle("MezgilPharma - Depolar")
        self.resize(480, 400)

        self.tablo = _tablo_olustur(["Depo", "Durum"])
        self.hata_etiketi = hata_etiketi_olustur()
        self.yeni_dugmesi = QPushButton("Yeni Depo")
        self.pasif_aktif_dugmesi = QPushButton("Pasif Yap")
        kapat_dugmesi = QPushButton("Kapat")
        dugmeler = QHBoxLayout()
        for dugme in (self.yeni_dugmesi, self.pasif_aktif_dugmesi, kapat_dugmesi):
            dugme.setAutoDefault(False)
        dugmeler.addWidget(self.yeni_dugmesi)
        dugmeler.addWidget(self.pasif_aktif_dugmesi)
        dugmeler.addStretch()
        dugmeler.addWidget(kapat_dugmesi)
        duzen = QVBoxLayout(self)
        duzen.addWidget(self.tablo)
        duzen.addWidget(self.hata_etiketi)
        duzen.addLayout(dugmeler)

        self.pasif_aktif_dugmesi.setVisible(self._eczaci)
        self.tablo.itemSelectionChanged.connect(self._secim_degisti)
        self.yeni_dugmesi.clicked.connect(self._yeni)
        self.pasif_aktif_dugmesi.clicked.connect(self._pasif_aktif)
        kapat_dugmesi.clicked.connect(self.accept)

        self._yenile()

    def _yenile(self) -> None:
        liste: list[Tedarikci] = []

        def _oku(baglanti: Baglanti) -> None:
            liste.extend(tedarikcileri_listele(baglanti, self._yapan, pasifler_dahil=self._eczaci))

        if not islemi_calistir(self._veritabani_ayari, self.hata_etiketi, _oku):
            return
        self._liste = liste
        _tabloyu_doldur(self.tablo, [[d.ad, "Aktif" if d.aktif else "Pasif"] for d in liste])

    def _secili(self) -> Tedarikci | None:
        secilenler = self.tablo.selectedItems()
        return self._liste[secilenler[0].row()] if secilenler else None

    def _secim_degisti(self) -> None:
        depo = self._secili()
        pasif = depo is not None and not depo.aktif
        self.pasif_aktif_dugmesi.setText("Aktif Yap" if pasif else "Pasif Yap")

    def _yeni(self) -> None:
        self.hata_etiketi.clear()
        if _yeni_depo_sor(self, self._veritabani_ayari, self._yapan, self.hata_etiketi) is not None:
            self._yenile()

    def _pasif_aktif(self) -> None:
        self.hata_etiketi.clear()
        depo = self._secili()
        if depo is None:
            self.hata_etiketi.setText("Lütfen listeden bir depo seçin.")
            return
        if depo.aktif:
            yanit = QMessageBox.question(
                self,
                "Depoyu pasif yap",
                f"{depo.ad} pasif yapılsın mı? Stok girişinde artık seçilemez.",
            )
            if yanit != QMessageBox.StandardButton.Yes:
                return
        islem = tedarikci_pasif_yap if depo.aktif else tedarikci_aktif_yap
        if islemi_calistir(
            self._veritabani_ayari,
            self.hata_etiketi,
            lambda b: islem(b, self._yapan, depo.id),
        ):
            self._yenile()
