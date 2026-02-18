import os
import json
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    ConversationHandler, MessageHandler, filters, CallbackQueryHandler
)

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

DB_FILE = "db.json"

AMOUNT, TIME_SENT, AVAILED = range(3)

POINTS_TABLE = {
    "per game special": 1,
    "bo3 special": 1,
    "bo5 special": 2,
    "bo7 special": 3,
    "per hour special": 1,
    "2 hours special": 2,
    "3 hours special": 3,
    "5 hours special": 4,

    "per game normal": 1,
    "bo3 normal": 2,
    "bo5 normal": 3,
    "bo7 normal": 5,
    "per hour normal": 2,
    "2 hours normal": 3,
    "3 hours normal": 4,
    "5 hours normal": 6,

    "6 hours": 6,
    "12 hours": 7,
    "18 hours": 8,
    "24 hours": 10,
    "1 month": 130,
}


def load_db():
    try:
        with open(DB_FILE) as f:
            return json.load(f)
    except:
        return {"points": {}, "pending": {}}


def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/submit — submit payment\n"
        "/points — check points"
    )


async def points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    uid = str(update.effective_user.id)
    pts = db["points"].get(uid, 0)
    await update.message.reply_text(f"You have {pts} points ⭐")


async def submit_start(update, context):
    await update.message.reply_text("Enter amount:")
    return AMOUNT


async def submit_amount(update, context):
    context.user_data["amount"] = update.message.text
    await update.message.reply_text("Enter time sent:")
    return TIME_SENT


async def submit_time(update, context):
    context.user_data["time"] = update.message.text
    await update.message.reply_text("What availed? (ex: Bo5 normal)")
    return AVAILED


async def submit_availed(update, context):
    availed = update.message.text.lower()
    pts = POINTS_TABLE.get(availed)

    if not pts:
        await update.message.reply_text("Not recognized — try again.")
        return AVAILED

    rid = str(uuid.uuid4())[:8]

    db = load_db()
    db["pending"][rid] = {
        "user": update.effective_user.id,
        "username": update.effective_user.username,
        "amount": context.user_data["amount"],
        "time": context.user_data["time"],
        "availed": availed,
        "points": pts
    }
    save_db(db)

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirm", callback_data=f"ok_{rid}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"no_{rid}")
    ]])

    await context.bot.send_message(
        ADMIN_ID,
        f"NEW PAYMENT\n\n"
        f"User: @{update.effective_user.username}\n"
        f"Availed: {availed}\n"
        f"Amount: {context.user_data['amount']}\n"
        f"Time: {context.user_data['time']}\n"
        f"Points: {pts}",
        reply_markup=kb
    )

    await update.message.reply_text("Submitted — pending admin approval.")
    return ConversationHandler.END


async def handle_confirm(update, context):
    q = update.callback_query
    await q.answer()

    action, rid = q.data.split("_")
    db = load_db()
    rec = db["pending"].get(rid)
    if not rec:
        return

    uid = str(rec["user"])

    if action == "ok":
        db["points"][uid] = db["points"].get(uid, 0) + rec["points"]
        await context.bot.send_message(rec["user"], f"Approved ✅ +{rec['points']} pts")
        msg = "Confirmed"
    else:
        await context.bot.send_message(rec["user"], "Rejected ❌")
        msg = "Rejected"

    del db["pending"][rid]
    save_db(db)
    await q.edit_message_text(msg)


app = Application.builder().token(TOKEN).build()

conv = ConversationHandler(
    entry_points=[CommandHandler("submit", submit_start)],
    states={
        AMOUNT: [MessageHandler(filters.TEXT, submit_amount)],
        TIME_SENT: [MessageHandler(filters.TEXT, submit_time)],
        AVAILED: [MessageHandler(filters.TEXT, submit_availed)],
    },
    fallbacks=[]
)

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("points", points))
app.add_handler(conv)
app.add_handler(CallbackQueryHandler(handle_confirm, pattern="^(ok|no)_"))

app.run_polling()
