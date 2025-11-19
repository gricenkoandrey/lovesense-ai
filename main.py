# main.py — LoveSenseAI v6 (aiogram 3 compatible)
# Paste into Replit > main.py, set Secrets: BOT_TOKEN, ADMIN_IDS (comma-separated).
# Optional: OPENAI_API_KEY, PING_URL

import os
import json
import time
import datetime
import asyncio
from aiohttp import web, ClientSession
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Set BOT_TOKEN in Replit Secrets (BOT_TOKEN)")

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
OPENAI_KEY = os.getenv("OPENAI_API_KEY")  # optional for better AI
PING_URL = os.getenv("PING_URL")  # optional keepalive

DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")

TRIAL_LIMIT = 2
PREMIUM_DAYS = 30
PRICE_KZT = 2500

os.makedirs(DATA_DIR, exist_ok=True)

def load_json(path):
    if not os.path.exists(path):
        return {} if "users" in path else []
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return {} if "users" in path else []

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_user(uid: int):
    users = load_json(USERS_FILE)
    u = users.get(str(uid))
    if not u:
        u = {"id": uid, "lang": "ru", "premium_until": 0, "trial_left": TRIAL_LIMIT, "ref_by": None, "ref_count": 0}
        users[str(uid)] = u
        save_json(USERS_FILE, users)
    return u

def save_user(u: dict):
    users = load_json(USERS_FILE)
    users[str(u["id"])] = u
    save_json(USERS_FILE, users)

def add_order(o: dict):
    orders = load_json(ORDERS_FILE)
    orders.append(o)
    save_json(ORDERS_FILE, orders)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

SUPPORTED_LANG = {"ru": "Русский", "kk": "Қазақша", "en": "English"}
CARD = {"price": f"{PRICE_KZT} ₸", "card": "4400 4302 7114 7016", "name": "Andrey.G"}

# Keyboards
def kb_lang():
    kb = InlineKeyboardMarkup(row_width=3)
    for code, name in SUPPORTED_LANG.items():
        kb.add(InlineKeyboardButton(name, callback_data=f"set_lang:{code}"))
    return kb

def kb_main(is_admin=False):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("🧠 Mini Personality", callback_data="mini_personality"),
           InlineKeyboardButton("🔮 AI Advice", callback_data="ai_advice"))
    kb.add(InlineKeyboardButton("❤️ Compatibility", callback_data="compatibility"),
           InlineKeyboardButton("💳 Buy Premium", callback_data="buy_premium"))
    kb.add(InlineKeyboardButton("📊 My Status", callback_data="my_status"))
    if is_admin:
        kb.add(InlineKeyboardButton("🛠 Admin Panel", callback_data="admin_panel"))
    return kb

def kb_buy_flow(user_id: int):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("⚡ Fast Checkout — Instant (demo)", callback_data=f"fast_checkout:{user_id}"))
    kb.add(InlineKeyboardButton("Оплатил вручную (отправить скрин)", callback_data=f"manual_paid:{user_id}"))
    kb.add(InlineKeyboardButton("Отмена", callback_data="cancel"))
    return kb

def kb_admin_panel():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
           InlineKeyboardButton("👥 Пользователи", callback_data="admin_users"))
    kb.add(InlineKeyboardButton("💳 Заказы", callback_data="admin_orders"),
           InlineKeyboardButton("⭐ Управление Premium", callback_data="admin_premium"))
    kb.add(InlineKeyboardButton("🔗 Рефералы", callback_data="admin_refs"),
           InlineKeyboardButton("🎯 Маркет шаблоны", callback_data="admin_marketing"))
    return kb

# Handlers (aiogram 3)
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    args = message.get_args()
    user = get_user(message.from_user.id)
    if args and args.startswith("ref_"):
        try:
            ref = int(args.split("_", 1)[1])
            if ref != message.from_user.id:
                r = get_user(ref)
                r["ref_count"] = r.get("ref_count", 0) + 1
                save_user(r)
                user["ref_by"] = ref
        except:
            pass
    save_user(user)
    await message.answer("Выберите язык / Тілді таңдаңыз / Choose language", reply_markup=kb_lang())

