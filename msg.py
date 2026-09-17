#!/usr/bin/env python3
"""
Challan Message Generator Bot v6
WhatsApp deep link + tappable message body.
"""

import random
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

BOT_TOKEN = "8309635118:AAETr3ceXUuQTTmsOhl2UOraZEtEL-m8dEE"
ALLOWED_USERS = []

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

user_batches = {}
copy_store = {}


def is_allowed(user_id):
    return not ALLOWED_USERS or user_id in ALLOWED_USERS


def generate_challan_id():
    prefix = random.choice(["77", "88"])
    suffix = "".join(random.choices("0123456789", k=8))
    return prefix + suffix


def build_message(vehicle, challan_id, phone):
    return (
        "📢 *mPARIVAHAN — CHALLAN ALERT* ⚠️\n\n"
        "Dear Owner,\n\n"
        f"A traffic challan has been issued against your vehicle *{vehicle}*.\n\n"
        "🚦 Red Light Jump\n"
        f"🎫 Challan: {challan_id}\n"
        "💰 Fine: *₹2,250*\n"
        "📸 Camera proof attached\n\n"
        "⚡ Pay within 24 hrs to avoid court summons.\n\n"
        "Open the official app below:\n\n"
        "— Ministry of Road Transport & Highways"
    )


def parse_line(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    for sep in [",", "\t", ";"]:
        if sep in line:
            parts = [p.strip() for p in line.split(sep)]
            break
    else:
        parts = line.split()

    if len(parts) < 2:
        return None

    vehicle = parts[0].upper().replace(" ", "")
    phone = parts[1].replace(" ", "").replace("-", "").replace("+", "")

    if phone.startswith("91") and len(phone) == 12:
        phone = phone[2:]
    if phone.startswith("0") and len(phone) == 11:
        phone = phone[1:]

    if len(vehicle) < 6 or not vehicle[:2].isalpha():
        return None
    if not phone.isdigit() or len(phone) < 10:
        return None

    return vehicle, phone


def process_lines(lines):
    valid = []
    invalid = []

    for i, line in enumerate(lines, start=1):
        parsed = parse_line(line)
        if parsed:
            vehicle, phone = parsed
            challan_id = generate_challan_id()
            valid.append((vehicle, phone, challan_id))
        elif line.strip():
            invalid.append((i, line.strip()[:60]))

    return valid, invalid


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("⛔ Not authorized.")
        return

    text = (
        "🎫  *Challan Message Generator v6*\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "Paste list or upload `.csv`/`.txt`:\n"
        "```\nGJ01KR3172,7874777720\n```\n\n"
        "Each entry → WhatsApp link + tappable body.\n\n"
        "*Commands*\n"
        "/clear /stats /export /send10 /sendall"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def clear_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return
    user_batches.pop(update.effective_user.id, None)
    copy_store.pop(update.effective_user.id, None)
    await update.message.reply_text("✅ Cleared.")


async def stats_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return
    batch = user_batches.get(update.effective_user.id, [])
    await update.message.reply_text(f"📊 *{len(batch)}* entries", parse_mode="Markdown")


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    user_id = update.effective_user.id
    lines = update.message.text.strip().split("\n")
    valid, invalid = process_lines(lines)

    if not valid:
        await update.message.reply_text(
            "❌ No valid entries.\nFormat: `VEHICLE,PHONE`",
            parse_mode="Markdown"
        )
        return

    if user_id not in user_batches:
        user_batches[user_id] = []
    user_batches[user_id].extend(valid)

    total = len(user_batches[user_id])
    summary = f"✅ Parsed *{len(valid)}* | Total: *{total}*"
    if invalid:
        summary += f" | Skipped {len(invalid)}"
    await update.message.reply_text(summary, parse_mode="Markdown")

    if total > 30:
        await update.message.reply_text(
            f"📦 *{total}* entries. Choose:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤  Send 10", callback_data="send10")],
                [InlineKeyboardButton("📄  Export", callback_data="export")],
            ])
        )
    else:
        await send_batch(update, user_id, valid)


