-- Programi kullanan kisiler. Parolanin kendisi degil, yalnizca ozeti saklanir.
CREATE TABLE kullanicilar (
    id INTEGER PRIMARY KEY,
    kullanici_adi TEXT NOT NULL UNIQUE,
    ad_soyad TEXT NOT NULL,
    parola_ozeti TEXT NOT NULL,
    aktif INTEGER NOT NULL DEFAULT 1 CHECK (aktif IN (0, 1)),
    olusturma_tarihi TEXT NOT NULL
);

-- Hasta kayitlarina her erisim: kim, ne zaman, ne yapti, hangi kayda.
-- Bu tabloya TC, ad, telefon veya teshis yazilmaz; yalnizca kayit numarasi yazilir.
CREATE TABLE erisim_log (
    id INTEGER PRIMARY KEY,
    kullanici_id INTEGER NOT NULL REFERENCES kullanicilar (id),
    tarih TEXT NOT NULL,
    islem TEXT NOT NULL,
    kayit_turu TEXT NOT NULL,
    kayit_id INTEGER NOT NULL
);

CREATE INDEX idx_erisim_log_kayit ON erisim_log (kayit_turu, kayit_id);
CREATE INDEX idx_erisim_log_kullanici ON erisim_log (kullanici_id);
