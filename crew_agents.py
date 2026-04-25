"""
CrewAI Multi-Agent Personel Yönetim Sistemi — v4

- Puanlama YOK
- Red gelince yedek çağrılır
- İPTAL desteği
- Konum bazlı sıralama
- Tarih düzeltme
- Eksik bilgi geri bildirimi
- Müşteriye otomatik email
"""

import json
import time
import random
from datetime import datetime, timedelta

import database as db
from llm import call_llm, extract_json
import messaging
import email_notifier


ANALYZER_PROMPT = """Sen talep analizi uzmanı bir AI agent'sın.
Müşteri mesajlarını analiz eder, pozisyonları, tarihi, saati,
konumu çıkarırsın. JSON formatında çıktı ver. Türkçe düşün."""

MATCHER_PROMPT = """Sen personel eşleştirme uzmanı AI agent'sın.
Müsait personeli bulur, konum yakınlığına göre sıralar."""

COMMUNICATOR_PROMPT = """Sen iletişim uzmanı AI agent'sın.
Personele mesaj yazarsın — kısa, samimi, profesyonel.
WhatsApp formatında yaz."""


# ═══════════════════════════════════════════════════════
# TARİH DÜZELTME
# ═══════════════════════════════════════════════════════

def fix_date_from_message(message: str, parsed: dict) -> dict:
    today = datetime.now().date()
    msg = message.lower()
    date_val = str(parsed.get("date", "") or "").lower()

    mapping = {
        "bugün": today, "bugun": today, "today": today,
        "yarın": today + timedelta(days=1), "yarin": today + timedelta(days=1),
        "tomorrow": today + timedelta(days=1),
        "haftaya": today + timedelta(days=7),
    }

    for keyword, real_date in mapping.items():
        if keyword in date_val:
            parsed["date"] = real_date.isoformat()
            return parsed

    if not parsed.get("date") or parsed["date"] == "null" or parsed["date"] is None:
        for keyword, real_date in mapping.items():
            if keyword in msg:
                parsed["date"] = real_date.isoformat()
                return parsed
        parsed["date"] = today.isoformat()

    try:
        datetime.strptime(str(parsed["date"]), "%Y-%m-%d")
    except (ValueError, TypeError):
        parsed["date"] = today.isoformat()

    return parsed


def normalize_parsed_data(raw):
    """parsed_needs'i güvenli şekilde normalize et."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            raw = {}
    if not isinstance(raw, dict):
        raw = {}
    return raw


# ═══════════════════════════════════════════════════════
# KONUM YAKINLIK
# ═══════════════════════════════════════════════════════

def location_score(staff_loc: str, event_loc: str) -> float:
    if not staff_loc or not event_loc:
        return 0.5
    s, e = staff_loc.lower(), event_loc.lower()
    if s in e or e in s:
        return 1.0
    groups = {
        "avrupa": ["maslak","levent","şişli","sisli","beyoğlu","beyoglu",
                    "taksim","beşiktaş","besiktas","sarıyer","bomonti","kağıthane","eyüp"],
        "anadolu": ["kadıköy","kadikoy","üsküdar","uskudar","ataşehir",
                     "atasehir","maltepe","kartal","pendik","tuzla","beykoz"],
    }
    sg = eg = None
    for g, kws in groups.items():
        if any(k in s for k in kws): sg = g
        if any(k in e for k in kws): eg = g
    if sg and eg and sg == eg: return 0.8
    if sg and eg: return 0.3
    return 0.5


# ═══════════════════════════════════════════════════════
# 1. ANALYZER AGENT
# ═══════════════════════════════════════════════════════

class AnalyzerAgent:
    role = "analyzer"

    async def analyze(self, request_id: int) -> dict:
        request = db.get_request(request_id)
        if not request:
            return {"error": "Talep bulunamadı"}

        db.log_activity(request_id, self.role, "thinking",
                        f"Talep okunuyor: '{request['original_message'][:80]}...'")

        memories = db.recall_memory(category="client_pattern",
                                     keyword=request["client_name"])
        mem_ctx = f"\nGeçmiş: {memories[0]['content']}" if memories else ""

        today_str = datetime.now().strftime("%Y-%m-%d")
        tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        prompt = f"""Müşteri talebini analiz et, SADECE JSON döndür.

Bugün: {today_str} | Yarın: {tomorrow_str}

Müşteri: {request['client_name']}
Mesaj: "{request['original_message']}"
{mem_ctx}

"bugün" = {today_str}, "yarın" = {tomorrow_str}

