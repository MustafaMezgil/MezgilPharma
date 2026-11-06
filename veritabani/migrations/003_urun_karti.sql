-- Urun karti. Karekodsuz urunler (dermokozmetik, mama, medikal) de burada tutulur.
-- psf, kamu_fiyati ve kdv_orani bos olabilir: personel karti fiyatsiz acar, eczaci sonradan girer.
CREATE TABLE urunler (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ad TEXT NOT NULL CHECK (btrim(ad) <> ''),
    -- Turkce harfleri esitlenmis arama metni; program kaydederken uretir.
    arama_metni TEXT NOT NULL,
    -- ITS Isletme Kilavuzu: GTIN 14 haneli ve yalnizca rakamdir. Barkodsuz urunde bos kalir.
    gtin TEXT UNIQUE CHECK (gtin ~ '^[0-9]{14}$'),
    urun_turu TEXT NOT NULL CHECK (urun_turu IN ('ilac', 'diger')),
    karekodlu BOOLEAN NOT NULL DEFAULT FALSE,
    recete_turu TEXT NOT NULL DEFAULT 'recetesiz'
        CHECK (recete_turu IN ('recetesiz', 'normal', 'kirmizi', 'yesil', 'mor', 'turuncu')),
    etken_madde TEXT,
    farmasotik_form TEXT,
    atc_kodu TEXT CHECK (atc_kodu ~ '^[A-Z0-9]{1,7}$'),
    uretici_firma TEXT,
    soguk_zincir BOOLEAN NOT NULL DEFAULT FALSE,
    raf_yeri TEXT,
    kritik_stok INTEGER NOT NULL DEFAULT 0 CHECK (kritik_stok >= 0),
    psf NUMERIC(12, 2) CHECK (psf > 0),
    kamu_fiyati NUMERIC(12, 2) CHECK (kamu_fiyati >= 0),
    kdv_orani NUMERIC(5, 2) CHECK (kdv_orani BETWEEN 0 AND 100),
    aktif BOOLEAN NOT NULL DEFAULT TRUE,
    olusturma_tarihi TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (NOT karekodlu OR gtin IS NOT NULL),
    CHECK (urun_turu = 'ilac' OR recete_turu = 'recetesiz')
);

CREATE INDEX idx_urunler_arama ON urunler (arama_metni);

-- Elimizdeki kutular parti parti tutulur: ayni ilacin farkli miatli kutulari olabilir.
-- Miktar tam kutudur ve eksiye dusemez. Alis fiyati farkliysa ayri satir olur.
CREATE TABLE stok_partileri (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    urun_id BIGINT NOT NULL REFERENCES urunler (id),
    -- Ilacta zorunludur (program denetler); diger urunlerde bos olabilir.
    parti_no TEXT CHECK (length(parti_no) BETWEEN 1 AND 20),
    skt DATE NOT NULL,
    miktar INTEGER NOT NULL CHECK (miktar >= 0),
    alis_fiyati NUMERIC(12, 2) NOT NULL CHECK (alis_fiyati >= 0),
    UNIQUE NULLS NOT DISTINCT (urun_id, parti_no, skt, alis_fiyati)
);

CREATE INDEX idx_stok_partileri_skt ON stok_partileri (skt);

-- Fiyat degisiklikleri. stok_miktari fiyat dususunde fiyat farki talebi icin gereklidir.
-- Kayitlar eklenir ve okunur, degistirilemez (yetki: veritabani/guncelle.py).
CREATE TABLE fiyat_gecmisi (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    urun_id BIGINT NOT NULL REFERENCES urunler (id),
    eski_psf NUMERIC(12, 2),
    yeni_psf NUMERIC(12, 2) NOT NULL,
    eski_kamu_fiyati NUMERIC(12, 2),
    yeni_kamu_fiyati NUMERIC(12, 2),
    stok_miktari INTEGER NOT NULL CHECK (stok_miktari >= 0),
    kullanici_id BIGINT NOT NULL REFERENCES kullanicilar (id),
    tarih TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_fiyat_gecmisi_urun ON fiyat_gecmisi (urun_id);
