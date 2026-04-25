"""Twilio WhatsApp Webhook — EVET / HAYIR / İPTAL + müşteri talebi alma."""

from typing import Optional

from fastapi import APIRouter, Form
from fastapi.responses import Response

import database as db
from crew_agents import CoordinatorAgent

router = APIRouter()


def normalize_tr(text: str) -> str:
    """Türkçe karakterleri ASCII'ye çevir ve küçük harfe dönüştür."""
    replacements = {
        "ı": "i", "İ": "i", "ğ": "g", "Ğ": "g",
        "ü": "u", "Ü": "u", "ş": "s", "Ş": "s",
        "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
    }
    t = text.lower().strip()
    for tr_c, en_c in replacements.items():
        t = t.replace(tr_c, en_c)
    return t


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(
    From: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(None),
    ProfileName: str = Form(None),
):
    """Twilio'dan gelen WhatsApp mesajlarını işle."""
    phone = From.replace("whatsapp:", "").strip()
    body_raw = Body.strip()
    body_norm = normalize_tr(body_raw)
    sender_name = ProfileName or phone

    print(f"\n{'='*55}")
    print(f"  📩 GELEN WHATSAPP: {sender_name} ({phone})")
    print(f"  Mesaj: {body_raw}")
    print(f"{'='*55}\n")

    db.log_activity(None, "webhook", "whatsapp_received",
                    f"{sender_name} ({phone}): '{body_raw}'")

    staff = db.get_staff_by_phone(phone)

    if not staff:
        request_keywords = [
            "lazim", "gerekiyor", "istiyoruz",
            "garson", "komi", "barmen", "asci",
            "personel", "eleman", "talep",
        ]
        if any(kw in body_norm for kw in request_keywords):
            db.log_activity(None, "webhook", "whatsapp_request",
                            f"WhatsApp'tan talep: {sender_name} ({phone}): '{body_raw}'")

            req_id = db.create_request(
                client_name=sender_name,
                message=body_raw,
                contact_phone=phone,
                priority="normal",
            )
            coordinator = CoordinatorAgent()
            await coordinator.process_request(req_id)

            return _twiml_reply(
                f"✅ Talebiniz alındı! (#{req_id})\n\n"
                f"Personellerimize davet gönderildi. "
                f"Kontenjan dolduğunda size bilgi vereceğiz.\n\n"
                f"Teşekkürler, {sender_name}!"
            )

        return _twiml_reply(
            "Merhaba! Bu numara sistemimizde kayıtlı değil.\n\n"
            "Personel talebi göndermek için mesajınızda "
            "pozisyon ve sayı belirtin.\n"
            "Örnek: 'Yarın 18:00 için 3 garson lazım. Konum: Hilton Bomonti'"
        )

    accept_words = [
        "evet", "yes", "kabul", "tamam", "ok", "olur",
        "e", "1", "accept", "gelirim", "uygun", "musaitim", "musait",
    ]
    decline_words = [
        "hayir", "no", "red", "olmaz", "gelemem",
        "musait degilim", "h", "0", "decline", "pas", "yok",
    ]
    cancel_words = [
        "iptal", "vazgectim", "cancel", "gelemiyorum",
        "gelemicem", "gelmiyorum", "cikmak istiyorum",
    ]

    is_accept = body_norm in accept_words
    is_decline = body_norm in decline_words
    is_cancel = body_norm in cancel_words

    coordinator = CoordinatorAgent()

    if is_cancel:
        accepted = _find_accepted_assignment(staff["id"])
        if not accepted:
            return _twiml_reply(
                f"Merhaba {staff['name']}, iptal edilecek aktif atamanız yok."
            )
        await coordinator.handle_cancellation(
            staff["id"], accepted["request_id"], accepted["id"]
        )
        request = db.get_request(accepted["request_id"])
        return _twiml_reply(
            f"❌ {staff['name']}, {request['client_name']} etkinliğindeki "
            f"{accepted['role']} atamanız iptal edildi.\n\n"
            f"Yerinize başka personel aranacak. Teşekkürler."
        )

    if is_accept or is_decline:
        assignment = _find_active_invitation(staff["id"])
        if not assignment:
            return _twiml_reply(
                f"Merhaba {staff['name']}, şu an aktif bir davetiniz yok.\n\n"
                f"Atanmış işinizi iptal etmek için İPTAL yazabilirsiniz."
            )

        response_str = "accept" if is_accept else "decline"
        result = await coordinator.handle_response(
            staff["id"], assignment["request_id"], response_str
        )

        if result.get("status") == "accepted":
            request = db.get_request(assignment["request_id"])
            parsed = request.get("parsed_needs") or {}
            return _twiml_reply(
                f"✅ Teşekkürler {staff['name']}! Atamanız onaylandı.\n\n"
                f"📍 {parsed.get('location', 'Bildirilecek')}\n"
                f"📅 {parsed.get('date', 'Bildirilecek')}\n"
                f"🕐 {parsed.get('time', 'Bildirilecek')}\n"
                f"👔 Pozisyon: {assignment['role']}\n\n"
                f"İptal etmek isterseniz İPTAL yazın.\n"
                f"Lütfen zamanında hazır olun. İyi çalışmalar!"
            )

        if result.get("status") == "quota_full":
            return _twiml_reply(
                f"Merhaba {staff['name']}, yanıtınız için teşekkürler.\n\n"
                f"Maalesef bu pozisyon için kontenjan dolmuştur. "
                f"Sizi bir sonraki etkinlikte arayacağız! 🙏"
            )

        if result.get("status") == "declined":
            return _twiml_reply(
                f"Anlaşıldı {staff['name']}, teşekkürler.\n"
                f"Bir sonraki etkinlikte tekrar yazacağız. İyi günler! 👋"
            )

        return _twiml_reply(f"İşleminiz alındı. Teşekkürler {staff['name']}.")

    return _twiml_reply(
        f"Merhaba {staff['name']}, yanıtınızı anlayamadım.\n\n"
        f"✅ Kabul → EVET\n"
        f"❌ Red → HAYIR\n"
        f"🚫 İptal → İPTAL\n\n"
        f"yazmanız yeterli."
    )


# ═══════════════════════════════════════════════════════
# YARDIMCı FONKSİYONLAR
# ═══════════════════════════════════════════════════════

def _find_active_invitation(staff_id: int) -> Optional[dict]:
    """Personelin en son bekleyen davetini döndür."""
    conn = db.get_db()
    row = conn.execute("""
        SELECT a.*, cr.client_name
        FROM assignments a JOIN client_requests cr ON a.request_id = cr.id
        WHERE a.staff_id = ? AND a.status = 'invited'
        ORDER BY a.invited_at DESC LIMIT 1
    """, (staff_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _find_accepted_assignment(staff_id: int) -> Optional[dict]:
    """Personelin en son kabul ettiği aktif atamasını döndür."""
    conn = db.get_db()
    row = conn.execute("""
        SELECT a.*, cr.client_name
        FROM assignments a JOIN client_requests cr ON a.request_id = cr.id
        WHERE a.staff_id = ? AND a.status = 'accepted'
        ORDER BY a.responded_at DESC LIMIT 1
    """, (staff_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _twiml_reply(message: str) -> Response:
    """TwiML XML yanıtı oluştur."""
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f"<Response><Message>{message}</Message></Response>"
    )
    return Response(content=twiml, media_type="application/xml")
