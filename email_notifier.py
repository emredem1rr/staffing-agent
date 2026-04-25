"""
Müşteriye otomatik email yanıtı.

1. Talep alındığında → "Talebiniz alındı" maili
2. Tamamlandığında → "Personel atandı" maili
3. Kısmi dolduysa → Durum güncelleme maili

Gmail SMTP kullanır (aynı uygulama şifresiyle).
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD
import database as db


def _send_email(to_email: str, subject: str, body_html: str) -> bool:
    """Gmail SMTP ile email gönder."""
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD or "YOUR_" in GMAIL_APP_PASSWORD:
        print(f"  ⚠️  Gmail ayarları eksik, email gönderilemiyor")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"Personel Agent <{GMAIL_ADDRESS}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)

        print(f"  ✅ Email gönderildi → {to_email}: {subject}")
        return True
    except Exception as e:
        print(f"  ❌ Email gönderilemedi → {to_email}: {e}")
        return False


def send_request_received(client_name: str, client_email: str,
                          request_id: int, original_message: str):
    """Talep alındı bildirimi."""
    if not client_email:
        return

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
        <div style="background:#7c6aef;color:white;padding:20px;border-radius:12px 12px 0 0;">
            <h2 style="margin:0;">✅ Talebiniz Alındı</h2>
        </div>
        <div style="background:#f8f9fa;padding:24px;border-radius:0 0 12px 12px;">
            <p>Merhaba <strong>{client_name}</strong>,</p>
            <p>Personel talebiniz başarıyla alınmıştır ve AI sistemimiz tarafından işlenmektedir.</p>
            <div style="background:white;padding:16px;border-radius:8px;border-left:4px solid #7c6aef;margin:16px 0;">
                <strong>Talep #{request_id}</strong><br>
                <em>"{original_message[:200]}{'...' if len(original_message) > 200 else ''}"</em>
            </div>
            <p>Uygun personellerimize davet gönderilmiştir. Kontenjan dolduğunda size bilgi verilecektir.</p>
            <p style="color:#888;font-size:13px;margin-top:24px;">
                Bu email otomatik olarak gönderilmiştir. — Personel Agent Sistemi
            </p>
        </div>
    </div>"""

    _send_email(client_email, f"Talebiniz alındı — #{request_id}", html)

    db.log_activity(request_id, "email_notifier", "client_email_sent",
                    f"Talep alındı emaili gönderildi → {client_email}")


def send_request_fulfilled(client_name: str, client_email: str,
                           request_id: int, assignments: list):
    """Talep tamamlandı — atanan personel listesi."""
    if not client_email:
        return

    staff_rows = ""
    for a in assignments:
        if a.get("status") == "accepted":
            staff_rows += f"""
            <tr>
                <td style="padding:8px 12px;border-bottom:1px solid #eee;">{a.get('staff_name','?')}</td>
                <td style="padding:8px 12px;border-bottom:1px solid #eee;">{a.get('role','?')}</td>
            </tr>"""

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
        <div style="background:#34d399;color:white;padding:20px;border-radius:12px 12px 0 0;">
            <h2 style="margin:0;">🎉 Personel Ataması Tamamlandı</h2>
        </div>
        <div style="background:#f8f9fa;padding:24px;border-radius:0 0 12px 12px;">
            <p>Merhaba <strong>{client_name}</strong>,</p>
            <p>Talep #{request_id} için tüm personel atamaları tamamlanmıştır.</p>
            <table style="width:100%;border-collapse:collapse;margin:16px 0;background:white;border-radius:8px;">
                <thead>
                    <tr style="background:#f1f3f5;">
                        <th style="padding:10px 12px;text-align:left;">Personel</th>
                        <th style="padding:10px 12px;text-align:left;">Pozisyon</th>
                    </tr>
                </thead>
                <tbody>{staff_rows}</tbody>
            </table>
            <p>Personellerimiz zamanında hazır olacaktır. İyi etkinlikler dileriz!</p>
            <p style="color:#888;font-size:13px;margin-top:24px;">
                Bu email otomatik olarak gönderilmiştir. — Personel Agent Sistemi
            </p>
        </div>
    </div>"""

    _send_email(client_email, f"Personel ataması tamamlandı — #{request_id}", html)

    db.log_activity(request_id, "email_notifier", "fulfilled_email_sent",
                    f"Tamamlandı emaili gönderildi → {client_email}")


def send_status_update(client_name: str, client_email: str,
                       request_id: int, status_message: str):
    """Genel durum güncelleme emaili."""
    if not client_email:
        return

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
        <div style="background:#60a5fa;color:white;padding:20px;border-radius:12px 12px 0 0;">
            <h2 style="margin:0;">📋 Durum Güncellemesi</h2>
        </div>
        <div style="background:#f8f9fa;padding:24px;border-radius:0 0 12px 12px;">
            <p>Merhaba <strong>{client_name}</strong>,</p>
            <p>Talep #{request_id} ile ilgili güncelleme:</p>
            <div style="background:white;padding:16px;border-radius:8px;border-left:4px solid #60a5fa;margin:16px 0;">
                {status_message}
            </div>
            <p style="color:#888;font-size:13px;margin-top:24px;">
                Bu email otomatik olarak gönderilmiştir. — Personel Agent Sistemi
            </p>
        </div>
    </div>"""

    _send_email(client_email, f"Durum güncellemesi — #{request_id}", html)