JSON:
{{
    "location": "yer veya null",
    "date": "YYYY-MM-DD",
    "time": "HH:MM veya null",
    "end_time": "HH:MM veya null",
    "needs": [{{"role": "pozisyon", "count": sayı}}],
    "special_requirements": "not veya null",
    "confidence": 0.0-1.0
}}

Pozisyonlar: garson, komi, aşçı, bulaşıkçı, temizlikçi, barmen, host/hostes, vale, güvenlik
SADECE JSON yaz."""

        raw = await call_llm(prompt, ANALYZER_PROMPT)
        parsed = extract_json(raw)

        if not parsed:
            db.log_activity(request_id, self.role, "warning", "Parse hatası, fallback")
            parsed = {"needs": [{"role": "garson", "count": 3}], "confidence": 0.3}

        parsed = fix_date_from_message(request["original_message"], parsed)

        needs_str = ", ".join(f"{n['count']} {n['role']}" for n in parsed.get("needs", []))
        db.log_activity(request_id, self.role, "analysis_done",
                        f"Sonuç: {needs_str} | Tarih: {parsed.get('date')}", parsed)

        db.store_memory(
            key=f"client_{request['client_name'].lower().replace(' ','_')}",
            category="client_pattern",
            content=f"{request['client_name']}: {needs_str}. Konum: {parsed.get('location','?')}")

        db.update_request_parsed(request_id, parsed)

        # Eksik bilgi kontrolü
        missing = []
        loc = parsed.get("location")
        if not loc or loc == "null" or loc is None:
            missing.append("konum (etkinlik nerede yapılacak?)")
        dt = parsed.get("date")
        if not dt or dt == "null" or dt is None:
            missing.append("tarih (GG.AA.YYYY formatında)")
        tm = parsed.get("time")
        if not tm or tm == "null" or tm is None:
            missing.append("saat (örn: 18:00)")
        if not parsed.get("needs") or len(parsed.get("needs", [])) == 0:
            missing.append("pozisyon ve sayı (örn: 3 garson, 2 komi)")

        if missing:
            parsed["_missing_info"] = missing
            db.log_activity(request_id, self.role, "missing_info",
                f"⚠️ Eksik bilgi: {', '.join(missing)}")

        return parsed


# ═══════════════════════════════════════════════════════
# 2. MATCHER AGENT
# ═══════════════════════════════════════════════════════

class MatcherAgent:
    role = "matcher"

    async def match(self, request_id: int, parsed: dict) -> dict:
        request = db.get_request(request_id)
        db.log_activity(request_id, self.role, "thinking", "Personel aranıyor...")

        matches = {}
        ev_date = parsed.get("date")
        ev_start = parsed.get("time", "09:00")
        ev_end = parsed.get("end_time", "23:00")
        ev_location = parsed.get("location", "")

        for need in parsed.get("needs", []):
            role = need["role"]
            count = need["count"]
            available = db.get_available_staff_by_role(role)

            if ev_date:
                clean = []
                for s in available:
                    conflict = db.check_schedule_conflict(s["id"], ev_date, ev_start, ev_end)
                    if not conflict["has_conflict"]:
                        clean.append(s)
                    else:
                        db.log_activity(request_id, self.role, "conflict",
                            f"⚠️ {s['name']}: {conflict['message']}")
                available = clean

            if ev_location:
                for s in available:
                    s["_loc"] = location_score(s.get("location", ""), ev_location)
                available.sort(key=lambda x: x.get("_loc", 0.5), reverse=True)
            else:
                random.shuffle(available)

            if not available:
                matches[role] = {"needed": count, "invited": 0, "staff": []}
                db.log_activity(request_id, self.role, "warning",
                                f"'{role}' için müsait personel yok!")
                continue

            invite_count = min(len(available), max(count * 2, count + 3))
            selected = available[:invite_count]

            matches[role] = {
                "needed": count,
                "invited": len(selected),
                "staff": selected,
                "remaining": available[invite_count:],
            }

            names = ", ".join(s["name"] for s in selected)
            db.log_activity(request_id, self.role, "matched",
                f"'{role}': {count} gerekli → {len(selected)} davet, "
                f"{len(available) - invite_count} yedek: {names}")

        return matches


# ═══════════════════════════════════════════════════════
# 3. COMMUNICATOR AGENT
# ═══════════════════════════════════════════════════════

class CommunicatorAgent:
    role = "communicator"

    async def create_invitation(self, staff, role, request, parsed) -> str:
        date = parsed.get('date', 'yakında')
        time_ = parsed.get('time', 'bildirilecek')
        end_time = parsed.get('end_time', '')
        location = parsed.get('location', 'bildirilecek')
        time_str = f"{time_}-{end_time}" if end_time else time_

        prompt = f"""Bir personele iş daveti için SADECE kısa selamlama cümlesi yaz (1 cümle, max 15 kelime).
