"""Urunler listesi ve urun karti ekranlari."""

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from arayuz.ortak import dugmeler_olustur, hata_etiketi_olustur, islemi_calistir
from ayarlar import VeritabaniAyari
from moduller.hatalar import GorunurHata
from moduller.ilac.servis import (
    ARAMA_SINIRI,
    ReceteTuru,
    Urun,
    UrunBilgisi,
    UrunFiyati,
    UrunTuru,
    urun_aktif_yap,
    urun_ara,
    urun_ekle,
    urun_getir,
    urun_guncelle,
    urun_onayla,
    urun_pasif_yap,
)
from arayuz.stok_penceresi import StokDetayiPenceresi, StokGirisiPenceresi
from moduller.kullanici.servis import Kullanici, Rol
from moduller.para import oran_coz, para_coz, para_metni
from veritabani.baglanti import Baglanti

_SUTUNLAR = ("Ürün adı", "Barkod", "Stok", "En yakın SKT", "PSF", "Durum")
_AZAMI_KRITIK_STOK = 1_000_000


class UrunKartiPenceresi(QDialog):
    """Yeni kart acar veya mevcut karti duzenler. Personelde fiyat alanlari kapalidir."""

    def __init__(
        self, veritabani_ayari: VeritabaniAyari, yapan: Kullanici, urun: Urun | None = None
    ) -> None:
        super().__init__()
        self._veritabani_ayari = veritabani_ayari
        self._yapan = yapan
        self._urun = urun
        self.setWindowTitle("MezgilPharma - Ürün Kartı")

        self.ad_alani = QLineEdit()
        self.gtin_alani = QLineEdit()
        self.tur_secimi = QComboBox()
        for tur in UrunTuru:
            self.tur_secimi.addItem(tur.gorunen_ad, tur)
        self.karekodlu_kutusu = QCheckBox("Karekodlu")
        self.recete_secimi = QComboBox()
        for recete in ReceteTuru:
            self.recete_secimi.addItem(recete.gorunen_ad, recete)
        self.etken_madde_alani = QLineEdit()
        self.form_alani = QLineEdit()
        self.atc_alani = QLineEdit()
        self.uretici_alani = QLineEdit()
        self.soguk_zincir_kutusu = QCheckBox("Soğuk zincir")
        self.raf_alani = QLineEdit()
        self.kritik_stok_alani = QSpinBox()
        self.kritik_stok_alani.setRange(0, _AZAMI_KRITIK_STOK)
        self.psf_alani = QLineEdit()
        self.kamu_alani = QLineEdit()
        self.kdv_alani = QLineEdit()
        self.hata_etiketi = hata_etiketi_olustur()
        self.kaydet_dugmesi = QPushButton("Kaydet")
        vazgec_dugmesi = QPushButton("Vazgeç")

        form = QFormLayout()
        form.addRow("Ürün adı:", self.ad_alani)
        form.addRow("Barkod (GTIN):", self.gtin_alani)
        form.addRow("Ürün türü:", self.tur_secimi)
        form.addRow("", self.karekodlu_kutusu)
        form.addRow("Reçete türü:", self.recete_secimi)
        form.addRow("Etken madde:", self.etken_madde_alani)
        form.addRow("Farmasötik form:", self.form_alani)
        form.addRow("ATC kodu:", self.atc_alani)
        form.addRow("Üretici firma:", self.uretici_alani)
        form.addRow("", self.soguk_zincir_kutusu)
        form.addRow("Raf yeri:", self.raf_alani)
        form.addRow("Kritik stok (kutu):", self.kritik_stok_alani)
        form.addRow("PSF (TL):", self.psf_alani)
        form.addRow("Kamu fiyatı (TL):", self.kamu_alani)
        form.addRow("KDV (%):", self.kdv_alani)
        duzen = QVBoxLayout(self)
        duzen.addLayout(form)
        duzen.addWidget(self.hata_etiketi)
        duzen.addLayout(dugmeler_olustur(vazgec_dugmesi, self.kaydet_dugmesi))

        self.tur_secimi.currentIndexChanged.connect(self._tur_degisti)
        self.kaydet_dugmesi.clicked.connect(self._kaydet)
        vazgec_dugmesi.clicked.connect(self.reject)

        if urun is None:
            self.karekodlu_kutusu.setChecked(True)
            self.recete_secimi.setCurrentIndex(self.recete_secimi.findData(ReceteTuru.NORMAL))
        else:
            self._doldur(urun)

        # Son karar her islemde sunucuda verilir; burasi yalnizca ekrani duzenler.
        eczaci = yapan.rol is Rol.ECZACI
        for alan in (self.psf_alani, self.kamu_alani, self.kdv_alani):
            alan.setEnabled(eczaci)
        # Personel bu alanlari yeni kartta doldurur, mevcut kartta degistiremez.
        if urun is not None and not eczaci:
            for alan in (
                self.gtin_alani,
                self.tur_secimi,
                self.karekodlu_kutusu,
                self.recete_secimi,
            ):
                alan.setEnabled(False)

    def _doldur(self, urun: Urun) -> None:
        bilgi = urun.bilgi
        self.ad_alani.setText(bilgi.ad)
        self.gtin_alani.setText(bilgi.gtin or "")
        self.tur_secimi.setCurrentIndex(self.tur_secimi.findData(bilgi.urun_turu))
        self.karekodlu_kutusu.setChecked(bilgi.karekodlu)
        self.recete_secimi.setCurrentIndex(self.recete_secimi.findData(bilgi.recete_turu))
        self.etken_madde_alani.setText(bilgi.etken_madde or "")
        self.form_alani.setText(bilgi.farmasotik_form or "")
        self.atc_alani.setText(bilgi.atc_kodu or "")
        self.uretici_alani.setText(bilgi.uretici_firma or "")
        self.soguk_zincir_kutusu.setChecked(bilgi.soguk_zincir)
        self.raf_alani.setText(bilgi.raf_yeri or "")
        self.kritik_stok_alani.setValue(bilgi.kritik_stok)
        if urun.psf is not None:
            self.psf_alani.setText(para_metni(urun.psf))
        if urun.kamu_fiyati is not None:
            self.kamu_alani.setText(para_metni(urun.kamu_fiyati))
        if urun.kdv_orani is not None:
            self.kdv_alani.setText(para_metni(urun.kdv_orani))

    def _tur_degisti(self) -> None:
        ilac = self.tur_secimi.currentData() is UrunTuru.ILAC
        self.karekodlu_kutusu.setChecked(ilac)
        if not ilac:
            self.recete_secimi.setCurrentIndex(self.recete_secimi.findData(ReceteTuru.RECETESIZ))
        self.recete_secimi.setEnabled(ilac)

    def _bilgi_oku(self) -> UrunBilgisi:
        return UrunBilgisi(
            ad=self.ad_alani.text(),
            gtin=self.gtin_alani.text(),
            urun_turu=self.tur_secimi.currentData(),
            karekodlu=self.karekodlu_kutusu.isChecked(),
            recete_turu=self.recete_secimi.currentData(),
            kritik_stok=self.kritik_stok_alani.value(),
            raf_yeri=self.raf_alani.text(),
            etken_madde=self.etken_madde_alani.text(),
            farmasotik_form=self.form_alani.text(),
            atc_kodu=self.atc_alani.text(),
            uretici_firma=self.uretici_alani.text(),
            soguk_zincir=self.soguk_zincir_kutusu.isChecked(),
        )

    def _fiyat_oku(self) -> UrunFiyati | None:
        """Personelde None. Eczaci yalnizca henuz fiyati olmayan kartta bos gecebilir."""
        if self._yapan.rol is not Rol.ECZACI:
            return None
        psf = self.psf_alani.text().strip()
        kamu = self.kamu_alani.text().strip()
        kdv = self.kdv_alani.text().strip()
        fiyatsiz_kart = self._urun is not None and self._urun.psf is None
        if fiyatsiz_kart and not (psf or kamu or kdv):
            return None
        return UrunFiyati(
            psf=para_coz(psf, "PSF"),
            kamu_fiyati=para_coz(kamu, "Kamu fiyatı") if kamu else None,
            kdv_orani=oran_coz(kdv, "KDV"),
        )

    def _kaydet(self) -> None:
        try:
            fiyat = self._fiyat_oku()
        except GorunurHata as hata:
            self.hata_etiketi.setText(str(hata))
            return
        bilgi = self._bilgi_oku()

        def _yaz(baglanti: Baglanti) -> None:
            if self._urun is None:
                urun_ekle(baglanti, self._yapan, bilgi, fiyat)
            else:
                urun_guncelle(baglanti, self._yapan, self._urun.id, bilgi, fiyat)

        if islemi_calistir(self._veritabani_ayari, self.hata_etiketi, _yaz):
            self.accept()


