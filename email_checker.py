"""
Gmail Talep Okuyucu — IMAP ile gelen talepleri otomatik işle.

Belirli aralıklarla Gmail'i kontrol eder. Konu satırında
"talep", "personel", "organizasyon" gibi anahtar kelimeler
varsa otomatik olarak sisteme talep oluşturur.

Kurulum:
  1. Gmail → Ayarlar → Tüm ayarları gör → Yönlendirme ve POP/IMAP
     → IMAP erişimini etkinleştir
  2. Google Hesabı → Güvenlik → 2 Adımlı Doğrulama açık olmalı
  3. Google Hesabı → Güvenlik → Uygulama şifreleri → Yeni şifre oluştur
     → "Mail" + "Windows Computer" seç → oluşan 16 haneli şifreyi kopyala
  4. config.py'de GMAIL ayarlarını doldur
"""

import imaplib
import email
from email.header import decode_header
import asyncio
import time
from datetime import datetime

import database as db
from config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD, EMAIL_CHECK_ENABLED


def decode_mime_header(header):
    """MIME kodlu başlığı decode et."""
    if not header:
        return ""
    decoded = decode_header(header)
    parts = []
    for data, charset in decoded:
        if isinstance(data, bytes):
            parts.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(data)
    return " ".join(parts)


def get_email_body(msg):
    """Email gövdesini çıkar."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    break
                except Exception:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode("utf-8", errors="replace")
        except Exception:
            pass
    return body.strip()


async def check_gmail_for_requests():
    """Gmail'den yeni talepleri kontrol et ve sisteme ekle."""
    if not EMAIL_CHECK_ENABLED:
        return []

    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("⚠️  Gmail ayarları eksik (config.py)")
        return []

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        mail.select("inbox")

        new_requests = []

        # Tüm okunmamış mailleri çek, konu filtresini Python tarafında yap
        # (IMAP SUBJECT araması Türkçe karakterlerde sorun çıkarabilir)
        status, messages = mail.search(None, "UNSEEN")
        if status != "OK" or not messages[0]:
            mail.logout()
            return []

        msg_ids = messages[0].split()
        print(f"\n📧 {len(msg_ids)} okunmamış mail kontrol ediliyor...")

        # Konu eşleşme kalıpları — büyük/küçük harf, noktalı/noktasız, yazım hataları
        subject_patterns = [
            "personel talebi",
            "personel taleb",
            "personel talebı",
            "personel talebİ",
            "personel talep",
            "personel ihtiyaci",
            "personel ihtiyacı",
            "personel gerekiyor",
            "personel lazim",
            "personel lazım",
            "eleman talebi",
            "eleman talep",
            "eleman lazim",
            "eleman lazım",
            "eleman ihtiyaci",
            "eleman ihtiyacı",
        ]

        def normalize_turkish(text):
            """Türkçe karakterleri ASCII'ye çevir + küçük harf."""
            replacements = {
                "ı": "i", "İ": "i", "ğ": "g", "Ğ": "g",
                "ü": "u", "Ü": "u", "ş": "s", "Ş": "s",
                "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
            }
            text = text.lower()
            for tr_char, en_char in replacements.items():
                text = text.replace(tr_char, en_char)
            return text

        for msg_id in msg_ids[-10:]:
            # Önce sadece header oku (maili okundu işaretleme)
            status_h, data_h = mail.fetch(msg_id, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])")
            if status_h != "OK":
                continue

            header_raw = data_h[0][1].decode("utf-8", errors="replace")
            msg_peek = email.message_from_string(header_raw)
            subject_raw = decode_mime_header(msg_peek.get("Subject", ""))

            # Normalize et ve kalıpları kontrol et
            subject_norm = normalize_turkish(subject_raw)
            matched = any(normalize_turkish(p) in subject_norm for p in subject_patterns)

            if not matched:
                continue

            # Filtreden geçti — tam maili oku
            status2, data2 = mail.fetch(msg_id, "(RFC822)")
            if status2 != "OK":
                continue

            msg = email.message_from_bytes(data2[0][1])
            subject = decode_mime_header(msg["Subject"])
            sender = decode_mime_header(msg["From"])
            body = get_email_body(msg)

            # Gönderen adını çıkar
            sender_name = sender
            if "<" in sender:
                sender_name = sender.split("<")[0].strip().strip('"')
            sender_email = ""
            if "<" in sender and ">" in sender:
                sender_email = sender.split("<")[1].split(">")[0]

            print(f"\n  📨 Talep maili bulundu!")
            print(f"  Kimden: {sender_name} ({sender_email})")
            print(f"  Konu: {subject}")
            print(f"  Mesaj: {body[:100]}...")

            # Mesajı oluştur — konu + gövde birleşik
            request_message = f"{subject}. {body}" if body else subject

            # Önceliği mesaj içeriğinden otomatik algıla
            msg_lower = request_message.lower()
            if any(w in msg_lower for w in ["acil", "urgent", "hemen", "şimdi", "simdi"]):
                priority = "urgent"
            elif any(w in msg_lower for w in ["bugün", "bugun", "today", "bu akşam", "bu aksam"]):
                priority = "high"
            elif any(w in msg_lower for w in ["yarın", "yarin", "tomorrow"]):
                priority = "high"
            else:
                priority = "normal"

            # Sisteme talep oluştur
            from crew_agents import CoordinatorAgent

            req_id = db.create_request(
                client_name=sender_name or "Email Talebi",
                message=request_message,
                contact_email=sender_email,
                priority=priority,
            )

            db.log_activity(req_id, "email_checker", "email_received",
                f"Email'den talep oluşturuldu: {sender_name} ({sender_email})")

            # Agent'ı çalıştır
            coordinator = CoordinatorAgent()
            result = await coordinator.process_request(req_id)

            new_requests.append({
                "request_id": req_id,
                "from": sender_name,
                "email": sender_email,
                "subject": subject,
                "result": result,
            })

            # Maili okundu olarak işaretle
            mail.store(msg_id, "+FLAGS", "\\Seen")

            print(f"  ✅ Talep #{req_id} oluşturuldu ve agent işledi")

        mail.logout()
        return new_requests

    except imaplib.IMAP4.error as e:
        print(f"⚠️  Gmail bağlantı hatası: {e}")
        print("   → Gmail IMAP açık mı? Uygulama şifresi doğru mu?")
        return []
    except Exception as e:
        print(f"⚠️  Email kontrol hatası: {e}")
        return []


async def email_check_loop(interval_seconds=60):
    """Belirli aralıklarla Gmail'i kontrol et."""
    print(f"📧 Email kontrolü başlatıldı ({interval_seconds}s aralıkla)")

    while True:
        try:
            results = await check_gmail_for_requests()
            if results:
                print(f"📧 {len(results)} yeni talep email'den oluşturuldu")
        except Exception as e:
            print(f"⚠️  Email döngü hatası: {e}")

        await asyncio.sleep(interval_seconds)