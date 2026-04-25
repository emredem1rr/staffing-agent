"""
Uygulama ayarları — Twilio WhatsApp + genel konfigürasyon.

Gerçek değerler .env dosyasından okunur.
Örnek: .env.example dosyasına bak.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════
# TWILIO AYARLARI
# ═══════════════════════════════════════════════════════

# Twilio Console → Account Info bölümünden al:
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "YOUR_TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN",  "YOUR_TWILIO_AUTH_TOKEN")

# WhatsApp gönderici numara:
# - Sandbox için: "whatsapp:+14155238886" (Twilio'nun sabit sandbox numarası)
# - Production için: Twilio'dan onayladığın kendi numaran
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

# ═══════════════════════════════════════════════════════
# WEBHOOK AYARLARI
# ═══════════════════════════════════════════════════════

# Twilio'nun yanıtları göndereceği URL.
# Local test için ngrok kullan: ngrok http 8000
# Production için kendi domainin: https://senin-domain.com
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "http://localhost:8000")

# ═══════════════════════════════════════════════════════
# OLLAMA AYARLARI
# ═══════════════════════════════════════════════════════

OLLAMA_URL   = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL_NAME   = os.getenv("MODEL_NAME", "llama3.1:8b")

# ═══════════════════════════════════════════════════════
# UYGULAMA AYARLARI
# ═══════════════════════════════════════════════════════

APP_PORT     = int(os.getenv("APP_PORT", "8000"))
DB_PATH      = os.getenv("DB_PATH", "staffing_agent.db")

# Mesaj gönderim modu:
#   "whatsapp"  → Gerçek Twilio WhatsApp
#   "console"   → Sadece konsola yaz (test/demo)
MESSAGING_MODE = os.getenv("MESSAGING_MODE", "whatsapp")

# ═══════════════════════════════════════════════════════
# GMAIL AYARLARI (Email ile talep alma)
# ═══════════════════════════════════════════════════════

# Gmail adresin:
GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS", "your_gmail@gmail.com")

# Uygulama şifresi (normal şifren DEĞİL!):
# Google Hesabı → Güvenlik → 2 Adımlı Doğrulama → Uygulama şifreleri
# → Mail + Windows Computer → 16 haneli şifre
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "YOUR_GMAIL_APP_PASSWORD")

# Email kontrolü açık mı?
EMAIL_CHECK_ENABLED = os.getenv("EMAIL_CHECK_ENABLED", "true").lower() == "true"

# Kaç saniyede bir kontrol edilsin?
EMAIL_CHECK_INTERVAL = int(os.getenv("EMAIL_CHECK_INTERVAL", "60"))