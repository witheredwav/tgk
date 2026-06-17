import json
import os
import random
from datetime import datetime
from threading import Lock

from config import DB_FILE

_lock = Lock()  # защита от одновременной записи при polling

# ─── БАЗОВЫЕ ОПЕРАЦИИ ──────────────────────────────────────────────────────────

def _default_db() -> dict:
    return {
        "codes": {},          # {"00001": {"type": ..., "content": ..., "caption": ...}}
        "stats": {             # {"total": {"event": [user_ids]}, "daily": {"YYYY-MM-DD": {...}}}
            "total": {},
            "daily": {}
        },
        "users": {},           # {"123456": {"joined": "...", "referrer": "789", "referrals": ["111","222"]}}
        "broadcast_log": []     # история рассылок
    }

def load_db() -> dict:
    if not os.path.exists(DB_FILE):
        return _default_db()
    with open(DB_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # на случай старой структуры без новых ключей
    defaults = _default_db()
    for key, val in defaults.items():
        data.setdefault(key, val)
    return data

def save_db(db: dict):
    with _lock:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)

# ─── СТАТИСТИКА (уникальные пользователи на событие) ─────────────────────────

def track(event: str, user_id: int):
    db = load_db()
    today = datetime.now().strftime("%Y-%m-%d")
    uid = str(user_id)

    total_users = db["stats"].setdefault("total", {}).setdefault(event, [])
    if uid not in total_users:
        total_users.append(uid)

    day_users = db["stats"].setdefault("daily", {}).setdefault(today, {}).setdefault(event, [])
    if uid not in day_users:
        day_users.append(uid)

    save_db(db)

def get_stats_text() -> str:
    db = load_db()
    today = datetime.now().strftime("%Y-%m-%d")
    total = db["stats"].get("total", {})
    daily = db["stats"].get("daily", {}).get(today, {})

    events = {
        "start": "🚀 /start",
        "check_sub": "✅ Проверка подписки",
        "works": "🎧 Примеры работ",
        "order": "💬 Заказать сведение",
        "enter_key": "🔑 Ввод ключа",
        "referral_join": "🤝 Переходы по реф. ссылке",
    }

    total_users_count = len(db.get("users", {}))

    lines = [f"📊 *Статистика*\n", f"👥 Всего пользователей бота: *{total_users_count}*\n", "*За сегодня:*"]
    for e, label in events.items():
        lines.append(f"  {label}: {len(daily.get(e, []))} чел.")
    lines.append("\n*Всего за всё время:*")
    for e, label in events.items():
        lines.append(f"  {label}: {len(total.get(e, []))} чел.")
    return "\n".join(lines)

# ─── КОДЫ ──────────────────────────────────────────────────────────────────────

def next_free_code() -> str | None:
    db = load_db()
    existing = set(db["codes"].keys())
    all_codes = [f"{i:05d}" for i in range(1, 100000)]
    free = [c for c in all_codes if c not in existing]
    if not free:
        return None
    return random.choice(free)

def get_code(code: str) -> dict | None:
    db = load_db()
    return db["codes"].get(code)

def save_code(code: str, entry: dict):
    db = load_db()
    db["codes"][code] = entry
    save_db(db)

def delete_code(code: str) -> bool:
    db = load_db()
    if code in db["codes"]:
        del db["codes"][code]
        save_db(db)
        return True
    return False

def list_codes() -> dict:
    db = load_db()
    return db["codes"]

# ─── ПОЛЬЗОВАТЕЛИ И РЕФЕРАЛЬНАЯ СИСТЕМА ────────────────────────────────────────

def register_user(user_id: int, referrer_id: int | None = None) -> bool:
    """Регистрирует пользователя. Возвращает True если пользователь новый."""
    db = load_db()
    uid = str(user_id)
    is_new = uid not in db["users"]

    if is_new:
        db["users"][uid] = {
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "referrer": str(referrer_id) if referrer_id and referrer_id != user_id else None,
            "referrals": []
        }
        # засчитываем приглашение рефереру
        if referrer_id and referrer_id != user_id:
            ref_uid = str(referrer_id)
            if ref_uid in db["users"]:
                if uid not in db["users"][ref_uid]["referrals"]:
                    db["users"][ref_uid]["referrals"].append(uid)
        save_db(db)

    return is_new

def get_user(user_id: int) -> dict | None:
    db = load_db()
    return db["users"].get(str(user_id))

def get_referral_count(user_id: int) -> int:
    user = get_user(user_id)
    if not user:
        return 0
    return len(user.get("referrals", []))

def get_all_user_ids() -> list[str]:
    db = load_db()
    return list(db["users"].keys())

def get_referral_leaderboard(limit: int = 10) -> list[tuple[str, int]]:
    db = load_db()
    rows = [(uid, len(data.get("referrals", []))) for uid, data in db["users"].items()]
    rows = [r for r in rows if r[1] > 0]
    rows.sort(key=lambda x: x[1], reverse=True)
    return rows[:limit]

# ─── ЛОГ РАССЫЛОК ──────────────────────────────────────────────────────────────

def log_broadcast(sent: int, failed: int):
    db = load_db()
    db["broadcast_log"].append({
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sent": sent,
        "failed": failed
    })
    save_db(db)
