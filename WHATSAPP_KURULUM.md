# WhatsApp Entegrasyonu — Twilio Kurulum Rehberi

## Twilio ile gerçek WhatsApp mesajı gönderilir ve yanıtlar otomatik alınır.

---

## ADIM 1 — Twilio Hesabı Aç

1. https://www.twilio.com/try-twilio adresine git
2. Ücretsiz hesap oluştur (kredi kartı gerekmez)
3. Email ve telefon doğrulamasını tamamla
4. Dashboard'a gir

## ADIM 2 — Twilio Bilgilerini Al

Twilio Console → Account Info bölümünden şu iki bilgiyi kopyala:

- **Account SID** → `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` formatında
- **Auth Token** → gizli token, "Show" tıklayarak gör

## ADIM 3 — WhatsApp Sandbox Aktifleştir

1. Twilio Console → Messaging → Try it out → Send a WhatsApp message
2. Sayfada bir "join xxxxxx" kodu göreceksin
3. Kendi telefonundan Twilio'nun WhatsApp numarasına
   (+1 415 523 8886) bu kodu gönder
4. "You are all set!" yanıtı gelecek

**ÖNEMLİ:** Test edeceğin HER telefon numarası bu join
kodunu Twilio'ya göndermelidir! Yoksa mesaj iletilmez.

## ADIM 4 — config.py Dosyasını Düzenle

`config.py` dosyasını aç ve kendi bilgilerini yaz:

```python
TWILIO_ACCOUNT_SID    = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
TWILIO_AUTH_TOKEN     = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
TWILIO_WHATSAPP_FROM  = "whatsapp:+14155238886"  # Sandbox numarası
MESSAGING_MODE        = "whatsapp"
```

## ADIM 5 — Twilio Paketini Kur

```powershell
pip install twilio python-multipart
```

## ADIM 6 — Test Et

Sunucuyu başlat ve bir talep oluştur:

```powershell
python main.py
```

Dashboard'dan veya API'den talep oluşturduğunda, kayıtlı
personellerin telefonuna gerçek WhatsApp mesajı gidecek.

---

## Gelen Yanıtları Otomatik Alma (Webhook)

Personel "EVET" veya "HAYIR" yazdığında Twilio bunu senin
sunucuna geri bildirir. Bunun için webhook kurulumu gerekir.

### Yöntem A — ngrok ile (local geliştirme)

1. ngrok kur: https://ngrok.com/download
2. Terminal aç:
   ```powershell
   ngrok http 8000
   ```
3. ngrok sana bir URL verecek, mesela:
   ```
   https://a1b2c3d4.ngrok-free.app
   ```
4. Twilio Console → Messaging → Settings → WhatsApp Sandbox
5. "When a message comes in" alanına yaz:
   ```
   https://a1b2c3d4.ngrok-free.app/webhook/whatsapp
   ```
6. HTTP Method: POST seç
7. Save tıkla

Artık personel WhatsApp'tan EVET/HAYIR yazdığında:
- Twilio → ngrok → senin sunucun → agent otomatik işler
- Kabul eden personele onay mesajı otomatik gider
- Kontenjan doluysa "doldu" mesajı otomatik gider

### Yöntem B — Production (gerçek sunucu)

Eğer projeni bir sunucuya deploy edersen (VPS, Heroku, Railway vb.):

1. Webhook URL'ini kendi domainine yaz:
   ```
   https://senin-domain.com/webhook/whatsapp
   ```
2. config.py'de güncelle:
   ```python
   WEBHOOK_BASE_URL = "https://senin-domain.com"
   ```

---

## Mesaj Akışı

```
1. Müşteri talep oluşturur (Dashboard / API)
         ↓
2. Agent talebi analiz eder (LLM)
         ↓
3. Uygun personeller bulunur (Matcher Agent)
         ↓
4. Her personele WhatsApp mesajı gider (Twilio)
    "Merhaba Ahmet, yarın 10:00'da Sheraton'da
     garson olarak çalışır mısın? EVET / HAYIR"
         ↓
5. Personel telefonundan "EVET" yazar
         ↓
6. Twilio → Webhook → Agent otomatik işler
         ↓
7. Personele onay mesajı gider:
    "✅ Atamanız onaylandı! 📍 Sheraton Maslak
     📅 25 Ocak 🕐 10:00 👔 Garson"
         ↓
8. Kontenjan dolunca diğerlerine:
    "Kontenjan doldu, bir sonraki sefer!"
         ↓
9. Müşteriye rapor gider
```

---

## Sık Sorulan Sorular

**"Mesaj gitmiyor"**
→ Personel telefonu Twilio sandbox'a join kodu gönderdi mi?
→ config.py'deki SID ve Token doğru mu?
→ Telefon numarası +90 ile başlıyor mu?

**"Sandbox süresi doldu"**
→ Sandbox 72 saat sonra devre dışı kalır.
→ Personelin tekrar join kodu göndermesi gerekir.
→ Production'da bu sorun olmaz (onaylı numara alınca).

**"Webhook çalışmıyor"**
→ ngrok açık mı? URL'i Twilio'ya doğru yazdın mı?
→ HTTP Method "POST" seçili mi?
→ Terminal'de "GELEN WHATSAPP YANITI" yazısı görünüyor mu?

**"MESSAGING_MODE = console yaparsam ne olur?"**
→ Gerçek mesaj gitmez, sadece konsola yazar.
→ Test/demo için kullanışlı.

**Production'a geçiş:**
→ Twilio'dan kendi WhatsApp Business numaranı al
→ config.py'de TWILIO_WHATSAPP_FROM'u güncelle
→ Meta Business onayı gerekir (1-2 hafta sürebilir)