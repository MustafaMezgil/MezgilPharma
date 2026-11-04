-- Programi kullanan kisiler. Parolanin kendisi degil, yalnizca ozeti saklanir.
CREATE TABLE kullanicilar (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kullanici_adi TEXT NOT NULL UNIQUE,
    ad_soyad TEXT NOT NULL,
    parola_ozeti TEXT NOT NULL,
    rol TEXT NOT NULL DEFAULT 'personel' CHECK (rol IN ('eczaci', 'personel')),
    aktif BOOLEAN NOT NULL DEFAULT TRUE,
    olusturma_tarihi TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Hasta kayitlarina her erisim: kim, ne zaman, ne yapti, hangi kayda.
-- Bu tabloya TC, ad, telefon veya teshis yazilmaz; yalnizca kayit numarasi yazilir.
-- Saat, bilgisayarlar arasindaki farktan etkilenmemesi icin sunucudan alinir.
CREATE TABLE erisim_log (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kullanici_id BIGINT NOT NULL REFERENCES kullanicilar (id),
    tarih TIMESTAMPTZ NOT NULL DEFAULT now(),
    islem TEXT NOT NULL,
    kayit_turu TEXT NOT NULL,
    kayit_id BIGINT NOT NULL
);

CREATE INDEX idx_erisim_log_kayit ON erisim_log (kayit_turu, kayit_id);
CREATE INDEX idx_erisim_log_kullanici ON erisim_log (kullanici_id);
