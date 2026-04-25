"""Örnek veri yükleme — v3 (konum + gerçek numaralar)."""
import database as db
import random


def seed():
    db.init_db()

    staff_data = [
        {"name": "Emre Demir",          "phone": "+905551000001", "roles": ["garson","komi"],        "email": "emre.demir@example.com",     "location": "Maslak"},
        {"name": "Muhammet Ali Gödek",   "phone": "+905551000002", "roles": ["barmen"],               "email": "mali.godek@example.com",     "location": "Bomonti"},
        {"name": "Mehmet Kaya",          "phone": "+905551000003", "roles": ["garson","barmen"],      "email": "mehmet@test.com",      "location": "Levent"},
        {"name": "Ayşe Çelik",          "phone": "+905551000004", "roles": ["garson","host/hostes"],  "email": "ayse@test.com",        "location": "Şişli"},
        {"name": "Burak Özkan",          "phone": "+905551000005", "roles": ["garson"],               "email": "burak@test.com",       "location": "Kadıköy"},
        {"name": "Zeynep Arslan",        "phone": "+905551000006", "roles": ["garson","komi"],        "email": "zeynep@test.com",      "location": "Beşiktaş"},
        {"name": "Can Polat",            "phone": "+905551000007", "roles": ["garson"],               "email": "can@test.com",         "location": "Üsküdar"},
        {"name": "Selin Yıldız",         "phone": "+905551000008", "roles": ["garson","host/hostes"], "email": "selin@test.com",       "location": "Taksim"},
        {"name": "Emre Şahin",           "phone": "+905551000009", "roles": ["komi","bulaşıkçı"],    "email": "emre@test.com",        "location": "Maslak"},
        {"name": "Fatma Güneş",          "phone": "+905551000010", "roles": ["komi"],                 "email": "fatma@test.com",       "location": "Sarıyer"},
        {"name": "Ali Koç",              "phone": "+905551000011", "roles": ["komi","garson"],         "email": "ali@test.com",         "location": "Beyoğlu"},
        {"name": "Derya Aksoy",          "phone": "+905551000012", "roles": ["komi"],                 "email": "derya@test.com",       "location": "Ataşehir"},
        {"name": "Murat Çetin",          "phone": "+905551000013", "roles": ["komi","aşçı"],          "email": "murat@test.com",       "location": "Bomonti"},
        {"name": "Hasan Usta",           "phone": "+905551000014", "roles": ["aşçı"],                 "email": "hasan@test.com",       "location": "Levent"},
        {"name": "Gülsüm Hanım",        "phone": "+905551000015", "roles": ["aşçı","komi"],          "email": "gulsum@test.com",      "location": "Şişli"},
        {"name": "İbrahim Chef",         "phone": "+905551000016", "roles": ["aşçı"],                 "email": "ibrahim@test.com",     "location": "Kadıköy"},
        {"name": "Hatice Yılmaz",        "phone": "+905551000017", "roles": ["temizlikçi"],            "email": "hatice@test.com",      "location": "Beşiktaş"},
        {"name": "Osman Kaplan",         "phone": "+905551000018", "roles": ["temizlikçi","bulaşıkçı"],"email": "osman@test.com",      "location": "Taksim"},
        {"name": "Deniz Aksu",           "phone": "+905551000019", "roles": ["barmen"],                "email": "deniz@test.com",       "location": "Bomonti"},
        {"name": "Cem Yılmaz",           "phone": "+905551000020", "roles": ["barmen","garson"],       "email": "cem@test.com",         "location": "Maslak"},
        {"name": "Berna Koç",            "phone": "+905551000021", "roles": ["garson","komi"],         "email": "berna@test.com",       "location": "Beyoğlu"},
        {"name": "Tolga Demir",          "phone": "+905551000022", "roles": ["güvenlik","vale"],       "email": "tolga@test.com",       "location": "Levent"},
        {"name": "Nazlı Çelik",          "phone": "+905551000023", "roles": ["host/hostes"],           "email": "nazli@test.com",       "location": "Şişli"},
        {"name": "Serkan Aydın",         "phone": "+905551000024", "roles": ["garson","barmen"],       "email": "serkan@test.com",      "location": "Kadıköy"},
        {"name": "Pınar Şen",            "phone": "+905551000025", "roles": ["komi","temizlikçi"],     "email": "pinar@test.com",       "location": "Ataşehir"},
    ]

    print("📋 Personel yükleniyor...")
    for s in staff_data:
        try:
            sid = db.create_staff(
                s["name"], s["phone"], s["roles"],
                s["email"], s.get("location"))

            loc = s.get("location", "?")
            print(f"  ✅ {s['name']} (ID:{sid}) — {', '.join(s['roles'])} — {loc}")
        except Exception as e:
            print(f"  ⚠️  {s['name']}: {e}")

    db.store_memory("client_sheraton", "client_pattern",
        "Sheraton İstanbul genellikle 5-10 garson, 3-5 komi talep ediyor. Maslak lokasyonu.", 1.0)
    db.store_memory("client_hilton", "client_pattern",
        "Hilton Bomonti büyük etkinliklerde 15+ garson isteyebilir.", 0.9)
    db.store_memory("lesson_overbooking", "lesson_learned",
        "İhtiyacın 1.5 katı davet göndermek optimal.", 1.0)

    print(f"\n✅ {len(staff_data)} personel + konum + performans verileri yüklendi!")
    print("🧠 3 hafıza kaydı eklendi")
    print("\n▶  python main.py")


if __name__ == "__main__":
    seed()