Personel: {staff['name']}, Pozisyon: {role}, Müşteri: {request['client_name']}.
SADECE selamlama yaz."""

        greeting = await call_llm(prompt, COMMUNICATOR_PROMPT)
        if not greeting or len(greeting) < 5:
            greeting = f"Merhaba {staff['name']}, sizin için bir iş fırsatımız var!"

        return (
            f"{greeting.strip()}\n\n"
            f"📍 Konum: {location}\n"
            f"📅 Tarih: {date}\n"
            f"🕐 Saat: {time_str}\n"
            f"👔 Pozisyon: {role}\n"
            f"🏢 Müşteri: {request['client_name']}\n\n"
            f"Kabul etmek için *EVET*\n"
            f"Reddetmek için *HAYIR*\n\n"
            f"yazmanız yeterli."
        )

    async def create_quota_full_message(self, staff_name, role, client_name) -> str:
        return (f"Merhaba {staff_name}, ilginiz için teşekkürler. "
                f"{role} pozisyonu için kontenjan doldu. "
                f"Sizi bir sonraki etkinlikte arayacağız! 🙏")

    async def create_client_report(self, request, assignments) -> str:
        accepted = [a for a in assignments if a["status"] == "accepted"]
        summary = ", ".join(f"{a['staff_name']} ({a['role']})" for a in accepted)
        return (f"Merhaba {request['client_name']}, talebiniz tamamlandı! "
                f"Atanan personel: {summary}. İyi etkinlikler!")


# ═══════════════════════════════════════════════════════
# 4. COORDINATOR AGENT
# ═══════════════════════════════════════════════════════

class CoordinatorAgent:
    role = "coordinator"

    def __init__(self):
        self.analyzer = AnalyzerAgent()
        self.matcher = MatcherAgent()
        self.communicator = CommunicatorAgent()

    async def process_request(self, request_id: int) -> dict:
        start = time.time()

        db.log_activity(request_id, self.role, "pipeline_start",
                        f"━━━ Talep #{request_id} başlatıldı ━━━")
        db.update_request_status(request_id, "analyzing")

        # 1. Analiz
        t1 = time.time()
        parsed = await self.analyzer.analyze(request_id)
        d1 = round(time.time() - t1, 1)
        if "error" in parsed:
            db.update_request_status(request_id, "failed")
            return {"status": "failed", "error": parsed["error"]}
        db.log_activity(request_id, self.role, "step_complete", f"✓ Analiz ({d1}s)")

        # Eksik bilgi varsa müşteriye geri mesaj gönder
        missing = parsed.get("_missing_info", [])
        if missing:
            missing_str = "\n".join(f"- {m}" for m in missing)
            feedback_msg = (
                f"Merhaba, talebiniz alındı (#{request_id}) ancak "
                f"bazı bilgiler eksik:\n\n{missing_str}\n\n"
                f"Lütfen bu bilgileri gönderiniz. Teşekkürler!"
            )
            request = db.get_request(request_id)
            contact_phone = request.get("contact_phone")
            contact_email = request.get("contact_email")
            if contact_phone:
                try:
                    messaging.send_reminder(0, "Müşteri", contact_phone,
                                            request_id, feedback_msg)
                except Exception:
                    pass
            if contact_email:
                try:
                    email_notifier.send_status_update(
                        request["client_name"], contact_email,
                        request_id, f"Eksik bilgiler: {', '.join(missing)}")
                except Exception:
                    pass
            db.log_activity(request_id, self.role, "feedback_sent",
                f"📩 Eksik bilgi bildirimi gönderildi: {', '.join(missing)}")

        # 2. Eşleştirme
        db.update_request_status(request_id, "matching")
        t2 = time.time()
        matches = await self.matcher.match(request_id, parsed)
        d2 = round(time.time() - t2, 1)
        db.log_activity(request_id, self.role, "step_complete", f"✓ Eşleştirme ({d2}s)")

        # 3. Mesajlar
        db.update_request_status(request_id, "messaging")
        t3 = time.time()
        request = db.get_request(request_id)

        for role, match_data in matches.items():
            for staff in match_data.get("staff", []):
                msg = await self.communicator.create_invitation(
                    staff, role, request, parsed)
                aid = db.create_assignment(
                    request_id=request_id, staff_id=staff["id"],
                    role=role, message_sent=msg)
                messaging.send_invitation(
                    staff["id"], staff["name"], staff["phone"],
                    request_id, aid, msg)
                db.log_activity(request_id, "communicator", "message_sent",
                    f"📱 Davet: {staff['name']} → {role}")

            remaining = match_data.get("remaining", [])
            if remaining:
                db.store_memory(
                    key=f"backup_{request_id}_{role}",
                    category="backup_pool",
                    content=json.dumps([s["id"] for s in remaining]))

        d3 = round(time.time() - t3, 1)
        total = round(time.time() - start, 1)
        total_invited = sum(m["invited"] for m in matches.values())

        result = {
            "status": "processing",
            "parsed_needs": parsed,
            "matches": {role: {"needed": m["needed"], "invited": m["invited"]}
                        for role, m in matches.items()},
            "pipeline_duration": total,
        }

        db.update_request_crew_result(request_id, result)
        db.log_activity(request_id, self.role, "pipeline_complete",
                        f"━━━ Tamamlandı ({total}s) — {total_invited} davet ━━━")

        email_notifier.send_request_received(
            request["client_name"], request.get("contact_email", ""),
            request_id, request["original_message"])

        return result

    # ── YANIT İŞLEME ──────────────────────────────────

    async def handle_response(self, staff_id: int, request_id: int, response: str) -> dict:
        assignment = db.get_invited_assignments_by_staff(staff_id, request_id)
        if not assignment:
            return {"error": "Aktif davet bulunamadı"}

        request = db.get_request(request_id)
        if not request:
            return {"error": "Request bulunamadı"}

        raw_parsed = request.get("parsed_needs") or {}
        parsed = normalize_parsed_data(raw_parsed)

        role = assignment["role"]
        staff = db.get_staff_by_id(staff_id)
        if not staff:
            return {"error": "Staff bulunamadı"}

        is_accept = response.lower().strip() in [
            "accept", "evet", "yes", "kabul", "tamam", "ok", "olur"]

        db.log_activity(request_id, self.role, "response_received",
            f"{staff['name']} ({role}): {'KABUL' if is_accept else 'RED'}")

        if is_accept:
            needed = 0
            for need in parsed.get("needs", []):
                if need["role"].lower() == role.lower():
                    needed = need["count"]
                    break

            current = db.get_accepted_count(request_id, role)

            if current >= needed:
                db.update_assignment_status(assignment["id"], "quota_full")
                messaging.send_quota_full(
                    staff_id, staff["name"], staff["phone"],
                    request_id, assignment["id"],
                    await self.communicator.create_quota_full_message(
                        staff["name"], role, request["client_name"]))
                return {"status": "quota_full"}

            db.update_assignment_status(assignment["id"], "accepted")
            db.record_job_accepted(staff_id)

            # Takvime ekle (güvenli)
            date = parsed.get("date")
            start_time = parsed.get("time") or "09:00"
            end_time = parsed.get("end_time") or "23:00"

            if date and start_time and end_time:
                try:
                    db.add_schedule_entry(
                        staff_id=staff_id, request_id=request_id,
                        date=date, start_time=start_time, end_time=end_time,
                        location=parsed.get("location"),
                        client_name=request.get("client_name"), role=role)
                except Exception as e:
                    print(f"SCHEDULE ERROR: {e}")

            filled = current + 1
            db.log_activity(request_id, self.role, "assigned",
                f"✅ {staff['name']} → {role} ({filled}/{needed})")

            if filled >= needed:
                await self._close_role_quota(request_id, role, needed)

            await self._check_fulfilled(request_id)
            return {"status": "accepted",
                    "message": f"{staff['name']} {role} ({filled}/{needed})"}

        else:
            db.update_assignment_status(assignment["id"], "declined")
            db.log_activity(request_id, self.role, "declined",
                f"❌ {staff['name']} → {role} reddetti")
            await self._invite_next_backup(request_id, role, request, parsed)
            return {"status": "declined",
                    "message": f"{staff['name']} reddetti, yedek aranıyor."}

    # ── YEDEK PERSONEL DAVET ──────────────────────────

    async def _invite_next_backup(self, request_id, role, request, parsed):
        needed = 0
        for need in parsed.get("needs", []):
            if need["role"].lower() == role.lower():
                needed = need["count"]
                break

        current_accepted = db.get_accepted_count(request_id, role)
        current_pending = len(db.get_pending_invitations_for_role(request_id, role))

        if current_accepted >= needed:
            return
        if current_pending >= (needed - current_accepted):
            return

        mem = db.recall_memory(category="backup_pool",
                                keyword=f"backup_{request_id}_{role}")
        if not mem:
            db.log_activity(request_id, self.role, "no_backup",
                f"⚠️ '{role}' için yedek personel kalmadı!")
            return

        try:
            backup_ids = json.loads(mem[0]["content"])
        except (json.JSONDecodeError, KeyError):
            return

        if not backup_ids:
            return

        next_id = backup_ids.pop(0)
        staff = db.get_staff_by_id(next_id)
        if not staff:
            return

        db.store_memory(
            key=f"backup_{request_id}_{role}",
            category="backup_pool",
            content=json.dumps(backup_ids))

        msg = await self.communicator.create_invitation(staff, role, request, parsed)
        aid = db.create_assignment(
            request_id=request_id, staff_id=staff["id"],
            role=role, message_sent=msg)
        messaging.send_invitation(
            staff["id"], staff["name"], staff["phone"],
            request_id, aid, msg)

        db.log_activity(request_id, self.role, "backup_invited",
            f"🔄 Yedek davet: {staff['name']} → {role} "
            f"(kalan yedek: {len(backup_ids)})")

    # ── İPTAL İŞLEME ──────────────────────────────────

    async def handle_cancellation(self, staff_id, request_id, assignment_id) -> dict:
        staff = db.get_staff_by_id(staff_id)
        request = db.get_request(request_id)
        parsed = normalize_parsed_data(request.get("parsed_needs") or {})

        conn = db.get_db()
        row = conn.execute("SELECT role FROM assignments WHERE id=?",
                           (assignment_id,)).fetchone()
        role = row["role"] if row else "?"
        conn.close()

        db.update_assignment_status(assignment_id, "declined")
        db.record_job_cancelled(staff_id)

        conn = db.get_db()
        conn.execute("UPDATE schedule SET status='cancelled' WHERE staff_id=? AND request_id=?",
                     (staff_id, request_id))
        conn.commit()
        conn.close()

        db.log_activity(request_id, self.role, "cancellation",
            f"🚫 {staff['name']} {role} iptal etti!")
        db.update_request_status(request_id, "partially_filled")

        await self._invite_next_backup(request_id, role, request, parsed)
        return {"status": "cancelled", "role": role}

    # ── KONTENJAN KAPATMA ─────────────────────────────

    async def _close_role_quota(self, request_id, role, needed):
        db.log_activity(request_id, self.role, "quota_closed",
                        f"🔒 '{role}' kontenjanı doldu ({needed}/{needed})")

        pending = db.get_pending_invitations_for_role(request_id, role)
        request = db.get_request(request_id)

        for inv in pending:
            msg = await self.communicator.create_quota_full_message(
                inv["staff_name"], role, request["client_name"])
            db.update_assignment_status(inv["id"], "quota_full")
            messaging.send_quota_full(
                inv["staff_id"], inv["staff_name"], inv["staff_phone"],
                request_id, inv["id"], msg)
            db.log_activity(request_id, self.role, "quota_notify",
                f"📩 Kontenjan doldu → {inv['staff_name']}")

    async def _check_fulfilled(self, request_id):
        request = db.get_request(request_id)
        parsed = normalize_parsed_data(request.get("parsed_needs") or {})
        if not parsed:
            return

        all_filled = True
        for need in parsed.get("needs", []):
            if db.get_accepted_count(request_id, need["role"]) < need["count"]:
                all_filled = False
                break

        if all_filled:
            db.update_request_status(request_id, "fulfilled")
            db.log_activity(request_id, self.role, "fulfilled",
                            "🎉 Tüm pozisyonlar doldu!")

            assignments = db.get_assignments_for_request(request_id)
            report = await self.communicator.create_client_report(request, assignments)
            contact = request.get("contact_email") or request.get("contact_phone") or ""
            messaging.send_client_notification(
                request["client_name"], contact, report, request_id)

            db.log_activity(request_id, self.role, "client_notified",
                            f"Müşteri bilgilendirildi: {request['client_name']}")

            email_notifier.send_request_fulfilled(
                request["client_name"], request.get("contact_email", ""),
                request_id, assignments)
        else:
            db.update_request_status(request_id, "partially_filled")