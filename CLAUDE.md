# Eczane Otomasyonu – Claude Code Talimatları

Bu proje, farklı eczanelere kurulacak masaüstü eczane otomasyon programıdır.
Her eczanenin kendi veritabanı vardır; eczaneler arasında veri paylaşılmaz.
Bilgisayar sayısı eczaneden eczaneye değişir, kod tek eczaneye özel varsayım içermez.
Proje sahibi bir eczacıdır, ileri düzey yazılımcı değildir. Ona her zaman
**Türkçe, sade ve adım adım** açıklama yap.

---

## 1. Teknoloji (değiştirme)

- **Dil:** Python 3.14, sanal ortam `.venv`
- **Arayüz:** PyQt6 (tek arayüz katmanı; pywebview, Tkinter, React vb. ekleme)
- **Veritabanı:** PostgreSQL 18 (`psycopg` ile), şema değişiklikleri yalnızca migration ile.
  Sunucu eczanenin ana makinesinde çalışır, diğer bilgisayarlar yerel ağdan bağlanır.
  Tek bilgisayarlı eczanede ana makine ile kasa aynı bilgisayardır.
- **Tip kontrolü:** Pyright
- **Testler:** pytest; veritabanı testleri gerçek PostgreSQL'de, yalnızca `eczane_pytest` üzerinde çalışır
- **Geliştirme ortamı:** Windows, PowerShell (VS Code terminali). Terminal komutlarını
  PowerShell'e uygun ver; Linux/macOS komutları (`ls -la`, `cat`, `export`, `/` ile yol) kullanma.
- **Paketleme:** PyInstaller (hedef işletim sistemi: **Windows**)
- **Mobil/web panel (ileride):** ayrı klasörde (`web_panel/`), FastAPI. Masaüstü koda karıştırma.

**Yeni bir kütüphane, framework ya da servis eklemeden önce mutlaka bana sor.**
Nedenini ve alternatifini kısaca açıkla.

---

## 2. Klasör yapısı

```
eczane/
├── CLAUDE.md
├── .env                  # şifreler (OKUMA, DEĞİŞTİRME)
├── .env.example          # örnek değişken adları (değer içermez)
├── main.py               # programın giriş noktası
├── ayarlar.py            # .env'den ayarları okur, TEST/CANLI ortam seçimi
├── gunluk.py             # log dosyası (hasta verisi yazılmaz)
├── veritabani/
│   ├── baglanti.py       # PostgreSQL bağlantısı
│   ├── migration.py      # migration'ları uygular, sürüm uyumunu doğrular
│   ├── guncelle.py       # şema güncellemesi, yedek ve yetkiler (yalnızca ana makinede)
│   └── migrations/       # 001_ilk_sema.sql, 002_... (numaralı, sırayla)
├── moduller/
│   ├── kullanici/        # kullanıcı girişi, roller, parola özetleme
│   ├── ilac/             # ilaç kartları
│   ├── stok/             # stok, miat, ölü stok, akıllı sipariş önerisi
│   ├── satis/            # satış ekranı, kasa
│   ├── karekod/          # GS1 DataMatrix ayrıştırma
│   ├── its/              # İlaç Takip Sistemi istemcisi
│   ├── medula/           # SGK Medula istemcisi
│   ├── recete_kontrol/   # SUT kural motoru + yapay zeka yardımı
│   ├── etiket/           # kullanım tarifi etiketi ve yazdırma
│   ├── hasta/            # hasta kartı, rıza kayıtları, hatırlatmalar
│   └── rapor/            # raporlar
├── arayuz/               # PyQt6 pencereleri ve QSS stilleri
├── dokumanlar/           # Medula, ITS, SUT resmi dokümanları (referans)
└── tests/                # her modül için test dosyaları
```

Aynı işi yapan ikinci bir dosya/fonksiyon oluşturma. Önce mevcut kodda ara.

---

## 3. Değişmez kurallar