def _durum_metni(urun: Urun) -> str:
    if not urun.aktif:
        return "Pasif"
    return "Onay bekliyor" if urun.onay_bekliyor else "Aktif"


class UrunlerPenceresi(QDialog):
    def __init__(self, veritabani_ayari: VeritabaniAyari, yapan: Kullanici) -> None:
        super().__init__()
        self._veritabani_ayari = veritabani_ayari
        self._yapan = yapan
        self._liste: list[Urun] = []
        self.setWindowTitle("MezgilPharma - Ürünler")
        self.resize(860, 520)

        self.arama_alani = QLineEdit()
        self.arama_alani.setPlaceholderText("Ad, etken madde, ATC kodu veya barkod")
        self.ara_dugmesi = QPushButton("Ara")
        self.pasifleri_goster = QCheckBox("Pasifleri göster")
        self.onay_bekleyenler = QCheckBox("Yalnızca onay bekleyenler")
        self.tablo = QTableWidget(0, len(_SUTUNLAR))
        self.tablo.setHorizontalHeaderLabels(_SUTUNLAR)
        self.tablo.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tablo.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tablo.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.hata_etiketi = hata_etiketi_olustur()
        self.yeni_dugmesi = QPushButton("Yeni Ürün")
        self.duzenle_dugmesi = QPushButton("Düzenle")
        self.pasif_aktif_dugmesi = QPushButton("Pasif Yap")
        self.onayla_dugmesi = QPushButton("Onayla")
        self.stok_girisi_dugmesi = QPushButton("Stok Girişi")
        self.stok_detayi_dugmesi = QPushButton("Stok Detayı")
        kapat_dugmesi = QPushButton("Kapat")

        ust = QHBoxLayout()
        ust.addWidget(self.arama_alani)
        ust.addWidget(self.ara_dugmesi)
        ust.addWidget(self.pasifleri_goster)
        ust.addWidget(self.onay_bekleyenler)
        alt = QHBoxLayout()
        for dugme in (
            self.ara_dugmesi,
            self.yeni_dugmesi,
            self.duzenle_dugmesi,
            self.pasif_aktif_dugmesi,
            self.onayla_dugmesi,
            self.stok_girisi_dugmesi,
            self.stok_detayi_dugmesi,
            kapat_dugmesi,
        ):
            dugme.setAutoDefault(False)
        alt.addWidget(self.yeni_dugmesi)
        alt.addWidget(self.duzenle_dugmesi)
        alt.addWidget(self.pasif_aktif_dugmesi)
        alt.addWidget(self.onayla_dugmesi)
        alt.addWidget(self.stok_girisi_dugmesi)
        alt.addWidget(self.stok_detayi_dugmesi)
        alt.addStretch()
        alt.addWidget(kapat_dugmesi)
        duzen = QVBoxLayout(self)
        duzen.addLayout(ust)
        duzen.addWidget(self.tablo)
        duzen.addWidget(self.hata_etiketi)
        duzen.addLayout(alt)

        eczaci = yapan.rol is Rol.ECZACI
        for parca in (
            self.pasif_aktif_dugmesi,
            self.pasifleri_goster,
            self.onayla_dugmesi,
            self.onay_bekleyenler,
        ):
            parca.setVisible(eczaci)

        # Barkod okuyucu okuttuktan sonra Enter gonderir: arama hemen calisir.
        self.arama_alani.returnPressed.connect(self._yenile)
        self.ara_dugmesi.clicked.connect(self._yenile)
        self.pasifleri_goster.toggled.connect(self._yenile)
        self.onay_bekleyenler.toggled.connect(self._yenile)
        self.onayla_dugmesi.clicked.connect(self._onayla)
        self.stok_girisi_dugmesi.clicked.connect(self._stok_girisi)
        self.stok_detayi_dugmesi.clicked.connect(self._stok_detayi)
        self.tablo.itemSelectionChanged.connect(self._secim_degisti)
        self.tablo.itemDoubleClicked.connect(self._duzenle)
        self.yeni_dugmesi.clicked.connect(self._yeni)
        self.duzenle_dugmesi.clicked.connect(self._duzenle)
        self.pasif_aktif_dugmesi.clicked.connect(self._pasif_aktif)
        kapat_dugmesi.clicked.connect(self.accept)

        self._yenile()

    def _yenile(self) -> None:
        def _oku(baglanti: Baglanti) -> None:
            self._liste = urun_ara(
                baglanti,
                self._yapan,
                self.arama_alani.text(),
                pasifler_dahil=self.pasifleri_goster.isChecked(),
                yalnizca_onay_bekleyen=self.onay_bekleyenler.isChecked(),
                limit=ARAMA_SINIRI,
            )

        onceki = self._secili()
        self.hata_etiketi.clear()
        if not islemi_calistir(self._veritabani_ayari, self.hata_etiketi, _oku):
            return
        self.tablo.clearSelection()
        self.tablo.setRowCount(len(self._liste))
        for satir, urun in enumerate(self._liste):
            degerler = (
                urun.ad,
                urun.gtin or "-",
                str(urun.stok_miktari),
                urun.en_yakin_skt.strftime("%d.%m.%Y") if urun.en_yakin_skt else "-",
                para_metni(urun.psf) if urun.psf is not None else "Fiyat girilmedi",
                _durum_metni(urun),
            )
            for sutun, deger in enumerate(degerler):
                self.tablo.setItem(satir, sutun, QTableWidgetItem(deger))
        self.tablo.resizeColumnsToContents()
        # Islemden sonra ayni urun secili kalsin; kullanici tekrar aramak zorunda kalmasin.
        if onceki is not None:
            for satir, urun in enumerate(self._liste):
                if urun.id == onceki.id:
                    self.tablo.selectRow(satir)
                    break
        if len(self._liste) >= ARAMA_SINIRI:
            self.hata_etiketi.setText(
                f"İlk {ARAMA_SINIRI} sonuç gösteriliyor. Aramayı daraltın."
            )

    def _secili(self) -> Urun | None:
        secilenler = self.tablo.selectedItems()
        return self._liste[secilenler[0].row()] if secilenler else None

    def _secileni_al(self) -> Urun | None:
        self.hata_etiketi.clear()
        urun = self._secili()
        if urun is None:
            self.hata_etiketi.setText("Lütfen listeden bir ürün seçin.")
        return urun

    def _secim_degisti(self) -> None:
        urun = self._secili()
        pasif = urun is not None and not urun.aktif
        self.pasif_aktif_dugmesi.setText("Aktif Yap" if pasif else "Pasif Yap")

    def _yeni(self) -> None:
        pencere = UrunKartiPenceresi(self._veritabani_ayari, self._yapan)
        if pencere.exec() == QDialog.DialogCode.Accepted:
            self._yenile()

    def _guncel_secili(self) -> Urun | None:
        """Secili urunu veritabanindan yeniden okur: liste eski kalmis olabilir."""
        secili = self._secileni_al()
        if secili is None:
            return None
        guncel: list[Urun] = []

        def _oku(baglanti: Baglanti) -> None:
            guncel.append(urun_getir(baglanti, self._yapan, secili.id))

        if not islemi_calistir(self._veritabani_ayari, self.hata_etiketi, _oku):
            return None
        return guncel[0]

    def _duzenle(self) -> None:
        urun = self._guncel_secili()
        if urun is None:
            return
        pencere = UrunKartiPenceresi(self._veritabani_ayari, self._yapan, urun)
        if pencere.exec() == QDialog.DialogCode.Accepted:
            self._yenile()

    def _stok_girisi(self) -> None:
        urun = self._guncel_secili()
        if urun is None:
            return
        pencere = StokGirisiPenceresi(self._veritabani_ayari, self._yapan, urun)
        pencere.exec()
        self._yenile()

    def _stok_detayi(self) -> None:
        urun = self._guncel_secili()
        if urun is not None:
            StokDetayiPenceresi(self._veritabani_ayari, self._yapan, urun).exec()

    def _pasif_aktif(self) -> None:
        urun = self._secileni_al()
        if urun is None:
            return
        if urun.aktif and not self._pasif_onayi(urun):
            return
        islem = urun_pasif_yap if urun.aktif else urun_aktif_yap
        if islemi_calistir(
            self._veritabani_ayari,
            self.hata_etiketi,
            lambda baglanti: islem(baglanti, self._yapan, urun.id),
        ):
            self._yenile()

    def _onayla(self) -> None:
        urun = self._secileni_al()
        if urun is None:
            return
        if islemi_calistir(
            self._veritabani_ayari,
            self.hata_etiketi,
            lambda baglanti: urun_onayla(baglanti, self._yapan, urun.id),
        ):
            self._yenile()

    def _pasif_onayi(self, urun: Urun) -> bool:
        yanit = QMessageBox.question(
            self,
            "Ürünü pasif yap",
            f"{urun.ad} pasif yapılsın mı? Stokta {urun.stok_miktari} kutu var. "
            "Ürün aramalarda görünmez, kaydı silinmez.",
        )
        return yanit == QMessageBox.StandardButton.Yes