@dp.callback_query(lambda c: c.data and c.data.startswith("set_lang:"))
async def set_lang(cb: types.CallbackQuery):
    code = cb.data.split(":", 1)[1]
    if code not in SUPPORTED_LANG:
        await cb.answer("Unsupported")
        return
    u = get_user(cb.from_user.id)
    u["lang"] = code
    save_user(u)
    await cb.message.answer(f"Язык: {SUPPORTED_LANG[code]}", reply_markup=kb_main(cb.from_user.id in ADMIN_IDS))
    await cb.answer()

async def ai_generate(prompt: str, premium: bool = False):
    # If OPENAI_KEY is set, try real OpenAI call (optional)
    if OPENAI_KEY:
        try:
            import aiohttp
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
            model = "gpt-3.5-turbo" if not premium else "gpt-4o-mini"
            payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 600}
            async with aiohttp.ClientSession() as s:
                async with s.post(url, headers=headers, json=payload, timeout=20) as resp:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
        except Exception as e:
            print("OpenAI call failed:", e)
    # fallback canned responses (free)
    if premium:
        return "💡 [Premium AI] Глубокий анализ (демо): вы внимательны к деталям, рекомендую обсудить ожидания и слушать партнёра."
    return "💡 [Trial AI] Короткий совет (демо): будьте честны и задавайте вопросы, чтобы понять партнёра."

async def handle_ai_request(user_id: int, prompt: str):
    user = get_user(user_id)
    if user.get("premium_until", 0) > time.time():
        return await ai_generate(prompt, premium=True)
    if user.get("trial_left", 0) > 0:
        user["trial_left"] -= 1
        save_user(user)
        return await ai_generate(prompt, premium=False)
    return None

@dp.callback_query(lambda c: c.data == "mini_personality")
async def mini_cb(cb: types.CallbackQuery):
    res = await handle_ai_request(cb.from_user.id, "mini personality analysis")
    if res is None:
        await cb.message.answer(trial_exhausted_text(), reply_markup=kb_buy_flow(cb.from_user.id))
    else:
        await cb.message.answer(res)
    await cb.answer()

@dp.callback_query(lambda c: c.data == "ai_advice")
async def advice_cb(cb: types.CallbackQuery):
    await cb.message.answer("Опиши ситуацию кратко (одно сообщение).")
    await cb.answer()

@dp.message()
async def catch_message(msg: types.Message):
    if msg.text and len(msg.text) < 2000:
        res = await handle_ai_request(msg.from_user.id, msg.text)
        if res is None:
            await msg.answer(trial_exhausted_text(), reply_markup=kb_buy_flow(msg.from_user.id))
        else:
            await msg.answer(res)
    else:
        await msg.answer("Нажмите кнопку меню или отправьте короткое текстовое сообщение.", reply_markup=kb_main(msg.from_user.id in ADMIN_IDS))

def trial_exhausted_text():
    return ("У вас закончились бонусные запросы (2). Хотите продолжить?\n\n"
            f"⚡ Fast Checkout — мгновенный доступ на {PREMIUM_DAYS} дней за {PRICE_KZT} ₸.\n\n"
            "Преимущества Premium:\n• Глубокие AI-ответы\n• Неограниченные запросы\n• Приоритетная поддержка\n\nНажмите кнопку ниже, чтобы купить.")

@dp.callback_query(lambda c: c.data and c.data.startswith("fast_checkout:"))
async def fast_checkout(cb: types.CallbackQuery):
    uid = int(cb.data.split(":", 1)[1])
    order = {"user_id": uid, "timestamp": int(time.time()), "status": "paid_instant", "price": PRICE_KZT}
    add_order(order)
    u = get_user(uid)
    u["premium_until"] = int(time.time()) + PREMIUM_DAYS * 24 * 3600
    if u.get("ref_by"):
        ref = get_user(u["ref_by"])
        ref["premium_until"] = max(ref.get("premium_until", 0), int(time.time())) + 7 * 24 * 3600
        save_user(ref)
    save_user(u)
    await cb.message.answer("🎉 Оплата подтверждена (демо). Вам выдан Premium на 30 дней. Спасибо!")
    for admin in ADMIN_IDS:
        try:
            await bot.send_message(admin, f"[SALE] User {uid} bought Premium (instant demo).")
        except:
            pass
    await cb.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("manual_paid:"))
