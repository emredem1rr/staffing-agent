"""
Gelişmiş veri modelleri — v2

Yeni özellikler:
- Personel performans puanlama
- Takvim ve müsaitlik
- Agent hafıza modelleri
- Multi-agent görev modelleri
"""

from __future__ import annotations
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


# ── Enum'lar ──────────────────────────────────────────

class RequestStatus(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    MATCHING = "matching"
    MESSAGING = "messaging"
    PARTIALLY_FILLED = "partially_filled"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"
    FAILED = "failed"


class StaffStatus(str, Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


class AssignmentStatus(str, Enum):
    INVITED = "invited"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    QUOTA_FULL = "quota_full"
    NO_RESPONSE = "no_response"


class AgentRole(str, Enum):
    """CrewAI agent rolleri."""
    COORDINATOR = "coordinator"       # Ana koordinatör — iş dağıtır
    ANALYZER = "analyzer"             # Talep analizi uzmanı
    MATCHER = "matcher"               # Personel eşleştirme uzmanı
    COMMUNICATOR = "communicator"     # İletişim uzmanı — mesaj yazar
    SCHEDULER = "scheduler"           # Takvim ve çakışma yönetimi


# ── API Request/Response ──────────────────────────────

class StaffCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    roles: list[str]
    location: Optional[str] = None
    hourly_rate: Optional[float] = None


class ClientRequestCreate(BaseModel):
    client_name: str
    message: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    priority: Optional[str] = "normal"  # low, normal, high, urgent


class StaffReply(BaseModel):
    request_id: int
    response: str  # "accept" / "decline"


# ── Performans ve Puanlama ────────────────────────────

class StaffScore(BaseModel):
    """Personel performans puanlama modeli."""
    staff_id: int
    reliability_score: float = 5.0     # Güvenilirlik (zamanında gelme, iptal oranı)
    quality_score: float = 5.0         # İş kalitesi (müşteri geri bildirimi)
    response_speed: float = 5.0        # Yanıt hızı (davet-kabul süresi)
    total_jobs: int = 0
    completed_jobs: int = 0
    cancelled_jobs: int = 0
    no_show_count: int = 0
    avg_response_minutes: float = 0.0  # Ortalama yanıt süresi (dakika)

    @property
    def overall_score(self) -> float:
        """Ağırlıklı genel puan (0-10)."""
        return round(
            self.reliability_score * 0.4 +
            self.quality_score * 0.35 +
            self.response_speed * 0.25,
            2
        )

    @property
    def cancel_rate(self) -> float:
        if self.total_jobs == 0:
            return 0.0
        return round(self.cancelled_jobs / self.total_jobs * 100, 1)


# ── Takvim ve Müsaitlik ──────────────────────────────

class ScheduleEntry(BaseModel):
    """Personel takvim kaydı."""
    staff_id: int
    request_id: int
    date: str           # YYYY-MM-DD
    start_time: str     # HH:MM
    end_time: str       # HH:MM
    location: Optional[str] = None
    client_name: Optional[str] = None
    role: str
    status: str = "confirmed"  # confirmed, tentative, cancelled


class ConflictCheck(BaseModel):
    """Çakışma kontrol sonucu."""
    has_conflict: bool
    conflicting_entry: Optional[ScheduleEntry] = None
    message: str = ""


# ── Agent Hafıza Modelleri ────────────────────────────

class MemoryEntry(BaseModel):
    """Agent'ın uzun süreli hafızasına kaydedilen bilgi."""
    key: str                           # Benzersiz anahtar
    category: str                      # staff_preference, client_pattern, lesson_learned
    content: str                       # Hatırlanan bilgi
    relevance_score: float = 1.0       # Ne kadar güncel/önemli (zamanla azalır)
    created_at: str = ""
    last_accessed: str = ""
    access_count: int = 0

    def __init__(self, **data):
        if not data.get("created_at"):
            data["created_at"] = datetime.now().isoformat()
        if not data.get("last_accessed"):
            data["last_accessed"] = data.get("created_at", datetime.now().isoformat())
        super().__init__(**data)


class AgentThought(BaseModel):
    """Agent'ın düşünce sürecindeki bir adım (chain-of-thought)."""
    agent_role: str          # Hangi agent düşünüyor
    thought_type: str        # observation, reasoning, decision, action, reflection
    content: str
    confidence: float = 0.8  # 0-1 arası güven seviyesi
    timestamp: str = ""
    data: Optional[dict] = None

    def __init__(self, **data):
        if not data.get("timestamp"):
            data["timestamp"] = datetime.now().isoformat()
        super().__init__(**data)


# ── CrewAI Görev Modelleri ────────────────────────────

class CrewTaskResult(BaseModel):
    """Bir CrewAI görevinin sonucu."""
    task_name: str
    agent_role: str
    status: str          # success, partial, failed
    output: dict
    thoughts: list[AgentThought] = []
    duration_seconds: float = 0.0


class PipelineResult(BaseModel):
    """Tüm multi-agent pipeline sonucu."""
    request_id: int
    status: str
    tasks: list[CrewTaskResult] = []
    total_duration: float = 0.0
    summary: str = ""


# ── Dashboard Modelleri ───────────────────────────────

class DashboardStats(BaseModel):
    total_requests: int = 0
    active_requests: int = 0
    fulfilled_requests: int = 0
    failed_requests: int = 0
    total_staff: int = 0
    available_staff: int = 0
    avg_fill_rate: float = 0.0        # Ortalama talep karşılama oranı
    avg_response_time: float = 0.0     # Ortalama personel yanıt süresi (dakika)
    top_roles: list[dict] = []         # En çok talep edilen pozisyonlar
    daily_requests: list[dict] = []    # Son 7 gün talep grafiği
    staff_performance: list[dict] = [] # Personel performans sıralaması


class AgentActivityLog(BaseModel):
    """Dashboard'da gösterilecek agent aktivite kaydı."""
    id: int = 0
    request_id: int
    agent_role: str
    action: str
    detail: str
    timestamp: str = ""

    def __init__(self, **data):
        if not data.get("timestamp"):
            data["timestamp"] = datetime.now().isoformat()
        super().__init__(**data)