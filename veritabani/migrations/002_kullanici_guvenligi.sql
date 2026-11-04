-- Hatali giris siniri ve gecici parola. Degerler veritabaninda durur:
-- program kapatilip acilinca veya baska kasaya gecilince sayac sifirlanmaz.
ALTER TABLE kullanicilar
    ADD COLUMN hatali_giris_sayisi INTEGER NOT NULL DEFAULT 0
        CHECK (hatali_giris_sayisi >= 0),
    ADD COLUMN kilit_bitis TIMESTAMPTZ,
    ADD COLUMN parola_degismeli BOOLEAN NOT NULL DEFAULT FALSE;