async def handle_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    doc = update.message.document
    filename = doc.file_name or ""

    if not (filename.lower().endswith(".csv") or filename.lower().endswith(".txt")):
        await update.message.reply_text("❌ Only `.csv` or `.txt`.", parse_mode="Markdown")
        return

    if doc.file_size and doc.file_size > 5 * 1024 * 1024:
        await update.message.reply_text("❌ File too large. Max 5 MB.")
        return

    await update.message.reply_text("⏳ Downloading...")

    try:
        file = await ctx.bot.get_file(doc.file_id)
        content = await file.download_as_bytearray()
        text = content.decode("utf-8", errors="ignore")
        lines = text.strip().split("\n")
        valid, invalid = process_lines(lines)

        if not valid:
            await update.message.reply_text("❌ No valid entries.")
            return

        user_id = update.effective_user.id
        if user_id not in user_batches:
            user_batches[user_id] = []
        user_batches[user_id].extend(valid)

        total = len(user_batches[user_id])
        summary = (
            f"📄 *{filename}*\n"
            f"✅ Valid: *{len(valid)}* | Skipped: *{len(invalid)}*\n"
            f"📊 Batch: *{total}*"
        )
        await update.message.reply_text(summary, parse_mode="Markdown")

        await update.message.reply_text(
            "Choose:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤  Send 10", callback_data="send10")],
                [InlineKeyboardButton("📄  Export", callback_data="export")],
                [InlineKeyboardButton("📨  Send ALL", callback_data="sendall")],
            ])
        )

    except Exception as e:
        logger.error(f"File error: {e}")
        await update.message.reply_text(f"❌ {str(e)[:200]}")


async def send_batch(update: Update, user_id, batch):
    """Send WhatsApp link + tappable message body."""
    for vehicle, phone, challan_id in batch:
        body = build_message(vehicle, challan_id, phone)

        # Build WhatsApp deep link
        wa_number = phone
        if not wa_number.startswith("91") and len(wa_number) == 10:
            wa_number = "91" + wa_number
        wa_link = f"https://wa.me/{wa_number}"

        msg1 = f"📱 *Open WhatsApp:*\n\n{wa_link}"
        msg2 = f"📝 *Message to copy:*\n\n```\n{body}\n```"

        try:
            await update.message.reply_text(
                msg1,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            await asyncio.sleep(0.15)
            await update.message.reply_text(msg2, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Send error: {e}")

        await asyncio.sleep(0.4)


async def export_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    batch = user_batches.get(update.effective_user.id, [])
    if not batch:
        await update.message.reply_text("❌ Batch empty.")
        return

    lines = ["phone\tvehicle\tchallan\twa_link\tmessage"]
    for vehicle, phone, challan_id in batch:
        body = build_message(vehicle, challan_id, phone)
        escaped = body.replace("\n", "\\n").replace("\t", " ")
        wa_number = phone if phone.startswith("91") else "91" + phone
        wa_link = f"https://wa.me/{wa_number}"
        lines.append(f"{phone}\t{vehicle}\t{challan_id}\t{wa_link}\t{escaped}")

    content = "\n".join(lines)

    await update.message.reply_document(
        document=content.encode("utf-8"),
        filename=f"challan_{len(batch)}.txt",
        caption=f"📄 *{len(batch)}* exported",
        parse_mode="Markdown"
    )


async def send10_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    user_id = update.effective_user.id
    batch = user_batches.get(user_id, [])
    if not batch:
        await update.message.reply_text("❌ Batch empty.")
        return

    chunk = batch[:10]
    user_batches[user_id] = batch[10:]

    await send_batch(update, user_id, chunk)

    remaining = len(user_batches[user_id])
    if remaining:
        await update.message.reply_text(
            f"📦 *{remaining}* remaining. /send10 again.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("✅ All sent.")


async def sendall_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    user_id = update.effective_user.id
    batch = user_batches.get(user_id, [])
    if not batch:
        await update.message.reply_text("❌ Batch empty.")
        return

    await update.message.reply_text(f"⏳ Sending *{len(batch)}*...", parse_mode="Markdown")
    await send_batch(update, user_id, batch)
    user_batches[user_id] = []
    await update.message.reply_text("✅ All sent.")


async def menu_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    data = q.data

    if data == "send10":
        await send10_cmd(q, ctx)
    elif data == "export":
        await export_cmd(q, ctx)
    elif data == "sendall":
        await sendall_cmd(q, ctx)


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("export", export_cmd))
    app.add_handler(CommandHandler("send10", send10_cmd))
    app.add_handler(CommandHandler("sendall", sendall_cmd))
    app.add_handler(CallbackQueryHandler(menu_cb))

    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🎫 Challan Message Bot v6 running...")
    app.run_polling()


if __name__ == "__main__":
    main()