async def manual_paid(cb: types.CallbackQuery):
    uid = int(cb.data.split(":", 1)[1])
    add_order({"user_id": uid, "timestamp": int(time.time()), "status": "pending_manual"})
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("✔ Grant Premium", callback_data=f"grant:{uid}"),
           InlineKeyboardButton("✖ Reject", callback_data=f"reject:{uid}"))
    for admin in ADMIN_IDS:
        try:
            await bot.send_message(admin, f"Платёж ожидает проверки: user {uid}", reply_markup=kb)
        except:
            pass
    await cb.message.answer("Заявка отправлена администраторам. Они проверят скрин и выдадут Premium.")
    await cb.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("grant:"))
async def grant_cb(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Только админ.")
        return
    uid = int(cb.data.split(":", 1)[1])
    u = get_user(uid)
    u["premium_until"] = int(time.time()) + PREMIUM_DAYS * 24 * 3600
    save_user(u)
    orders = load_json(ORDERS_FILE)
    for o in orders:
        if o.get("user_id") == uid and o.get("status") == "pending_manual":
            o["status"] = "paid_manual"
    save_json(ORDERS_FILE, orders)
    try:
        await bot.send_message(uid, "Вам выдали Premium. Спасибо!")
    except:
        pass
    await cb.message.answer(f"Пользователю {uid} выдан Premium.")
    await cb.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith("reject:"))
