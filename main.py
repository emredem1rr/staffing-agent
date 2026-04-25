"""
FastAPI Backend v2 — Multi-Agent + Hafıza + Puanlama + Takvim

Yeni endpoint'ler:
- /api/staff/{id}/score — Personel puanı
- /api/staff/{id}/schedule — Personel takvimi
- /api/activity — Canlı agent aktivite logu
- /api/memory — Agent hafızası
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn, os

import database as db
from models import StaffCreate, ClientRequestCreate, StaffReply
from crew_agents import CoordinatorAgent
from webhook import router as webhook_router
from config import APP_PORT, MESSAGING_MODE, EMAIL_CHECK_ENABLED, EMAIL_CHECK_INTERVAL
from email_checker import email_check_loop
from reminder import reminder_loop
import asyncio

app = FastAPI(
    title="Otonom Personel Yönetim Sistemi v2",
    description="Multi-Agent AI + Hafıza + Puanlama + Takvim",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# WhatsApp webhook
app.include_router(webhook_router)


@app.on_event("startup")
async def startup():
    db.init_db()
    mode_icon = "📱" if MESSAGING_MODE == "whatsapp" else "🖥️"
    print("=" * 55)
    print("  🤖 Otonom Personel Yönetim Sistemi v2")
    print(f"  {mode_icon} Mesajlaşma : {MESSAGING_MODE.upper()}")
    print("  📊 Dashboard : http://localhost:8000/dashboard")
    print("  📡 API Docs  : http://localhost:8000/docs")
    print("  📩 Webhook   : http://localhost:8000/webhook/whatsapp")
    print("  🧠 Agent'lar : Coordinator, Analyzer, Matcher, Communicator")
    print("=" * 55)
    if EMAIL_CHECK_ENABLED:
        asyncio.create_task(email_check_loop(EMAIL_CHECK_INTERVAL))
        print(f"  📧 Email kontrol AKTİF — her {EMAIL_CHECK_INTERVAL}s'de bir")
    else:
        print("  📧 Email kontrol KAPALI (config.py → EMAIL_CHECK_ENABLED=true)")
    # Hatırlatma sistemi her zaman aktif
    asyncio.create_task(reminder_loop(60))
    print("  ⏰ Hatırlatma sistemi AKTİF (etkinlikten 2 saat önce)")


@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    p = os.path.join(os.path.dirname(__file__), "dashboard.html")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>dashboard.html bulunamadı</h1>", status_code=404)


# ═══════════════════════════════════════════════════════
# STAFF
# ═══════════════════════════════════════════════════════

@app.post("/api/staff")
async def create_staff(data: StaffCreate):
    try:
        sid = db.create_staff(data.name, data.phone, data.roles,
                              data.email, data.location, data.hourly_rate)
        return {"id": sid, "message": f"{data.name} kaydedildi"}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/staff")
async def list_staff():
    return db.get_all_staff()


@app.get("/api/staff/{staff_id}")
async def get_staff(staff_id: int):
    s = db.get_staff_by_id(staff_id)
    if not s:
        raise HTTPException(404, "Personel bulunamadı")
    return s


@app.get("/api/staff/{staff_id}/schedule")
async def get_schedule(staff_id: int, date_from: str = None, date_to: str = None):
    return db.get_staff_schedule(staff_id, date_from, date_to)


@app.post("/api/staff/{staff_id}/complete-job")
async def complete_job(staff_id: int):
    db.record_job_completed(staff_id)
    return {"message": "İş tamamlandı olarak işaretlendi"}


@app.post("/api/staff/{staff_id}/no-show")
async def no_show(staff_id: int):
    db.record_no_show(staff_id)
    return {"message": "Gelmedi olarak işaretlendi, puan düşürüldü"}


# ═══════════════════════════════════════════════════════
# REQUESTS
# ═══════════════════════════════════════════════════════

@app.post("/api/requests")
async def create_request(data: ClientRequestCreate):
    req_id = db.create_request(
        data.client_name, data.message,
        data.contact_email, data.contact_phone,
        data.priority or "normal")

    coordinator = CoordinatorAgent()
    result = await coordinator.process_request(req_id)
    return {"request_id": req_id, "agent_result": result}


@app.get("/api/requests")
async def list_requests():
    return db.get_all_requests()


@app.get("/api/requests/{request_id}")
async def get_request(request_id: int):
    r = db.get_request(request_id)
    if not r:
        raise HTTPException(404, "Talep bulunamadı")
    return {
        **r,
        "assignments": db.get_assignments_for_request(request_id),
        "messages": db.get_messages_for_request(request_id),
        "activity": db.get_activity_for_request(request_id),
    }


# ═══════════════════════════════════════════════════════
# STAFF RESPONSE
# ═══════════════════════════════════════════════════════

@app.post("/api/respond/{staff_id}")
async def staff_respond(staff_id: int, data: StaffReply):
    s = db.get_staff_by_id(staff_id)
    if not s:
        raise HTTPException(404, "Personel bulunamadı")
    coordinator = CoordinatorAgent()
    result = await coordinator.handle_response(staff_id, data.request_id, data.response)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


# ═══════════════════════════════════════════════════════
# AGENT ACTIVITY & MEMORY
# ═══════════════════════════════════════════════════════

@app.get("/api/activity")
async def get_activity(limit: int = 50):
    return db.get_recent_activity(limit)


@app.get("/api/memory")
async def get_memory(category: str = None, keyword: str = None):
    return db.recall_memory(category, keyword, limit=20)


# ═══════════════════════════════════════════════════════
# DASHBOARD STATS
# ═══════════════════════════════════════════════════════

@app.get("/api/dashboard")
async def dashboard():
    return db.get_dashboard_stats()


@app.get("/api/requests/{request_id}/assignments")
async def get_assignments(request_id: int):
    return db.get_assignments_for_request(request_id)


@app.post("/api/check-email")
async def check_email_now():
    """Gmail'i şimdi kontrol et ve talepleri işle."""
    from email_checker import check_gmail_for_requests
    results = await check_gmail_for_requests()
    return {"checked": True, "new_requests": len(results), "details": results}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=APP_PORT, reload=True)