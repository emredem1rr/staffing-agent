"""FastAPI backend — Otonom Personel Yönetim Sistemi v2."""

import asyncio
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

import database as db
from config import APP_PORT, EMAIL_CHECK_ENABLED, EMAIL_CHECK_INTERVAL, MESSAGING_MODE
from crew_agents import CoordinatorAgent
from email_checker import check_gmail_for_requests, email_check_loop
from models import ClientRequestCreate, StaffCreate, StaffReply
from reminder import reminder_loop
from webhook import router as webhook_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama başlangıç ve bitiş işlemleri."""
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
        print("  📧 Email kontrol KAPALI (.env → EMAIL_CHECK_ENABLED=true)")
    asyncio.create_task(reminder_loop(60))
    print("  ⏰ Hatırlatma sistemi AKTİF (etkinlikten 2 saat önce)")
    yield


app = FastAPI(
    title="Otonom Personel Yönetim Sistemi v2",
    description="Multi-Agent AI + Hafıza + Puanlama + Takvim",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router)


# ═══════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════

@app.get("/dashboard", response_class=HTMLResponse, tags=["UI"])
async def serve_dashboard():
    """Dashboard HTML sayfasını sun."""
    p = os.path.join(os.path.dirname(__file__), "dashboard.html")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>dashboard.html bulunamadı</h1>", status_code=404)


# ═══════════════════════════════════════════════════════
# STAFF
# ═══════════════════════════════════════════════════════

@app.post("/api/staff", tags=["Personel"])
async def create_staff(data: StaffCreate):
    """Yeni personel kaydı oluştur."""
    try:
        sid = db.create_staff(
            data.name, data.phone, data.roles,
            data.email, data.location, data.hourly_rate,
        )
        return {"id": sid, "message": f"{data.name} kaydedildi"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/staff", tags=["Personel"])
async def list_staff():
    """Tüm personel listesini döndür."""
    return db.get_all_staff()


@app.get("/api/staff/{staff_id}", tags=["Personel"])
async def get_staff(staff_id: int):
    """Tek personel detayını döndür."""
    s = db.get_staff_by_id(staff_id)
    if not s:
        raise HTTPException(status_code=404, detail="Personel bulunamadı")
    return s


@app.get("/api/staff/{staff_id}/schedule", tags=["Personel"])
async def get_schedule(staff_id: int, date_from: str = None, date_to: str = None):
    """Personel takvimini döndür."""
    return db.get_staff_schedule(staff_id, date_from, date_to)


@app.post("/api/staff/{staff_id}/complete-job", tags=["Personel"])
async def complete_job(staff_id: int):
    """Personelin işini tamamlandı olarak işaretle, güvenilirlik puanını artır."""
    db.record_job_completed(staff_id)
    return {"message": "İş tamamlandı olarak işaretlendi"}


@app.post("/api/staff/{staff_id}/no-show", tags=["Personel"])
async def no_show(staff_id: int):
    """Personelin gelmediğini kaydet, güvenilirlik puanını düşür."""
    db.record_no_show(staff_id)
    return {"message": "Gelmedi olarak işaretlendi, puan düşürüldü"}


# ═══════════════════════════════════════════════════════
# REQUESTS
# ═══════════════════════════════════════════════════════

@app.post("/api/requests", tags=["Talepler"])
async def create_request(data: ClientRequestCreate):
    """Yeni müşteri talebi oluştur ve multi-agent pipeline'ı başlat."""
    req_id = db.create_request(
        data.client_name, data.message,
        data.contact_email, data.contact_phone,
        data.priority or "normal",
    )
    coordinator = CoordinatorAgent()
    result = await coordinator.process_request(req_id)
    return {"request_id": req_id, "agent_result": result}


@app.get("/api/requests", tags=["Talepler"])
async def list_requests():
    """Tüm talepleri döndür."""
    return db.get_all_requests()


@app.get("/api/requests/{request_id}", tags=["Talepler"])
async def get_request(request_id: int):
    """Talep detayını atamalar, mesajlar ve aktivite loguyla döndür."""
    r = db.get_request(request_id)
    if not r:
        raise HTTPException(status_code=404, detail="Talep bulunamadı")
    return {
        **r,
        "assignments": db.get_assignments_for_request(request_id),
        "messages": db.get_messages_for_request(request_id),
        "activity": db.get_activity_for_request(request_id),
    }


@app.get("/api/requests/{request_id}/assignments", tags=["Talepler"])
async def get_assignments(request_id: int):
    """Talebe ait atamaları döndür."""
    return db.get_assignments_for_request(request_id)


# ═══════════════════════════════════════════════════════
# STAFF RESPONSE
# ═══════════════════════════════════════════════════════

@app.post("/api/respond/{staff_id}", tags=["Yanıtlar"])
async def staff_respond(staff_id: int, data: StaffReply):
    """Personelin davet yanıtını (kabul/red) işle."""
    s = db.get_staff_by_id(staff_id)
    if not s:
        raise HTTPException(status_code=404, detail="Personel bulunamadı")
    coordinator = CoordinatorAgent()
    result = await coordinator.handle_response(staff_id, data.request_id, data.response)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ═══════════════════════════════════════════════════════
# AGENT ACTIVITY & MEMORY
# ═══════════════════════════════════════════════════════

@app.get("/api/activity", tags=["Agent"])
async def get_activity(limit: int = 50):
    """Son agent aktivitelerini döndür."""
    return db.get_recent_activity(limit)


@app.get("/api/memory", tags=["Agent"])
async def get_memory(category: str = None, keyword: str = None):
    """Agent hafızasını sorgula."""
    return db.recall_memory(category, keyword, limit=20)


# ═══════════════════════════════════════════════════════
# DASHBOARD & EMAIL
# ═══════════════════════════════════════════════════════

@app.get("/api/dashboard", tags=["İstatistik"])
async def dashboard_stats():
    """Dashboard için özet istatistikleri döndür."""
    return db.get_dashboard_stats()


@app.post("/api/check-email", tags=["Email"])
async def check_email_now():
    """Gmail'i anında kontrol et ve yeni talepleri işle."""
    results = await check_gmail_for_requests()
    return {"checked": True, "new_requests": len(results), "details": results}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=APP_PORT, reload=True)
