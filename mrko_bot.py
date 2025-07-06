
# Mrko TikTok Bot with Admin-Only Access & Approval Requests

import random
import asyncio
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

BOT_TOKEN = '7661780419:AAG73BWEA8iW1Hc3qnjz8Vk6zG_c1xcs9R0'
ADMIN_ID = 7058689089  # Replace with your actual Telegram user ID

HASHTAGS = ["#viral", "#fyp", "#ea", "#chicks", "#chix", "#eabab", "#masarap", "#babae"]
NSFW_WORDS = ["onlyfans", "18+", "nude", "horny", "hub", "p0rn"]

approved_users = set()
auto_channels = set()
daily_users = set()
user_settings = {}

DROP_CAPTION = (
    "🔥 Another TikTok drop incoming\n"
    "🎯 Matched with your favorite tags\n"
    "🤖 Auto-delivered by Mrko's system\n"
    "⚡ Krueger on top bitches!!!.."
)

def get_settings(user_id):
    if user_id not in user_settings:
        user_settings[user_id] = {"nsfw_mode": "off", "drop_count": 3}
    return user_settings[user_id]

def is_nsfw(text):
    return any(word in text.lower() for word in NSFW_WORDS)

def fetch_tiktoks(limit=3, nsfw_mode="mixed", snipe=False):
    results = []
    attempts = 0
    while len(results) < limit and attempts < 15:
        tag = random.choice(HASHTAGS).replace("#", "")
        url = f"https://api.tikwm.com/feed/search?keyword=%23{tag}&count=10"
        try:
            res = requests.get(url, timeout=5).json()
            if res.get("code") != 0:
                attempts += 1
                continue
            videos = res.get("data", [])
            if snipe:
                videos = sorted(videos, key=lambda v: v.get("play_count", 0), reverse=True)
            for v in videos:
                title = v.get("title", "").lower()
                link = v.get("play")
                if not link or not any(t in title for t in HASHTAGS):
                    continue
                if nsfw_mode == "only" and not is_nsfw(title):
                    continue
                if nsfw_mode == "off" and is_nsfw(title):
                    continue
                if link not in results:
                    results.append(link)
                    if len(results) >= limit:
                        break
        except:
            attempts += 1
            continue
    return results

async def drop_videos(context, chat_id, count=3, nsfw_mode="mixed", snipe=False, silent=False):
    videos = fetch_tiktoks(count, nsfw_mode, snipe)
    if not videos:
        if not silent:
            await context.bot.send_message(chat_id, "❌ No videos found.")
        return
    for vid in videos:
        await context.bot.send_video(chat_id, vid, caption=DROP_CAPTION)
        await asyncio.sleep(1)

# --- ACCESS CHECK ---

async def is_approved(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id == ADMIN_ID or user.id in approved_users:
        return True

    try:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve:{user.id}"),
                InlineKeyboardButton("❌ Decline", callback_data=f"decline:{user.id}")
            ]
        ])
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"👤 <b>{user.full_name}</b> wants access to the bot.\n"
                f"🆔 ID: <code>{user.id}</code>\n"
                f"🔗 <a href='tg://user?id={user.id}'>View Profile</a>"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except:
        pass

    await update.message.reply_text("🔒 This bot is private. Your access request was sent to the admin.")
    return False

def protected_command(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await is_approved(update, context):
            return await func(update, context)
    return wrapper

# --- COMMANDS ---

@protected_command
async def command_mrko(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prefs = get_settings(update.effective_user.id)
    await drop_videos(context, update.effective_chat.id, prefs["drop_count"], prefs["nsfw_mode"])

@protected_command
async def command_dropnsfw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await drop_videos(context, update.effective_chat.id, 3, nsfw_mode="only")

@protected_command
async def command_dropsnipe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await drop_videos(context, update.effective_chat.id, 1, snipe=True)

@protected_command
async def command_dropdaily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    daily_users.add(user_id)
    await update.message.reply_text("📅 Daily TikTok drop enabled.")

@protected_command
async def command_dropch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        raw = context.args[0]
        chat_id = int(raw) if raw.lstrip('-').isdigit() else raw
        auto_channels.add(chat_id)
        await update.message.reply_text(f"✅ Auto-drop started for {chat_id}.")
    except:
        await update.message.reply_text("Usage: /dropch <chat_id or @channel>")

@protected_command
async def command_stopdropch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        raw = context.args[0]
        chat_id = int(raw) if raw.lstrip('-').isdigit() else raw
        auto_channels.discard(chat_id)
        await update.message.reply_text(f"🛑 Auto-drop stopped for {chat_id}.")
    except:
        await update.message.reply_text("Usage: /stopdropch <chat_id or @channel>")

@protected_command
async def command_setnsfw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        mode = context.args[0].lower()
        assert mode in ["off", "only", "mixed"]
        get_settings(update.effective_user.id)["nsfw_mode"] = mode
        await update.message.reply_text(f"NSFW mode set to: {mode}")
    except:
        await update.message.reply_text("Usage: /setnsfw [off|only|mixed]")

@protected_command
async def command_setcount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(context.args[0])
        assert 1 <= count <= 5
        get_settings(update.effective_user.id)["drop_count"] = count
        await update.message.reply_text(f"Drop count set to: {count}")
    except:
        await update.message.reply_text("Usage: /setcount [1-5]")

# --- Callback Handler for Approvals ---

async def handle_access_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, uid = query.data.split(":")
    uid = int(uid)
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("⛔ You can't approve users.")
        return

    if action == "approve":
        approved_users.add(uid)
        await context.bot.send_message(uid, "✅ You have been approved. You can now use the bot.")
        await query.edit_message_text("✅ User has been approved.")
    elif action == "decline":
        await context.bot.send_message(uid, "❌ Your request was declined. You cannot use this bot.")
        await query.edit_message_text("❌ User has been declined.")

# --- Scheduler ---

async def run_auto_drops(bot):
    for chat_id in auto_channels:
        try:
            await drop_videos(bot, chat_id, 3, silent=True)
        except:
            continue
    for user_id in daily_users:
        try:
            await drop_videos(bot, user_id, 1, silent=True)
        except:
            continue

# --- Main ---

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("mrko", command_mrko))
    app.add_handler(CommandHandler("dropnsfw", command_dropnsfw))
    app.add_handler(CommandHandler("dropsnipe", command_dropsnipe))
    app.add_handler(CommandHandler("dropdaily", command_dropdaily))
    app.add_handler(CommandHandler("dropch", command_dropch))
    app.add_handler(CommandHandler("stopdropch", command_stopdropch))
    app.add_handler(CommandHandler("setnsfw", command_setnsfw))
    app.add_handler(CommandHandler("setcount", command_setcount))
    app.add_handler(CallbackQueryHandler(handle_access_callback, pattern=r'^(approve|decline):'))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: run_auto_drops(app.bot), "interval", hours=5)
    scheduler.start()

    print("[Mrko Bot] Running with admin-only access...")
    await app.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