### Güvenlik ve KVKK
- `.env` dosyasını **okuma, gösterme, değiştirme**. Yeni bir ayar gerekirse
  `.env.example`'a sadece değişken adını ekle ve bana söyle.
- Şifre, GLN, kullanıcı adı, API anahtarı gibi bilgileri **asla koda yazma**.
- **Gerçek hasta verisi kullanma.** Testlerde sahte TC, sahte ad, sahte reçete üret.
- Hasta verisi (TC, ad, telefon, teşhis) loglara, hata mesajlarına ve
  yapay zeka servislerine **gönderilmez**. Yapay zekaya yalnızca anonim veri
  (ilaç, teşhis kodu, doz, rapor bilgisi) gider.
- Hasta kayıtlarına her erişim `erisim_log` tablosuna yazılır (kim, ne zaman, ne).

### Para ve hesaplar
- Para, fiyat, iskonto, KDV için **`float` değil `Decimal`** kullan.
- Yuvarlama kuralını tek bir yardımcı fonksiyonda topla.

### Veritabanı
- SQL sorguları **her zaman parametreli** (`%s`). String birleştirme ile SQL yazma.
- Tabloyu doğrudan değiştirme; yeni numaralı migration dosyası oluştur.
- Uygulanmış migration dosyası değiştirilmez.
- Tarihler PostgreSQL tarih türlerinde (`DATE`, `TIMESTAMPTZ`) saklanır; kayıt saati
  sunucudan alınır. Dışa aktarımda ISO biçimi (`YYYY-MM-DD`, `YYYY-MM-DDTHH:MM:SS`) kullanılır.
- Para ve fiyat sütunları `NUMERIC`; `FLOAT`/`REAL` kullanılmaz.
- Silme işlemi yerine mümkünse `aktif = FALSE` (soft delete).
- Şema güncellemesini yalnızca ana makine yapar (`eczane_sahip` hesabı, güncelleme öncesi yedek).
  Kasalar `eczane_uygulama` hesabıyla bağlanır; tablo yapısını değiştiremez, `erisim_log`
  kayıtlarını değiştirip silemez. Yeni yetki kuralları `veritabani/guncelle.py` içindedir.
- Ağ üzerinden bağlantıda SSL zorunludur.

### Medula ve ITS
- Varsayılan ortam **TEST**. CANLI ortam yalnızca `ayarlar.py`'deki tek bir
  ayarla açılır; bunu asla kendiliğinden değiştirme.
- Alan adlarını, kod tablolarını ve servis yapılarını **tahmin etme**;
  `dokumanlar/` klasöründeki resmi dokümana bak. Dokümanda yoksa bana sor.
- İnternet veya Medula kesildiğinde program çökmemeli; işlem kuyruğa alınır,
  bağlantı gelince gönderilir.
- Satış, iade, deaktivasyon gibi geri alınamayan bildirimlerden önce kullanıcıdan
  onay alınır.

### Yapay zeka ve öneriler
- Akıllı sipariş, reçete/rapor kontrolü gibi özellikler **yalnızca öneri ve uyarı**
  verir. Son kararı her zaman eczacı verir; otomatik sipariş veya otomatik
  reçete işlemi yapılmaz.
- SUT kuralları test edilebilir kod olarak `recete_kontrol/kurallar/` içinde,
  tarihli sürümlerle tutulur. Yapay zeka sadece kuralların kapsamadığı durumda
  açıklama/yorum için kullanılır ve ilgili SUT maddesini gösterir.
- İlaç etkileşimi, doz bilgisi gibi tıbbi verileri **uydurma**. Kaynak yoksa söyle.

### Hasta hatırlatmaları
- SMS/WhatsApp yalnızca açık rızası kayıtlı hastalara gider (rıza tarihi ve kanalı saklanır).
- Mesajlar sadece bilgilendirme içerir; kampanya, ürün tanıtımı, reklam **yok**.
- Mesajda ilaç adı veya hastalık bilgisi açıkça yazılmaz.

