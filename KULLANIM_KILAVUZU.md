# 📖 İmzacı - Detaylı Kullanım Kılavuzu

Profesyonel PDF İmzalama Uygulaması için adım adım kılavuz.

---

## 📑 İçindekiler

1. [İlk Başlangıç](#ilk-başlangıç)
2. [Arayüz Tanıtımı](#arayüz-tanıtımı)
3. [Adım Adım Kullanım](#adım-adım-kullanım)
4. [İmza Ayarları](#imza-ayarları)
5. [Gelişmiş Özellikler](#gelişmiş-özellikler)
6. [Toplu İmzalama](#toplu-imzalama)
7. [Sık Sorulan Sorular](#sık-sorulan-sorular)
8. [Sorun Giderme](#sorun-giderme)

---

## 🚀 İlk Başlangıç

### 1. Uygulamayı Açın
imzaci.exe

### 2. İlk Açılışta
- ✅ Uygulama otomatik olarak sistem PKCS#11 kütüphanelerini arar
- ✅ Bağlı tokenlar (USB e-imza, akıllı kart, vb.) algılanır
- ✅ Eğer e-imzanız algılanamıyorsa lütfen selimsagol@hotmail.com adresine ekranın altındaki İşlem Günlüğü bölümündeki satırları ekleyerek bildirin.


### Yapılandırma Alanı
- **PKCS#11 DLL**(Otomatik tespit edilir): Sistem kütüphanesi dosyası (akisp11.dll, vb.)
- **Token**(Otomatik tespit edilir): USB e-imza, akıllı kart, HSM
- **Sertifika**(Otomatik tespit edilir): İmzalama için kullanılacak sertifika

### İmzalama Alanı
- **Giriş Dosyası**: İmzalanacak PDF
- **Çıkış Dosyası**: İmzalı PDF'nin kaydedileceği yer
- **PIN**: e-İmza şifrenizi gireceğiniz alan
- **İmzala**: İmzalama işlemini başlat
- e-imza işlemlerinde isteğe bağlı(boş bırakılabilir) eklenebilecek Neden ve Yer alanları için girişleri yapabilirsiniz

### İmza Şablonu Alanı
- **Logo Genişliği**: İmza resminin genişliği (mm cinsinden)
- **Metin Boyutu**: İmza metni (isim, tarih, sN) boyutu
- **Yazı Tipi**: İmza metninin fontu (Segoe, Arial, vb.)
- **Stil**: Yazı tipi stili (Normal, **Bold**, *Italic*)
- **Önizle Butonu**: Sağ panelde büyük ön izleme açar, bu önizleme ekranında imza resmini sürükle bırak ile istediğiniz konuma getrebilirsiniz.

### Şablon Alanı
- Bu alandaki imza resmini sürükle bırak ile istediğiniz konuma getirebilirsiniz.
- Bu alanda oluşturulan imza örselinin çıktı dosyası üzerindeki son durumunu görebilirsiniz.
- Henüz PDF seçimi yapılmamış ise bu alanda örnek bir dosya gösterilir, PDF seçimi sonrası bu alan gerçek PDF ile güncellenir.

### İşlem Günlüğü

- **Log**: Tüm işlemlerin kaydı

---

## 👣 Adım Adım Kullanım

### Adım 1: PKCS#11 Kütüphanesi Seçin ((Otomatik seçilir)


**Ne yapılır:**
1. Eğer otomatik keşif çalışmadıysa, "Gözat" butonuna tıkla
2. `C:\Windows\System32\` klasöründe `.dll` dosyasını ara
3. **Yaygın PKCS#11 dosyaları:**
   - `akisp11.dll` - AKI Smart Card
   - `aks11.dll` - Aks e-imza  
   - `softhsm.dll` - Yazılım HSM
4. Dosyayı seç, uygulama otomatik kaydeder

**Sorun:** DLL bulunamıyorsa → lütfen selimsagol@hotmail.com adresine ekranın altındaki İşlem Günlüğü bölümündeki satırları ekleyerek bildirin.

---

### Adım 2: Token Seçin (Otomatik seçilir)


**Ne yapılır:**
1. Token combo'sundan kendi token'ını seç
2. Format: `Slot X: TokenAdı`
3. Eğer token görünmüyorsa:
   - USB e-imzayı çıkar ve takın
   - "Yenile" butonuna basın
   - 2-3 saniye bekle

**İpucu:** Yenile butonuna her basışta token listesi güncellenir

---

### Adım 3: Sertifika Seçin (Otomatik seçilir)


**Ne yapılır:**
1. Token seçtikten sonra sertifika combo otomatik doldurulur
2. İmzalamak için kullanılacak sertifikayı seç
3. Format: `İsim | Tarih | Seri No`
4. Sertifika yoksa token'ı kontrol et

---

### Adım 4: PDF Dosyalarını Seçin

**Ne yapılır:**
1. **Giriş PDF:** "Gözat" butonuyla imzalanacak PDF'yi seç
2. **Çıkış Dosyası:** Otomatik olarak `_signed` eklenmiş ad ile orjinal dosyayla aynı konuma eklenir
   - İstenirse başka isim/konum seçilebilir
3. Çıkış dosyası varsa üzerine yazmak için onay ister


---

### Adım 5: İmza Ayarlarını Yapılandırın

### 5.1 - Logo Genişliği
- **Varsayılan:** 15.0 mm
- **Aralık:** 10-25 mm önerilir
- **Büyük** (20+ mm) = Daha belirgin imza
- **Küçük** (10 mm) = Daha az yer kaplayıcı
- **Örnek:** e-imza logosu tipik 15-20 mm

### 5.2 - Font Boyutu
- **Varsayılan:** 3.0 mm (bu yazı tipi boyutu değil, imza blok boyutu)
- **Aralık:** 2-5 mm
- **Büyük** (4-5 mm) = Okunması daha kolay
- **Küçük** (2-3 mm) = Daha az yer kaplayıcı

**Kombinasyonlar:**
- **Normal + Segoe** = Resmi belgeler
- **Bold + Arial** = Önemli belgeler
- **Italic + Verdana** = Vurgu, özel notlar

---

### Adım 6: Ön İzleme Yapın

Dilerseniz ana ekrandaki Şablon alanını, dilerseniz de Önzile butonu ile daha büyük bir ekranda açılan İmza Önizleme penceresini kullanabilirsiniz. 

**Ön izlemede:**
- ✅ Tam boyutlu A4 sayfa (ölçeklenmiş)
- ✅ İmza konumunu gösterir
- ✅ Sürükle-bırak ile konumu dinamik değiştirebilirsin
- ✅ Metin, logo, kenar boşluğu ön izlenir

---

### Adım 7: PIN Gir ve İmzala

**Ne yapılır:**
1. PIN alanına şifrenizi girin
2. PIN maskeli gösterilir (••••••)
3. "İmzala" butonuna basın
4. İmzalama başlayacak:
   ```
   ⏳ PDF imzalanıyor... Lütfen bekleyin
   [====== İlerleme Çubuğu ======]
   [İptal]
   ```

**İşlem sırasında:**
- ⏳ 3-10 saniye bekle (PDF boyutuna bağlı)

---

## 🛡️ Gelişmiş Özellikler

### Çoklu İmzalama (Multi-Signature)

**Ne işe yarar?**
Birden fazla kişinin aynı PDF'yi ardı ardına imzalamasını sağlar.

**Kullanım adımları:**
1. "Çoklu İmza" checkbox'ını işaretleyin
2. İlk kişi PDF'yi imzalasın → `belgem_signed.pdf` oluşur
3. İkinci kişi bu imzalı PDF'yi giriş dosyası olarak seç
4. Tekrar "Çoklu İmza" işaretlenmiş halde "İmzala" tıkla
5. İkinci imza eklenir → `belgem_signed_2.pdf` oluşur

**Örnek senaryo:**
```
Talep Eden: Ali (Email: ali@sirket.com)
    ↓ İmzala (İmza 1)
Onaylayan: Veli (Email: veli@sirket.com)  
    ↓ İmzala (İmza 2)
Genel Müdür: Mehmet (Email: meli@sirket.com)
    ↓ İmzala (İmza 3)
Final PDF: belgem_signed_3.pdf (3 imza ile)
```

**İpucu:** Her imzalama sonrası yeni dosya oluşturulur, orijinal korunur.

---

### Zaman Damgası (TSA - Time Stamp Authority)

**Ne işe yarar?**
PDF'nin hangi tarih/saatte imzalandığını resmi olarak kayıt altına alır.

**Otomatik Etkinleştirme:**
- Test ağı kullanılıyorsa: Otomatik açılır
- Manuel açma:
  1. "TSA" checkbox'ını işaretleyin
  2. Default: `http://timestamp.digicert.com` (DigiCert sunucusu)
  3. İmzalayın

**Avantajları:**
- İmza zamanını kanıtla
- Hukuki belge için tarih damgası
- İmzanın süresi dolsa bile zaman kaydı kalır

---

### Süresi Uzatma (LTV - Long-Term Validity)

**Ne işe yarar?**
İmzanın yıllar sonrasında da doğrulanabilmesini sağlar.

**Kullanım:**
1. "LTV" checkbox'ını işaretleyin
2. Sertifika chain'i (zincir) PDF'e gömülür
3. İmzalayın

**Neden gerekli?**
- İmza sertifikası süresi dolsa bile PDF geçerli olur
- Arşivleme için uzun vadeli geçerlilik
- Yasal belgeler için önerilir

---

### Belge Kısıtlamalar (DocMDP - Certification Permissions)

**Ne işe yarar?**
İmzalı PDF'ye sonradan yapılabilecek değişiklikleri kontrol eder.

**3 Seçenek:**

| Seçenek | İzin Verilen | Yasak |
|---------|-------------|-------|
| **Sadece İmza** | Yalnız imza ekleme | Form doldurma, düzenleme |
| **Form Doldurma + İmza** | Form doldurma, imza ekleme | PDF içeriğini düzenleme |
| **Form + Yorum + İmza** | Form, yorum, imza ekleme | PDF sayfalarını silme |

**Örnek:**
```
Sözleşme: "Sadece İmza" → Hiç kimse muhteva değiştiremez
Teklif: "Form doldurma + imza" → Fiyat alanı doldurulabilir
Rapor: "Form + yorum + imza" → Notlar/açıklamalar eklenebilir
```

---

### İmzalama Seçenekleri Yardımı

Sağ üst köşedeki **ℹ️ (Mavi soru işareti)** butonuyla açılan modal pencereden tüm seçenekleri görebilirsiniz:
- **LTV:** Sertifika zincirsin kaydı
- **TSA:** Zaman damgası sunucusu ve durumu
- **DocMDP:** Belge kısıtlamaları açıklaması
- **Çoklu İmza:** Ardışık imzalama bilgisi

---

## 📚 Toplu Belge İmzalama

**Birden fazla PDF'yi bir kez imzalamak için:**

### 1. "Toplu Belge İmzalama" Butonuna Tıkla
```
[📚 Toplu Belge İmzalama]
```

### 2. Dosya Seç Dialogu Açılır
- **Giriş Klasörü:** İmzalanacak PDF'lerin bulunduğu klasörü seç
- **Çıkış Klasörü:** İmzalı dosyaların kaydedileceği yeri seç (varsayılan: Giriş Klasörü)

### 3. Otomatik İmzalama Başlar
```
⏳ belgem1.pdf imzalanıyor...
✅ belgem1_signed.pdf tamam

⏳ belgem2.pdf imzalanıyor...
✅ belgem2_signed.pdf tamam

⏳ belgem3.pdf imzalanıyor...
✅ belgem3_signed.pdf tamam

Hepsi Bitti! 3 dosya imzalandı.
```

**Avantajları:**
- 100+ dosyayı otomatik imzala
- Hepsi aynı ayarlarla (PIN, sertifika, imza konumu)
- Hata varsa devam et, istisna dosyaları raporla
- Zaman tasarrufu

**İpucu:** İmza konumunu önceden ön izlemede ayarla, toplu imzalama hepsine uygulayacak.

---

### S: Birden fazla token var, onu seçebilir miyim?
**C:** Evet! Token combo'sundan istediğinizi seçebilirsiniz. 
Slot 0: TokenAdı
Slot 1: DiğerTokenAdı

### S: PDF'de imzanın konumunu sürükle-bırak ile değiştirebilir miyim?
**C:** Evet! Ana ekrandaki Şablon panelinden yada "Önizle" butonuna tıklayarak, açılan pencerede yapabilirsiniz.

### S: Çıkış PDF'sine başka isim vermek istiyorum?
**C:** "Çıkış Dosyası" alanına tıkla, istediğin adı yaz veya "Gözat" ile konum seç.

### S: Ön izlemede konum değiştirdikten sonra bu kalıcı olur mu?
**C:** Evet! Sürükle-bırak konumları otomatik kaydedilir ve bir sonraki açılışta uygulanır.

### S: PIN'i yanlış girirsem ne olur?
**C:** Hata mesajı görürsün:
```
⚠️ Hata: PIN yanlış veya token kimlik doğrulaması başarısız
```
PIN'i düzelt ve yeniden dene.

### S: PDF'yi imzalarken yanlışlıkla kapatırsem ne olur?
**C:** Hiçbir şey olmaz:
- Orijinal PDF değişmez (yedek gibi işlev görür)
- Çıkış dosyası kısmen yazılır ve kullanılamaz hale gelebilir
- Yeniden imzalamayı dene

### S: Bir PDF'yi birden fazla kez imzalayabilir miyim?
**C:** Evet! İmzalı PDF'yi yeniden giriş dosyası olarak seçebilirsin.

### S: Çoklu imzalamada sırası önemli mi?
**C:** Evet! Yasal ve kronolojik sırayla yapılması tavsiye edilir:
1. Talebi yapan kişi
2. Onaylayan/Müdür
3. Genel Müdür/Yönetim

### S: TSA sunucusu offline olursa ne olur?
**C:** İmza başarısız olur. Uygulama otomatik interneti kontrol eder:
- Offline ise "TSA" checkbox'ı gri olur
- Online bağlandıktan sonra açılabilir

### S: LTV ve TSA farklı mı?
**C:** Evet!
- **TSA:** İmza anının zaman kaydı
- **LTV:** Sertifika zincirinin saklanması
- **İkisi beraber:** En güvenli (önerilir)

### S: PDF zaten imzalı ise "Çoklu İmza" olmadan imzalayırsam?
**C:** 
- "Çoklu İmza" açık: 2. imza eklenir ✅
- "Çoklu İmza" kapalı: Hata → "PDF zaten imzalı" uyarısı

### S: Toplu imzalamada hata olursa tüm işlem durmam mı?
**C:** Hayır! Hatalı dosya atlanır, diğerleri devam eder:
```
⏳ belgem1.pdf imzalanıyor...
✅ belgem1_signed.pdf tamam

❌ belgem2.pdf → HATA: PIN yanlış
(Devam ediyor...)

⏳ belgem3.pdf imzalanıyor...
✅ belgem3_signed.pdf tamam
```

---

## 🔧 Sorun Giderme

### 🔴 Hata: "PKCS#11 DLL bulunamadı"

**Çözüm 1: Manuel seç**
1. Sağ panelde "Gözat" butonuna tıkla
2. `C:\Windows\System32\` aç
3. Yaygın PKCS#11 dosyaları ara:
   - `akisp11.dll`
   - `aks11.dll`
   - `eToken.dll`

**Çözüm 2: Sürücü kur**
1. Token'ın sürücü yazılımını indir
2. Kur ve yeniden başlat

---

### 🔴 Hata: "Token algılanmadı"

**Çözüm 1: Fiziksel kontrol**
- USB e-imzayı başka USB porta tak
- USB hub yerine doğrudan bilgisayara tak
- Başka bilgisayarda dene

**Çözüm 2: Sürücü sorunu**
- Sürücü yoksa kur, varsa güncelle

**Çözüm 3: Uygulamayı yenile**
1. "Yenile" butonuna basın
2. 3 saniye bekle
3. Hala gözükmüyorsa uygulamayı kapat/aç

**Çözüm 4: Token'ı sıfırla (Son çare)**
- Token üreticisinin yazılımıyla PIN sıfırla
- VEYA token'ı başka bilgisayarda dene
- VEYA teknik destek ile iletişim kur
---

### 🔴 Hata: "Sertifika bulunamadı"

**Çözüm 1: Token açılması gerekiyor**
- "Yenile" butonuna basın
- 2-3 saniye bekle

**Çözüm 2: PIN yanlış (ön-imza için)**
- Yazılım PIN tarafından korunuyorsa GUI'de istem olacak
- İlk imzalamada PIN girmesi gerekebilir

**Çözüm 3: Sertifika süresi doldu**
```powershell
# Sertifika bilgilerini kontrol et
# Token yazılımı > Sertifikalar > Geçerlilik Tarihi
```
Süresi dolmuşsa yeni sertifika talep et.

**Çözüm 4: Yanlış token seçti**
- Token combo'sundan başka token seç
- Bazı tokenlar birden fazla sertifika taşır

---


### 🔴 Hata: "PDF imzalanırken sorun oluştu"

**Sık nedenler:**

| Hata | Çözüm |
|------|-------|
| "Dosya bulunamadı" | Giriş dosyası silinmişse yeniden seç |
| "Yazma izni yok" | Çıkış dosyası başka uygulamada açıksa kapat |
| "PDF hatalı" | Giriş dosyasını kontrol et, başka PDF dene |
| "Memory hatası" | Çok büyük PDF, sistem RAM'i kontrol et |
| "Timeout" | Ağ bağlantısında hata (HSM kullanıyorsa) |

---

## 📞 Destek

**Sorunu çözemezseniz:**
1. Log penceresindeki tüm mesajları kopyala
2. Bu kılavuzda Sorun Giderme bölümünü kontrol et
3. `~/.imzaci/config.json` yapısını kontrol et
4. selimsagol@hotmail.com a eposta ile bildir
---

## 📚 Ek Kaynaklar

- [PAdES Standartı](https://en.wikipedia.org/wiki/PAdES)
- [PKCS#11 Nedir?](https://en.wikipedia.org/wiki/PKCS_%2311)
- [Adobe PDF İmza Referansı](https://www.adobe.com/content/dam/acom/en/security/pdfs/iso_32000-2_2020_locked.pdf)

---

**Versiyon:** 2.4  
**Son Güncelleme:** Şubat 2026  
**Yazarlar:** Selim SAĞOL - Öğr. Görevlisi/Uzman/Bilgisayar Mühendisi  

Keyifli imzalamalar! 🎉
