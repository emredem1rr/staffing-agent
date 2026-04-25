# Otonom Personel Yönetim Agent'ı

> Yapay Zeka dersi bitirme projesi — Multi-Agent AI ile otel/etkinlik sektörü için otonom personel yönetim sistemi.

## Özellikler

- **Multi-Agent Mimarisi** — 4 uzman AI agent (Coordinator, Analyzer, Matcher, Communicator)
- **Doğal Dil Analizi** — Müşteri mesajından pozisyon, tarih, saat, konum otomatik çıkarır (Ollama/llama3.1)
- **WhatsApp Entegrasyonu** — Twilio ile personele gerçek WhatsApp daveti gönderir; EVET/HAYIR/İPTAL işler
- **Gmail Entegrasyonu** — Gelen talep emaillerini otomatik okur ve işler; müşteriye durum emaili gönderir
- **Takvim ve Çakışma Kontrolü** — Personelin başka etkinliğe atanıp atanmadığını kontrol eder
- **Yedek Personel** — Red gelince sıradaki yedek otomatik davet edilir
- **Uzun Süreli Hafıza** — Agent, müşteri ve personel kalıplarını hatırlar
- **Hatırlatma Sistemi** — Etkinlikten 2 saat önce WhatsApp hatırlatması gönderir
- **Dashboard** — Chart.js ile canlı istatistik ve agent aktivite logu

## Teknolojiler

| Katman | Teknoloji |
|--------|-----------|
| Backend | FastAPI + Uvicorn |
| AI / LLM | Ollama (llama3.1:8b) — yerel, API ücreti yok |
| Agent Çerçevesi | CrewAI pattern (özel implementasyon) |
| Mesajlaşma | Twilio WhatsApp API |
| Email | Gmail IMAP (okuma) + SMTP (gönderme) |
| Veritabanı | SQLite (WAL modu) |
| Veri Modeli | Pydantic v2 |

## Mimari

```
Müşteri talebi (WhatsApp / Email / API)
              │
              ▼
    ┌─────────────────┐
    │   Coordinator   │  ← Tüm pipeline'ı yönetir
    └────────┬────────┘
             │
     ┌───────┼────────┐
     ▼       ▼        ▼
 Analyzer  Matcher  Communicator
    │         │         │
    │ JSON    │ Puan    │ Mesaj
    │ çıkar   │ sırala  │ yaz
     \        │        /
      └───────┴───────┘
              │
              ▼
    WhatsApp Davetleri
              │
    EVET / HAYIR / İPTAL
              │
              ▼
    Kontenjan dolunca → Müşteriye email
```

## Dosya Yapısı

```
staffing-agent/
├── main.py            ← FastAPI endpoints
├── crew_agents.py     ← 4 agent implementasyonu
├── llm.py             ← Ollama bağlantı katmanı
├── database.py        ← SQLite (6 tablo)
├── models.py          ← Pydantic modeller
├── messaging.py       ← Twilio WhatsApp gönderim
├── email_checker.py   ← Gmail IMAP okuyucu
├── email_notifier.py  ← Gmail SMTP göndericisi
├── webhook.py         ← Twilio webhook handler
├── reminder.py        ← Otomatik hatırlatma sistemi
├── dashboard.html     ← React + Chart.js dashboard
├── seed_data.py       ← 25 örnek personel verisi
├── test_scenario.py   ← Uçtan uca test
├── .env               ← Gerçek anahtarlar (gitignore'da)
├── .env.example       ← Örnek yapı (GitHub'a gider)
└── requirements.txt   ← Bağımlılıklar
```

## Kurulum

### 1. Ollama (yerel LLM)

```bash
# Ollama'yı yükle: https://ollama.com
ollama pull llama3.1:8b
ollama serve
```

### 2. Proje

```bash
git clone <repo-url>
cd staffing-agent

python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Ortam değişkenleri

```bash
cp .env.example .env
# .env dosyasını düzenle — Twilio ve Gmail bilgilerini gir
```

`.env` için gereken anahtarlar:
- **Twilio**: [console.twilio.com](https://console.twilio.com) → Account SID + Auth Token
- **Gmail**: Google Hesabı → Güvenlik → 2 Adımlı Doğrulama → Uygulama Şifreleri → 16 haneli şifre

### 4. Veri yükle ve başlat

```bash
python seed_data.py   # 25 örnek personel ekler

# WhatsApp webhook için (Twilio'ya URL vermek gerekiyorsa):
ngrok http 8000       # Terminal 1

python main.py        # Terminal 2
```

### 5. Bağlantılar

| Sayfa | URL |
|-------|-----|
| Dashboard | http://localhost:8000/dashboard |
| API Docs (Swagger) | http://localhost:8000/docs |
| WhatsApp Webhook | http://localhost:8000/webhook/whatsapp |

## Hızlı Test

```bash
python test_scenario.py
```

Veya Swagger UI'dan `/api/requests` endpoint'ine POST:

```json
{
  "client_name": "Sheraton İstanbul",
  "message": "Yarın akşam 18:00 Maslak'ta 3 garson ve 2 komi lazım",
  "contact_email": "test@sheraton.com",
  "priority": "high"
}
```

## Mesajlaşma Modu

`.env` dosyasında `MESSAGING_MODE` ayarı:

| Değer | Davranış |
|-------|----------|
| `console` | Mesajlar terminale yazılır (geliştirme/demo) |
| `whatsapp` | Twilio ile gerçek WhatsApp gönderilir |

## Ekran Görüntüleri

> Dashboard, API Docs ve WhatsApp akışı görselleri buraya eklenecek.

## Veritabanı Şeması

```
staff              → Personel bilgileri
staff_scores       → Performans puanları (güvenilirlik, kalite, hız)
client_requests    → Müşteri talepleri
assignments        → Personel-talep atamaları
schedule           → Personel takvimi (çakışma kontrolü için)
agent_memory       → Agent uzun süreli hafızası
agent_activity     → Canlı agent aktivite logu
messages_log       → Gönderilen tüm mesajlar
```
