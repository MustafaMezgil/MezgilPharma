-- Kullanicinin rolu: eczaci veya personel. Yetkisi en dusuk olan varsayilandir.
ALTER TABLE kullanicilar
    ADD COLUMN rol TEXT NOT NULL DEFAULT 'personel' CHECK (rol IN ('eczaci', 'personel'));