async def reject_cb(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Только админ.")
        return
    uid = int(cb.data.split(":", 1)[1])
    orders = load_json(ORDERS_FILE)
    for o in orders:
        if o.get("user_id") == uid and o.get("status") == "pending_manual":
            o["status"] = "rejected"
    save_json(ORDERS_FILE, orders)
    try:
        await bot.send_message(uid, "К сожалению, оплата не подтверждена.")
    except:
        pass
    await cb.message.answer(f"Заявка пользователя {uid} отклонена.")
    await cb.answer()

@dp.callback_query(lambda c: c.data == "buy_premium")
async def buy_cb(cb: types.CallbackQuery):
    text = f"Цена: {CARD['price']}\nКарта: {CARD['card']}\nИмя: {CARD['name']}\n\nВыберите способ оплаты:"
    await cb.message.answer(text, reply_markup=kb_buy_flow(cb.from_user.id))
    await cb.answer()

@dp.callback_query(lambda c: c.data == "admin_panel")
async def admin_panel_cb(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Только админ.")
        return
    await cb.message.answer("Admin Panel:", reply_markup=kb_admin_panel())
    await cb.answer()

@dp.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats_cb(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Только админ.")
        return
    users = load_json(USERS_FILE)
    orders = load_json(ORDERS_FILE)
    total = len(users)
    active = sum(1 for u in users.values() if u.get("premium_until", 0) > time.time())
    sales_day = {}
    sales_month = {}
    for o in orders:
        if o.get("status", "").startswith("paid"):
            day = datetime.datetime.fromtimestamp(o["timestamp"]).strftime("%Y-%m-%d")
            mon = datetime.datetime.fromtimestamp(o["timestamp"]).strftime("%Y-%m")
            sales_day[day] = sales_day.get(day, 0) + 1
            sales_month[mon] = sales_month.get(mon, 0) + 1
    text = f"📊 Статистика\n\n👥 Пользователей: <b>{total}</b>\n⭐ Активных Premium: <b>{active}</b>\n\n💳 Продажи по дням:\n"
    if sales_day:
        for d, c in sorted(sales_day.items(), reverse=True)[:10]:
            text += f"• {d}: <b>{c}</b>\n"
    else:
        text += "Нет подтверждённых продаж.\n"
    text += "\n💳 Продажи по месяцам:\n"
    if sales_month:
        for m, c in sorted(sales_month.items(), reverse=True)[:6]:
            text += f"• {m}: <b>{c}</b>\n"
    else:
        text += "Нет подтверждённых продаж.\n"
    await cb.message.answer(text, parse_mode="HTML")
    await cb.answer()

@dp.callback_query(lambda c: c.data == "admin_users")
async def admin_users_cb(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Только админ.")
        return
    users = load_json(USERS_FILE)
    lines = []
    for uid, u in users.items():
        pu = "Yes" if u.get("premium_until", 0) > time.time() else "No"
        lines.append(f"ID:{uid} | premium:{pu} | trial_left:{u.get('trial_left',0)} | refs:{u.get('ref_count',0)}")
    await cb.message.answer("👥 Пользователи:\n" + "\n".join(lines[:200]))
    await cb.answer()

@dp.callback_query(lambda c: c.data == "admin_orders")
async def admin_orders_cb(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Только админ.")
        return
    orders = load_json(ORDERS_FILE)
    if not orders:
        await cb.message.answer("Нет заказов.")
        await cb.answer()
        return
    text = "💳 Заказы:\n"
    for o in sorted(orders, key=lambda x: x.get("timestamp", 0), reverse=True)[:100]:
        dt = datetime.datetime.fromtimestamp(o.get("timestamp", 0)).strftime("%Y-%m-%d %H:%M")
        text += f"ID:{o.get('user_id')} | {dt} | {o.get('status')}\n"
    await cb.message.answer(text)
    await cb.answer()

@dp.callback_query(lambda c: c.data == "admin_premium")
async def admin_premium_cb(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Только админ")
        return
    await cb.message.answer("Используйте команды: /grant <id> или /revoke <id> (в чат боту).")
    await cb.answer()

@dp.message(Command("grant"))
async def cmd_grant(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    parts = msg.get_args().split()
    if not parts:
        await msg.answer("Usage: /grant <user_id>")
        return
    try:
        uid = int(parts[0])
        u = get_user(uid)
        u["premium_until"] = int(time.time()) + PREMIUM_DAYS * 24 * 3600
        save_user(u)
        await msg.answer(f"Granted premium to {uid}.")
        try:
            await bot.send_message(uid, "Вам выдали Premium администратором.")
        except:
            pass
    except Exception as e:
        await msg.answer("Error: " + str(e))

@dp.message(Command("revoke"))
async def cmd_revoke(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS:
        return
    parts = msg.get_args().split()
    if not parts:
        await msg.answer("Usage: /revoke <user_id>")
        return
    try:
        uid = int(parts[0])
        u = get_user(uid)
        u["premium_until"] = 0
        save_user(u)
        await msg.answer(f"Revoked premium for {uid}.")
        try:
            await bot.send_message(uid, "Ваш Premium отозван администратором.")
        except:
            pass
    except Exception as e:
        await msg.answer("Error: " + str(e))

@dp.callback_query(lambda c: c.data == "admin_refs")
async def admin_refs_cb(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Только админ")
        return
    users = load_json(USERS_FILE)
    refs = sorted(((u.get("ref_count",0), uid) for uid,u in users.items()), reverse=True)[:20]
    text = "🔗 Топ рефералов:\n"
    for cnt, uid in refs:
        text += f"ID:{uid} — {cnt}\n"
    await cb.message.answer(text)
    await cb.answer()

@dp.callback_query(lambda c: c.data == "admin_marketing")
async def admin_marketing_cb(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("Только админ")
        return
    templates = marketing_templates()
    await cb.message.answer("🎯 Маркет шаблоны (копируй в Threads):\n\n" + "\n\n".join(templates))
    await cb.answer()

def marketing_templates():
    return [
        "🔥 Ощути настоящую химию за 2 минуты — LoveSenseAI: попробуй 2 бесплатных анализа сейчас! ➜ t.me/YourBot?start=ref_123",
        "💬 Хочешь, чтобы он(а) написал(а) первым? Получи совет от AI — 2 бесплатных запроса. Premium от 2500 ₸.",
        "⚡ Fast Checkout — мгновенный доступ к PRO-анализам. Премиум за 2500 ₸. Ссылка в профиле.",
        "🎁 Реферальная программа: приведи друга — получи +7 дней Premium при его покупке.",
    ]

# HTTP handlers for Replit + uptime monitoring
async def handle_user_status(request):
    uid = request.match_info.get("id")
    try:
        uid = int(uid)
    except:
        return web.json_response({"error": "invalid id"}, status=400)
    u = get_user(uid)
    return web.json_response({"user_id": uid, "is_premium": u.get("premium_until", 0) > time.time(), "trial_left": u.get("trial_left", 0)})

async def handle_health(request):
    return web.json_response({"ok": True, "time": int(time.time())})

async def start_webapp():
    app = web.Application()
    app.add_routes([web.get("/user_status/{id}", handle_user_status), web.get("/health", handle_health)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=8080)
    await site.start()
    print("HTTP API running on port 8080")

async def keepalive_task():
    if not PING_URL:
        return
    async with ClientSession() as s:
        while True:
            try:
                await s.get(PING_URL, timeout=10)
            except:
                pass
            await asyncio.sleep(300)

async def main():
    await start_webapp()
    if PING_URL:
        asyncio.create_task(keepalive_task())
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped")
