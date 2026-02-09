# PDF İmzacı - Profesyonel PDF İmza Uygulaması v2.4

Türkçe, Python tabanlı PDF dijital imzalama uygulaması. PKCS#11 uyumlu tokenlar (USB e-imza, akıllı kartlar, HSM'ler) ile PAdES (ISO 32000-2) standartında imza atar.

## � Hızlı Başlangıç

**Windows Kullanıcıları:** [Latest Release](https://github.com/selsag/imzaci/releases) kısmından `imzaci.exe` indir ve çalıştır! 🎯
> ⚠️ **Windows Uyarısı:** İlk çalıştırmada "Bilinmeyen yayıncı" uyarısı görebilirsiniz.
> "Daha Fazla Bilgi" → "Yine de Çalıştır" tıklayınız. Bu normal ve güvenlidir.
Veya aşağıda Python ile kurulum yap.

## �🚀 Özellikleri

- ✨ **Modern ttkbootstrap GUI** - Profesyonel, kullanıcı dostu arayüz
- 🔐 **PKCS#11 Token Yönetimi** - Otomatik keşif ve slot/sertifika seçimi  
- 📁 **Dosya Seçimi** - Giriş/çıkış PDF dosyaları için dialog desteği
- ✍️ **Görsel İmza Özelleştirmesi** - Boyut, konum, kenar boşluğu ayarları
- 💾 **Kalıcı Ayarlar** - `~/.imzaci/config.json` dosyasında otomatik kaydedilir
- 🔑 **Güvenli PIN Giriş** - Maskeli giriş, asla diske yazılmaz
- 📊 **Gerçek-zamanlı Log** - İşlem geçmişi ve hata mesajları
- 🛡️ **Hata Toleransı** - Fallback stratejileri ve anlaşılır hata mesajları
### 🆕 Gelişmiş Özellikler (v2.4)

- **🔗 Çoklu İmzalama** - Birden fazla kişi aynı belgeyi ardı ardına imzalayabilir
- **⏰ Zaman Damgası (TSA)** - İmza zamanını resmi olarak kayıt altına al
- **📦 Süresi Uzatma (LTV)** - Sertifika zincirini PDF'e gömülerek yıllar sonra doğrulama
- **🔒 Belge Kısıtlamaları (DocMDP)** - 3 seviye izin kontrolü (İmza-sadece, Form+İmza, Form+Yorum+İmza)
- **📚 Toplu Belge İmzalama** - 100+ PDF'yi bir kez imzala, otomatik işleme devam et
## 📋 Gereksinimler

- Python 3.8+
- Windows (Linux/macOS için değişiklikler gerekebilir)
- PKCS#11 uyumlu token ve sürücüleri

## ⚙️ Kurulum

### 1. Bağımlılıkları Yükle
```powershell
pip install -r requirements.txt
```

### 2. Uygulamayı Çalıştır
```powershell
# GUI'yi başlat
python gui.py

# Veya
python -m imzaci
```

## 🎯 Kullanım

### GUI İle (Önerilen)

1. **PKCS#11 DLL Seçin**
   - "Gözat" butonuyla manuel seç
   - Veya otomatik keşif (uygulama açılışında çalışır)
   - Ayarlar `~/.imzaci/config.json` dosyasında kaydedilir

2. **Token & Sertifika Seçin**
   - Token combo'sundan token seçin
   - Sertifika combo'sundan sertifika seçin
   - "Yenile" butonuyla manual güncelle

3. **Dosyaları Seçin**
   - Giriş PDF'ini seçin
   - Çıkış dosyası otomatik önerilir (değiştirebilirsiniz)

4. **İmza Ayarlarını Yapılandırın**
   - Logo genişliği (mm)
   - Metin genişliği (mm)
   - Pozisyon (sağ-üst, sol-üst, vs.)
   - Kenar boşluğu (mm)

5. **PIN Girin ve İmzala**
   - PIN'i girin (maskeli giriş)
   - "İmzala" butonuna basın
   - Log penceresinde ilerlemeyi izleyin

### Gelişmiş Seçenekler

#### Çoklu İmzalama (Multi-Signature)
```
Hukuki süreç: Talep Eden → Onaylayan → Genel Müdür
Her bir kişi:
1. İmzalı PDF'yi giriş dosyası olarak seç
2. "Çoklu İmza" checkbox'ını işaretle
3. İmzala → Yeni imza eklenir (belgem_signed_2.pdf)
```

#### Zaman Damgası (TSA) & Süresi Uzatma (LTV)
```
"TSA" checkbox: İmza zamanını resmi sunucudan kaydettir
"LTV" checkbox: Sertifika zincirini PDF'e göm (uzun vadeli geçerlilik)
```

#### Belge Kısıtlamaları (DocMDP)
```
"Sadece İmza": İmza eklenmesi dışında hiçbir değişiklik
"Form Doldurma + İmza": Form alanları doldurulabilir
"Form + Yorum + İmza": Notlar ve yorumlar eklenebilir
```

### Toplu Belge İmzalama

```
1. "Toplu Belge İmzalama" butonuna tıkla
2. İmzalanacak PDF'lerin klasörünü seç
3. Çıkış klasörünü seç (otomatik ayarlanır)
4. PIN ve ayarlarla 100+ dosya otomatik imzala
5. Hata varsa devam et, rapor döndür
```

### CLI İle (Opsiyonel)

```powershell
# Tokenları listele
python sign_pdf.py --pkcs11-lib "C:\Windows\System32\akisp11.dll" list-slots

# Sertifikaları listele
python sign_pdf.py --pkcs11-lib "C:\Windows\System32\akisp11.dll" list-certs

# PDF imzala
python sign_pdf.py sign \
  --pkcs11-lib "C:\Windows\System32\akisp11.dll" \
  --in input.pdf \
  --out signed.pdf \
  --pin 123456 \
  --reason "Belge onayı" \
  --location "İstanbul"
```

## 📁 Proje Yapısı

```
.
├── gui.py                        ⭐ Ana GUI (ttkbootstrap)
├── sign_pdf.py                   🔧 İmzalama motoru (backend)
├── constants.py                  ⚙️  Sabit değerler & konfigürasyonlar
├── __main__.py                   📍 Entry point
├── requirements.txt              📦 Python bağımlılıkları
└── README.md                     📚 Bu dosya
```

### Dosya Açıklamaları

| Dosya | Amaç |
|-------|------|
| `gui.py` | Ana GUI uygulaması - kullanıcı arayüzü, event handling |
| `sign_pdf.py` | PDF imzalama ve PKCS#11 yönetimi - saf backend |
| `constants.py` | Merkezi sabit değerler - UI boyutları, varsayılan ayarlar |
| `__main__.py` | PyInstaller ve modül çalıştırma desteği |

## 🔒 Güvenlik Notları

- 🔐 **PIN hiçbir zaman kaydedilmez** - Her imzalama işleminde girilir
- 🔐 **Detached imza** - Orijinal PDF değiştirilmez
- ✅ **Adobe/Acrobat uyumlu** - İmzalar standart reader'larda doğrulanır
- ✅ **PAdES ISO 32000-2** - Uluslararası standart imza formatı

## 🛠️ Konfigürasyon

Ayarlar `~/.imzaci/config.json` dosyasında kaydedilir:

```json
{
  "pkcs11_dll": "C:\\Windows\\System32\\akisp11.dll",
  "signature": {
    "width_mm": 30.0,
    "logo_width_mm": 15.0,
    "margin_x_mm": 12.0,
    "margin_y_mm": 12.0,
    "placement": "top-right"
  }
}
```

## 🐛 Sorun Giderme

### PKCS#11 DLL Bulunamıyor
```powershell
# Sistem32'de PKCS#11 DLL'lerini ara
Get-ChildItem C:\Windows\System32 -Filter *pkcs11* -o List
Get-ChildItem C:\Windows\System32 -Filter akisp* -o List
```

### Token Algılanmıyor
1. USB tokeni çıkar/takın
2. Sürücüleri yeniden yükleyin
3. GUI'de "Yenile" butonuna tıkla
4. Windows Cihaz Yöneticisi'nde kontrol et

### İmzalama Başarısız
- Log penceresindeki hata mesajını oku
- PIN'i doğrula
- PDF dosyasını kontrol et
- Token'ı yeniden tak

## 📦 Dağıtım

### PyInstaller ile EXE Oluştur
```powershell
pip install pyinstaller
pyinstaller imzaci.spec
```

Çıktı: `dist/imzaci.exe` (bağımsız çalışabilir)

## 📚 Teknoloji Stack

| Bileşen | Amaç |
|---------|------|
| [pyHanko](https://github.com/MatthiasValvekens/pyHanko) | PDF imzalama (PAdES) |
| [python-pkcs11](https://github.com/openegos/python-pkcs11) | PKCS#11 token API |
| [ttkbootstrap](https://ttkbootstrap.readthedocs.io/) | Modern GUI framework |
| [pikepdf](https://pikepdf.readthedocs.io/) | PDF işlemleri |
| [cryptography](https://cryptography.io/) | Kriptografi işlemleri |

## 📝 Lisans

Bu proje açık kaynaklı olup eğitim ve ticari amaçla kullanılabilir.

---

**Son Güncelleme:** Şubat 2026  
**Versiyon:** 2.4