### Etiket yazdırma
- Doz kodunu metne çeviren fonksiyon (`etiket/doz_metni.py`) saf fonksiyondur
  ve kapsamlı testleri vardır.
- Yazdırmadan önce önizleme ve düzenleme ekranı gösterilir.
- Etikette TC ve teşhis yazılmaz; hasta adı en fazla "Ad S." biçiminde.
- Türkçe karakterler (ş, ğ, ı, İ, ç, ö, ü) her yazıcı çıktısında test edilir.

### Karekod
- GS1 DataMatrix ayrıştırma `karekod/` modülündedir: (01) GTIN, (21) seri no,
  (17) SKT, (10) parti no, FNC1 ayıracı, değişken uzunluklu alanlar.
- Her yeni karekod durumu için test eklenir.

---

## 4. Çalışma şekli

1. **Büyük işlerde önce plan yap**, bana göster, onayımı bekle. Sonra kodla.
2. İşi küçük adımlara böl; bir seferde tek modül/özellik.
3. **Önce testi yaz, sonra kodu yaz.** Her değişiklikten sonra çalıştır:
   ```
   .venv\Scripts\pytest
   .venv\Scripts\pyright
   ```
   Testler veya Pyright hata veriyorsa işi bitmiş sayma.
4. Her adım bitince bana şunları Türkçe ve kısaca anlat:
   - Ne yaptın, hangi dosyaları değiştirdin
   - Programı nasıl deneyebilirim (hangi ekrana girip neye tıklayayım)
   - Dikkat etmem gereken bir risk var mı
5. Emin olmadığın bir eczacılık/mevzuat konusunda **tahmin etme, bana sor**.
6. Hata mesajlarını kullanıcıya Türkçe ve anlaşılır göster; teknik detay loga gider.
7. Bir özellik bitince commit mesajı öner (Türkçe, kısa).

---

## 5. Terimler sözlüğü

| Terim | Anlamı |
|---|---|
| ITS | İlaç Takip Sistemi (TİTCK); karekodlu ilaçların alım/satış/iade bildirimi |
| Medula | SGK'nın reçete ve provizyon sistemi |
| SUT | Sağlık Uygulama Tebliği; geri ödeme kuralları |
| GLN | Eczanenin global konum numarası (ITS'de kimlik) |
| Karekod | İlaç kutusundaki GS1 DataMatrix kod |
| GTIN | Ürünün barkod numarası (karekoddaki 01 alanı) |
| SKT / Miat | Son kullanma tarihi |
| Reçete türleri | Normal (beyaz), kırmızı, yeşil, mor, turuncu |
| Raporlu ilaç | Hekim raporu olmadan SGK'nın ödemediği ilaç |
| Kesinti | SGK'nın kurala uymayan reçete için ödememesi |
| ÖKC | Yeni nesil yazar kasa |
| Ölü stok | Uzun süredir satılmayan ürün |

---

## 6. Geliştirme sırası

1. Proje iskeleti, ayarlar, veritabanı ve migration sistemi
2. İlaç kartı ve stok
3. Karekod modülü
4. Satış ekranı
5. Raporlar (miat, ölü stok, ciro)
6. Akıllı stok ve sipariş önerisi
7. Kullanım tarifi etiketi (önce elle girilen dozla)
8. Günlük otomatik yedekleme ve disk şifreleme
9. Hasta kartı ve hatırlatmalar
10. ITS (test ortamında)
11. Medula (test ortamında), etikete Medula verisinin bağlanması
12. Reçete/rapor kontrolü (kural motoru + yapay zeka)
13. Yazar kasa (ÖKC) ve e-fatura/e-arşiv
14. Mobil/web panel (yalnızca özet: ciro, kritik stok, miat; hasta verisi yok)

Şu an üzerinde çalışılan adım: **1**
