"""Programin ana penceresi. Simdilik yalnizca ortami ve veritabani surumunu gosterir."""

from PyQt6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from ayarlar import Ortam


class AnaPencere(QMainWindow):
    def __init__(self, ortam: Ortam, veritabani_surumu: int) -> None:
        super().__init__()
        self.setWindowTitle("MezgilPharma")
        self.resize(800, 500)

        ortam_etiketi = QLabel(f"Ortam: {ortam.value}")
        ortam_etiketi.setObjectName("ortam_etiketi")
        surum_etiketi = QLabel(f"Veritabanı sürümü: {veritabani_surumu}")
        surum_etiketi.setObjectName("surum_etiketi")

        icerik = QWidget()
        duzen = QVBoxLayout(icerik)
        duzen.addWidget(ortam_etiketi)
        duzen.addWidget(surum_etiketi)
        duzen.addStretch()
        self.setCentralWidget(icerik)
