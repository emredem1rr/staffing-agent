"""
Otomatik hatırlatma sistemi.

Etkinlikten 2 saat önce kabul etmiş personele WhatsApp hatırlatma gönderir.
Arka planda sürekli çalışır, her dakika kontrol eder.
"""

import asyncio
from datetime import datetime, timedelta
import database as db
import messaging


async def check_and_send_reminders():
    """Yaklaşan etkinlikler için hatırlatma gönder."""
    now = datetime.now()
    today = now.date().isoformat()
    
    # Bugünkü tüm onaylanmış programları al
    conn = db.get_db()
    rows = conn.execute("""
        SELECT s.id as schedule_id, s.staff_id, s.request_id, s.date,
               s.start_time, s.location, s.client_name, s.role,
               st.name as staff_name, st.phone as staff_phone
        FROM schedule s
        JOIN staff st ON s.staff_id = st.id
        WHERE s.date = ? AND s.status = 'confirmed'
    """, (today,)).fetchall()
    conn.close()

    if not rows:
        return 0

    sent_count = 0
    for row in rows:
        row = dict(row)
        try:
            # Etkinlik başlangıç zamanını hesapla
            event_start = datetime.strptime(
                f"{row['date']} {row['start_time']}", "%Y-%m-%d %H:%M")
            
            # 2 saat önce mi kontrol et (1:50 - 2:10 arası pencere)
            diff = (event_start - now).total_seconds() / 60  # dakika
            
            if 110 <= diff <= 130:  # ~2 saat önce (10 dk tolerans)
                # Daha önce hatırlatma gönderilmiş mi?
                conn = db.get_db()
                already = conn.execute("""
                    SELECT COUNT(*) as cnt FROM messages_log
                    WHERE staff_id=? AND request_id=? AND message_type='reminder'
                """, (row["staff_id"], row["request_id"])).fetchone()
                conn.close()

                if already["cnt"] > 0:
                    continue  # Zaten gönderilmiş

                reminder_msg = (
                    f"⏰ Hatırlatma!\n\n"
                    f"Merhaba {row['staff_name']}, bugün bir etkinliğiniz var:\n\n"
                    f"📍 {row.get('location', 'Bildirilecek')}\n"
                    f"🕐 Saat: {row['start_time']}\n"
                    f"👔 Pozisyon: {row.get('role', '?')}\n"
                    f"🏢 Müşteri: {row.get('client_name', '?')}\n\n"
                    f"Lütfen zamanında hazır olun. İyi çalışmalar! 💪"
                )

                messaging.send_reminder(
                    staff_id=row["staff_id"],
                    staff_name=row["staff_name"],
                    staff_phone=row["staff_phone"],
                    request_id=row["request_id"],
                    message=reminder_msg,
                )

                db.log_activity(row["request_id"], "reminder", "reminder_sent",
                    f"⏰ Hatırlatma gönderildi → {row['staff_name']} ({row['start_time']})")

                sent_count += 1
                print(f"  ⏰ Hatırlatma → {row['staff_name']} (etkinlik {row['start_time']})")

        except Exception as e:
            print(f"  ⚠️ Hatırlatma hatası: {e}")

    return sent_count


async def reminder_loop(interval_seconds=60):
    """Her dakika hatırlatma kontrolü yap."""
    print("⏰ Hatırlatma sistemi başlatıldı")
    while True:
        try:
            count = await check_and_send_reminders()
            if count > 0:
                print(f"⏰ {count} hatırlatma gönderildi")
        except Exception as e:
            print(f"⚠️ Hatırlatma döngü hatası: {e}")
        await asyncio.sleep(interval_seconds)
