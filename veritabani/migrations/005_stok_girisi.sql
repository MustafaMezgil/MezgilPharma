-- Parti maliyeti mal fazlasi dahil net birim maliyettir (toplam tutar / toplam kutu).
-- Bolme kurusa tam inmeyebilir: 4 hane saklanir, ekranda 2 haneye yuvarlanir.
ALTER TABLE stok_partileri RENAME COLUMN alis_fiyati TO birim_maliyet;
ALTER TABLE stok_partileri ALTER COLUMN birim_maliyet TYPE NUMERIC(14, 4);

-- Ecza depolari. Ayni depo farkli yazimla iki kez eklenmesin diye arama_adi tekildir.
CREATE TABLE tedarikciler (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ad TEXT NOT NULL CHECK (btrim(ad) <> ''),
    arama_adi TEXT NOT NULL UNIQUE,
    aktif BOOLEAN NOT NULL DEFAULT TRUE,
    olusturma_tarihi TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Stok defteri: stogu degistiren her islem. Kayitlar degistirilemez ve silinemez
-- (yetki: veritabani/guncelle.py). Hatali islem karsi kayitla duzeltilir.
-- toplam_tutar faturadaki satir tutaridir (KDV haric, iskontolu); toplam maliyet
-- raporlarda bu tutardan hesaplanir, birim maliyetten degil.
CREATE TABLE stok_hareketleri (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    parti_id BIGINT NOT NULL REFERENCES stok_partileri (id),
    tur TEXT NOT NULL CHECK (tur IN ('giris', 'acilis')),
    miktar INTEGER NOT NULL CHECK (miktar <> 0),
    alinan_adet INTEGER CHECK (alinan_adet >= 0),
    mf_adet INTEGER CHECK (mf_adet >= 0),
    toplam_tutar NUMERIC(14, 2) CHECK (toplam_tutar >= 0),
    tedarikci_id BIGINT REFERENCES tedarikciler (id),
    fatura_no TEXT CHECK (btrim(fatura_no) <> ''),
    kullanici_id BIGINT NOT NULL REFERENCES kullanicilar (id),
    tarih TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (tur NOT IN ('giris', 'acilis') OR (
        alinan_adet IS NOT NULL AND mf_adet IS NOT NULL AND toplam_tutar IS NOT NULL
        AND miktar = alinan_adet + mf_adet
    )),
    CHECK (tur <> 'giris' OR (tedarikci_id IS NOT NULL AND fatura_no IS NOT NULL)),
    CHECK (tur <> 'acilis' OR (tedarikci_id IS NULL AND fatura_no IS NULL AND mf_adet = 0))
);

CREATE INDEX idx_stok_hareketleri_parti ON stok_hareketleri (parti_id);
CREATE INDEX idx_stok_hareketleri_fatura ON stok_hareketleri (tedarikci_id, fatura_no);

-- Eczaneye ozel ayarlar. Kayit yoksa program varsayilan degeri kullanir.
CREATE TABLE eczane_ayarlari (
    anahtar TEXT PRIMARY KEY,
    deger TEXT NOT NULL
);

INSERT INTO eczane_ayarlari (anahtar, deger) VALUES ('miat_uyari_ay', '6');
