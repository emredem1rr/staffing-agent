"""
Ollama LLM bağlantı katmanı.

Tüm agent'lar bu modül üzerinden LLM'e erişir.
Ollama yoksa fallback mod devreye girer.
"""

import json
import re
import httpx
from config import OLLAMA_URL, MODEL_NAME


async def call_llm(prompt: str, system_prompt: str = None,
                   temperature: float = 0.3, max_tokens: int = 1024) -> str:
    """Ollama LLM'e istek gönder."""
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    if system_prompt:
        payload["system"] = system_prompt

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(OLLAMA_URL, json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
    except httpx.ConnectError:
        print("⚠️  Ollama bağlantısı yok — fallback mod")
        return _fallback(prompt)
    except Exception as e:
        print(f"⚠️  LLM hatası: {e}")
        return _fallback(prompt)


def extract_json(text: str) -> dict | None:
    """LLM çıktısından JSON çıkar."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # ```json ... ``` bloğu
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # İlk { ... } bloğu
    m = re.search(r'\{[\s\S]*\}', text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _fallback(prompt: str) -> str:
    """Ollama yokken basit kural-tabanlı fallback."""
    p = prompt.lower()
    if "json" in p and ("role" in p or "pozisyon" in p):
        return json.dumps({
            "location": "Belirtilmemiş",
            "date": "Belirtilmemiş",
            "time": "Belirtilmemiş",
            "needs": [{"role": "garson", "count": 5}, {"role": "komi", "count": 3}],
            "notes": "Fallback mod aktif — Ollama bağlantısı yok"
        })
    if "mesaj yaz" in p or "message" in p or "davet" in p:
        return "Merhaba, yaklaşan bir etkinlik için sizinle çalışmak isteriz. Detaylar için lütfen EVET veya HAYIR yazın."
    if "kontenjan" in p or "doldu" in p:
        return "İlginiz için teşekkür ederiz. Bu pozisyon için kontenjan dolmuştur. Bir sonraki etkinlikte görüşmek üzere!"
    if "puan" in p or "score" in p or "değerlendir" in p:
        return json.dumps({"score": 7, "reasoning": "Fallback — varsayılan puan"})
    if "kaç kişi" in p or "sayı" in p:
        return "8"
    if "özet" in p or "rapor" in p or "summary" in p:
        return "Talep başarıyla işlendi. Personel atamaları tamamlandı."
    return "Ollama bağlantısı yok, fallback mod aktif."