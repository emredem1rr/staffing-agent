"""
Mesajlaşma modülü v2 — Gerçek Twilio WhatsApp entegrasyonu.

İki mod:
  - "whatsapp" → Twilio API ile gerçek WhatsApp mesajı gönderir
  - "console"  → Sadece konsola yazar (test/demo)

config.py dosyasındaki MESSAGING_MODE ayarı ile kontrol edilir.
"""

import database as db
from datetime import datetime
from config import (
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
    TWILIO_WHATSAPP_FROM, MESSAGING_MODE
)

# ── Twilio Client ─────────────────────────────────────

_twilio_client = None


def _get_twilio():
    """Lazy-load Twilio client."""
    global _twilio_client
    if _twilio_client is None:
        try:
            from twilio.rest import Client
            _twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            print("✅ Twilio WhatsApp client hazır")
        except ImportError:
            print("⚠️  twilio paketi bulunamadı! → pip install twilio")
            _twilio_client = False
        except Exception as e:
            print(f"⚠️  Twilio bağlantı hatası: {e}")
            _twilio_client = False
    return _twilio_client


def _format_whatsapp_number(phone: str) -> str:
    """Telefon numarasını WhatsApp formatına çevir.

    +905551234567 → whatsapp:+905551234567
    05551234567   → whatsapp:+905551234567
    5551234567    → whatsapp:+905551234567
    """
    phone = phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    if phone.startswith("whatsapp:"):
        return phone

    if phone.startswith("0") and len(phone) == 11:
        phone = "+90" + phone[1:]
    elif phone.startswith("5") and len(phone) == 10:
        phone = "+90" + phone
    elif not phone.startswith("+"):
        phone = "+" + phone

    return f"whatsapp:{phone}"


def _send_whatsapp(to_phone: str, message: str) -> dict:
    """Twilio ile gerçek WhatsApp mesajı gönder."""
    client = _get_twilio()

    if not client:
        print(f"⚠️  Twilio yok, konsola yazılıyor: {to_phone}")
        return {"status": "fallback_console", "sid": None}

    to = _format_whatsapp_number(to_phone)

    try:
        msg = client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=to,
            body=message
        )
        print(f"  ✅ WhatsApp gönderildi → {to} (SID: {msg.sid})")
        return {"status": "sent", "sid": msg.sid}
    except Exception as e:
        print(f"  ❌ WhatsApp gönderilemedi → {to}: {e}")
        return {"status": "failed", "error": str(e)}


def _send_console(to_phone: str, staff_name: str, message: str, msg_type: str):
    """Konsola yaz (test modu)."""
    icons = {"invitation": "📱", "quota_full": "🔴", "reminder": "⏰", "client": "✅"}
    print(f"\n{'='*55}")
    print(f"  {icons.get(msg_type, '📱')} {msg_type.upper()} [CONSOLE]")
    print(f"  Kime: {staff_name} ({to_phone})")
    print(f"  Mesaj: {message[:140]}{'...' if len(message) > 140 else ''}")
    print(f"  Zaman: {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*55}\n")


def _send(to_phone: str, staff_name: str, message: str, msg_type: str) -> dict:
    """Mesaj gönder — mode'a göre WhatsApp veya konsol."""
    if MESSAGING_MODE == "whatsapp":
        result = _send_whatsapp(to_phone, message)
        status_icon = "✅" if result["status"] == "sent" else "❌"
        print(f"  {status_icon} [{msg_type}] → {staff_name} ({to_phone})")
        return result
    else:
        _send_console(to_phone, staff_name, message, msg_type)
        return {"status": "console", "sid": None}


# ═══════════════════════════════════════════════════════
# DAVET MESAJI
# ═══════════════════════════════════════════════════════

def send_invitation(staff_id, staff_name, staff_phone,
                    request_id, assignment_id, message, channel="whatsapp"):
    result = _send(staff_phone, staff_name, message, "invitation")
    db.log_message(staff_id, request_id, "invitation", message, assignment_id, channel)
    return result


# ═══════════════════════════════════════════════════════
# KONTENJAN DOLDU
# ═══════════════════════════════════════════════════════

def send_quota_full(staff_id, staff_name, staff_phone,
                    request_id, assignment_id, message, channel="whatsapp"):
    result = _send(staff_phone, staff_name, message, "quota_full")
    db.log_message(staff_id, request_id, "quota_full", message, assignment_id, channel)
    return result


# ═══════════════════════════════════════════════════════
# MÜŞTERİ BİLDİRİM
# ═══════════════════════════════════════════════════════

def send_client_notification(client_name, contact, message, request_id):
    if contact and ("+" in contact or contact.startswith("0") or contact.startswith("5")):
        _send(contact, client_name, message, "client")
    else:
        print(f"\n  ✅ MÜŞTERİ BİLDİRİM → {client_name} ({contact})")
        print(f"  Mesaj: {message[:150]}...\n")


# ═══════════════════════════════════════════════════════
# HATIRLATMA
# ═══════════════════════════════════════════════════════

def send_reminder(staff_id, staff_name, staff_phone,
                  request_id, message, channel="whatsapp"):
    result = _send(staff_phone, staff_name, message, "reminder")
    db.log_message(staff_id, request_id, "reminder", message, channel=channel)
    return result