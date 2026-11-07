-- Denetim kaydinin ayrintisi: ornegin kart degisikliginde degisen alanlar ve kritik
-- alanlarin eski/yeni degeri. Hasta verisi (TC, ad, telefon, teshis) buraya yazilmaz.
ALTER TABLE erisim_log ADD COLUMN ayrinti JSONB;

-- Personelin actigi kart, eczaci onaylayana kadar isaretli kalir.
ALTER TABLE urunler ADD COLUMN onay_bekliyor BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX idx_urunler_onay_bekliyor ON urunler (onay_bekliyor) WHERE onay_bekliyor;
