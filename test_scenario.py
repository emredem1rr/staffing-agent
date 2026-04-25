"""Tam senaryo testi — v2 multi-agent pipeline."""

import asyncio
import httpx

BASE = "http://localhost:8000"


async def run():
    async with httpx.AsyncClient(timeout=120.0) as client:
        print("\n" + "═" * 60)
        print("  🧪 MULTI-AGENT SENARYO TESTİ v2")
        print("═" * 60)

        # 1. Talep oluştur
        print("\n📨 Müşteri talebi gönderiliyor...")
        resp = await client.post(f"{BASE}/api/requests", json={
            "client_name": "Sheraton İstanbul Maslak",
            "message": (
                "Merhaba, 25 Ocak Cumartesi saat 10:00-23:00 arası "
                "düğün organizasyonu için 5 garson, 3 komi ve 1 aşçıya ihtiyacımız var. "
                "Konum: Sheraton İstanbul Maslak, Büyükdere Cad. No:233."
            ),
            "contact_email": "events@sheraton-maslak.com",
            "priority": "high",
        })

        data = resp.json()
        rid = data["request_id"]
        result = data.get("agent_result", {})

        print(f"✅ Talep #{rid} oluşturuldu")
        print(f"⏱  Pipeline süresi: {result.get('pipeline_duration', '?')}s")
        if "steps" in result:
            for s in result["steps"]:
                print(f"   {s['agent']}: {s['duration']}s")
        if "matches" in result:
            for role, info in result["matches"].items():
                print(f"   {role}: {info['needed']} gerekli → {info['invited']} davet")

        # 2. Agent aktivite logunu göster
        print("\n🧠 Agent düşünce süreci:")
        activity = await client.get(f"{BASE}/api/activity?limit=15")
        for a in reversed(activity.json()):
            icon = {"thinking": "💭", "delegate": "📋", "matched": "🔗",
                    "message_sent": "📱", "conflict": "⚠️",
                    "step_complete": "✓", "pipeline_complete": "🏁",
                    "analysis_done": "🔍"}.get(a["action"], "•")
            print(f"   {icon} [{a['agent_role']}] {a['detail'][:80]}")

        # 3. Yanıtlar simüle et
        print("\n📱 Personel yanıtları simüle ediliyor...")
        detail = await client.get(f"{BASE}/api/requests/{rid}")
        assignments = detail.json().get("assignments", [])

        for i, a in enumerate(assignments):
            will_accept = (i % 3 != 2)
            response = "accept" if will_accept else "decline"
            emoji = "✅" if will_accept else "❌"
            print(f"   {emoji} {a['staff_name']} ({a['role']}): {'KABUL' if will_accept else 'RED'}")

            r2 = await client.post(f"{BASE}/api/respond/{a['staff_id']}",
                json={"request_id": rid, "response": response})
            if r2.status_code == 200:
                print(f"      → {r2.json()['message']}")
            await asyncio.sleep(0.3)

        # 4. Final
        print("\n" + "═" * 60)
        final = await client.get(f"{BASE}/api/requests/{rid}")
        fd = final.json()
        print(f"  📊 Durum: {fd['status']}")
        for a in fd.get("assignments", []):
            icon = {"accepted":"✅","declined":"❌","invited":"⏳","quota_full":"🔴"}.get(a["status"],"?")
            score = f" (Güvenilirlik:{a.get('reliability_score','?')})" if a.get('reliability_score') else ""
            print(f"     {icon} {a['staff_name']} — {a['role']} — {a['status']}{score}")

        # 5. Hafıza
        print("\n🧠 Agent hafızası:")
        mem = await client.get(f"{BASE}/api/memory")
        for m in mem.json()[:5]:
            print(f"   [{m['category']}] {m['content'][:70]}...")

        print("\n" + "═" * 60)
        print("  ✅ Test tamamlandı!")
        print("  📊 Dashboard: http://localhost:8000/dashboard")
        print("═" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(run())