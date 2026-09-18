#!/usr/bin/env python3
"""
Series Vending Bot — Persistent Vending with Channel Index
"""

import os
import re
import io
import json
import asyncio
import logging
from datetime import datetime
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

# ═══════════════════════════════════════════════════════
#  ⚙️  CONFIG
# ═══════════════════════════════════════════════════════
BOT_TOKEN = "8932518970:AAEVxFQa3xxvfu8zzeYBXEWw2xJE2PePuug"
STORAGE_CHANNEL_ID = -1004411229864
ALLOWED_USERS = []
BATCH_SIZE = 50
INDEX_FILENAME = "_index.json"
# ═══════════════════════════════════════════════════════

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

series_store = defaultdict(list)
vended_set = set()
user_state = {}
channel_index = {}


def is_allowed(user_id):
    return not ALLOWED_USERS or user_id in ALLOWED_USERS


def extract_series(vehicle):
    m = re.match(r"^([A-Z]{2}\d{1,2}[A-Z]{1,3})", vehicle)
    return m.group(1) if m else None


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


# ─────────────────────────────────────────────────────
#  Index management
# ─────────────────────────────────────────────────────
async def download_index(ctx):
    global channel_index
    channel_index = {}

    try:
        chat = await ctx.bot.get_chat(STORAGE_CHANNEL_ID)
        pinned = chat.pinned_message

        if pinned and pinned.document and pinned.document.file_name == INDEX_FILENAME:
            file = await ctx.bot.get_file(pinned.document.file_id)
            content = await file.download_as_bytearray()
            channel_index = json.loads(content.decode("utf-8"))
            logger.info(f"Index loaded from pin: {len(channel_index)} files")
            return

        logger.info("No pinned index found. Bot will start with empty index.")
    except Exception as e:
        logger.error(f"Index load error: {e}")


async def upload_index(ctx):
    try:
        content = json.dumps(channel_index, indent=2).encode("utf-8")
        buf = io.BytesIO(content)
        buf.name = INDEX_FILENAME

        msg = await ctx.bot.send_document(
            chat_id=STORAGE_CHANNEL_ID,
            document=buf,
            filename=INDEX_FILENAME,
            caption=f"Index updated · {len(channel_index)} files · {datetime.utcnow().isoformat()}"
        )

        try:
            await ctx.bot.pin_chat_message(
                chat_id=STORAGE_CHANNEL_ID,
                message_id=msg.message_id,
                disable_notification=True
            )
        except Exception as e:
            logger.warning(f"Could not pin index: {e}")

    except Exception as e:
        logger.error(f"Index upload error: {e}")


async def send_file_to_channel(ctx, filename, content_bytes, caption=""):
    buf = io.BytesIO(content_bytes)
    buf.name = filename
    msg = await ctx.bot.send_document(
        chat_id=STORAGE_CHANNEL_ID,
        document=buf,
        caption=caption,
        filename=filename
    )
    channel_index[filename] = msg.message_id
    await upload_index(ctx)
    return msg


async def fetch_and_process_all_files(ctx):
    global series_store, vended_set
    series_store = defaultdict(list)
    vended_set = set()

    if not channel_index:
        logger.info("No files in index.")
        return

    sorted_files = sorted(channel_index.items(), key=lambda x: x[1])

    for filename, msg_id in sorted_files:
        if not filename.startswith("vended_"):
            continue
        try:
            fwd = await ctx.bot.forward_message(
                chat_id=ctx.bot.id,
                from_chat_id=STORAGE_CHANNEL_ID,
                message_id=msg_id
            )
            file = await ctx.bot.get_file(fwd.document.file_id)
            content = await file.download_as_bytearray()
            text = content.decode("utf-8", errors="ignore")
            for line in text.strip().split("\n"):
                parsed = parse_line(line)
                if parsed:
                    vended_set.add(parsed[0])

            try:
                await ctx.bot.delete_message(chat_id=ctx.bot.id, message_id=fwd.message_id)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Failed vended file {filename}: {e}")

    logger.info(f"Loaded {len(vended_set)} vended entries")

    for filename, msg_id in sorted_files:
        if filename.startswith("vended_") or filename == INDEX_FILENAME:
            continue
        try:
            fwd = await ctx.bot.forward_message(
                chat_id=ctx.bot.id,
                from_chat_id=STORAGE_CHANNEL_ID,
                message_id=msg_id
            )
            file = await ctx.bot.get_file(fwd.document.file_id)
            content = await file.download_as_bytearray()
            text = content.decode("utf-8", errors="ignore")
            for line in text.strip().split("\n"):
                parsed = parse_line(line)
                if not parsed:
                    continue
                vehicle, phone = parsed
                if vehicle in vended_set:
                    continue
                series = extract_series(vehicle)
                if not series:
                    continue
                existing = {v for v, p in series_store[series]}
                if vehicle not in existing:
                    series_store[series].append((vehicle, phone))

            try:
                await ctx.bot.delete_message(chat_id=ctx.bot.id, message_id=fwd.message_id)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Failed data file {filename}: {e}")

    total = sum(len(v) for v in series_store.values())
    logger.info(f"Loaded {len(series_store)} series, {total} available entries")


async def load_from_channel(ctx):
    await download_index(ctx)
    await fetch_and_process_all_files(ctx)


# ─────────────────────────────────────────────────────
#  Commands
# ─────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("⛔ Not authorized.")
        return

    total = sum(len(v) for v in series_store.values())

    text = (
        "📦  *Series Vending Bot*\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Loaded: *{len(series_store)}* series · *{total}* available\n"
        f"✅ Vended: *{len(vended_set)}* tracked\n"
        f"📁 Indexed files: *{len(channel_index)}*\n\n"
        "*Commands*\n"
        "`/series` — pick a series to vend\n"
        "`/stats` — inventory\n"
        "`/reload` — refresh from channel\n"
        "`/index` — show channel file index\n"
        "`/clear <series>` — remove from memory\n\n"
        "*Load data:* send `.txt`/`.csv` file\n"
        "*Vend format:* `VEHICLE,PHONE`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def reload_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return
    await update.message.reply_text("⏳ Reloading...")
    await load_from_channel(ctx)
    total = sum(len(v) for v in series_store.values())
    await update.message.reply_text(
        f"✅ Reloaded.\n"
        f"📊 *{len(series_store)}* series · *{total}* available\n"
        f"✅ *{len(vended_set)}* vended tracked",
        parse_mode="Markdown"
    )


async def index_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    if not channel_index:
        await update.message.reply_text("📭 Index empty.")
        return

    lines = ["📁  *Channel Index*", "━━━━━━━━━━━━━━━━━━━", ""]
    for name, mid in sorted(channel_index.items(), key=lambda x: x[1]):
        prefix = "🔴" if name.startswith("vended_") else "🟢"
        lines.append(f"{prefix} `{name}` · `#{mid}`")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def stats_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    if not series_store:
        await update.message.reply_text("📭 No data loaded.")
        return

    lines = ["📊  *Inventory*", "━━━━━━━━━━━━━━━━━━━", ""]
    total = 0
    for series in sorted(series_store.keys()):
        count = len(series_store[series])
        total += count
        lines.append(f"  `{series}`  ➜  *{count}*")
    lines.append("")
    lines.append(f"📦 Available: *{total}*")
    lines.append(f"✅ Vended: *{len(vended_set)}*")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def series_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    if not series_store:
        await update.message.reply_text("📭 No data loaded.")
        return

    buttons = []
    for series in sorted(series_store.keys()):
        count = len(series_store[series])
        buttons.append([
            InlineKeyboardButton(
                f"📦  {series}  ({count})",
                callback_data=f"series:{series}"
            )
        ])

    await update.message.reply_text(
        "📦  *Choose a series to vend:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def vend_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await series_cmd(update, ctx)


async def clear_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: `/clear UP16DP`", parse_mode="Markdown")
        return

    series = args[0].upper()
    if series in series_store:
        del series_store[series]
        await update.message.reply_text(f"✅ Cleared `{series}` from memory.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Series `{series}` not found.", parse_mode="Markdown")


# ─────────────────────────────────────────────────────
#  Handle uploaded files
# ─────────────────────────────────────────────────────
async def handle_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    doc = update.message.document
    filename = doc.file_name or ""

    if filename.startswith("vended_") or filename == INDEX_FILENAME:
        return

    if not (filename.lower().endswith(".csv") or filename.lower().endswith(".txt")):
        await update.message.reply_text("❌ Only `.csv` or `.txt` files accepted.", parse_mode="Markdown")
        return

    await update.message.reply_text("⏳ Processing file...")

    try:
        file = await ctx.bot.get_file(doc.file_id)
        content = await file.download_as_bytearray()
    except Exception as e:
        await update.message.reply_text(f"❌ Download failed: {str(e)[:100]}")
        return

    try:
        await send_file_to_channel(
            ctx,
            filename=filename,
            content_bytes=bytes(content),
            caption=f"Data: {filename}"
        )
    except Exception as e:
        logger.error(f"Channel store failed: {e}")
        await update.message.reply_text(f"⚠️ Channel store failed (retrying data only): {str(e)[:100]}")

    added = 0
    for line in content.decode("utf-8", errors="ignore").strip().split("\n"):
        parsed = parse_line(line)
        if not parsed:
            continue
        vehicle, phone = parsed
        if vehicle in vended_set:
            continue
        series = extract_series(vehicle)
        if not series:
            continue
        existing = {v for v, p in series_store[series]}
        if vehicle not in existing:
            series_store[series].append((vehicle, phone))
            added += 1

    if added == 0:
        await update.message.reply_text("❌ No new entries.")
        return

    total_all = sum(len(v) for v in series_store.values())

    await update.message.reply_text(
        f"✅ Added *{added}* entries\n"
        f"📊 Total available: *{total_all}*",
        parse_mode="Markdown"
    )

    await series_cmd(update, ctx)


# ─────────────────────────────────────────────────────
#  Handle quantity input
# ─────────────────────────────────────────────────────
async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    user_id = update.effective_user.id
    state = user_state.get(user_id, {})

    if state.get("action") != "waiting_qty":
        await update.message.reply_text(
            "ℹ️ Send a `.txt`/`.csv` file to load data, or use `/series`.",
            parse_mode="Markdown"
        )
        return

    series = state.get("series")
    txt = update.message.text.strip()

    if not txt.isdigit():
        await update.message.reply_text("❌ Send a number, e.g. `100`", parse_mode="Markdown")
        return

    qty = int(txt)
    if qty < 1 or qty > 5000:
        await update.message.reply_text("❌ Quantity must be 1–5000.")
        return

    pool = series_store.get(series, [])
    if not pool:
        await update.message.reply_text(f"❌ No entries left in `{series}`.", parse_mode="Markdown")
        user_state.pop(user_id, None)
        return

    if qty > len(pool):
        await update.message.reply_text(
            f"⚠️ Only *{len(pool)}* left. Sending all.",
            parse_mode="Markdown"
        )
        qty = len(pool)

    vend = pool[:qty]
    series_store[series] = pool[qty:]

    for vehicle, phone in vend:
        vended_set.add(vehicle)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    vended_filename = f"vended_{series}_{timestamp}.txt"
    vended_content = "\n".join(f"{vehicle},{phone}" for vehicle, phone in vend)

    try:
        await send_file_to_channel(
            ctx,
            filename=vended_filename,
            content_bytes=vended_content.encode("utf-8"),
            caption=f"Vended {len(vend)} from {series}"
        )
    except Exception as e:
        logger.error(f"Vended file store failed: {e}")

    await update.message.reply_text(
        f"📤 Vending *{len(vend)}* from `{series}`...",
        parse_mode="Markdown"
    )

    for i in range(0, len(vend), BATCH_SIZE):
        chunk = vend[i:i + BATCH_SIZE]
        block = "\n".join(f"{vehicle},{phone}" for vehicle, phone in chunk)
        await update.message.reply_text(f"```\n{block}\n```", parse_mode="Markdown")
        await asyncio.sleep(0.4)

    remaining = len(series_store.get(series, []))
    await update.message.reply_text(
        f"✅ Vend complete.\n"
        f"📦 Remaining: *{remaining}*\n"
        f"✅ Total vended: *{len(vended_set)}*",
        parse_mode="Markdown"
    )

    user_state.pop(user_id, None)


# ─────────────────────────────────────────────────────
#  Inline buttons
# ─────────────────────────────────────────────────────
async def menu_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    data = q.data
    user_id = q.from_user.id

    if data.startswith("series:"):
        series = data.replace("series:", "")
        pool = series_store.get(series, [])

        if not pool:
            await q.message.reply_text(f"❌ No entries in `{series}`.", parse_mode="Markdown")
            return

        user_state[user_id] = {"action": "waiting_qty", "series": series}

        await q.message.reply_text(
            f"📦 *{series}*\n"
            f"Available: *{len(pool)}* entries\n\n"
            f"Send the *quantity* you want to vend.\n"
            f"Example: `100`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
            ])
        )

    elif data == "cancel":
        user_state.pop(user_id, None)
        await q.message.reply_text("❌ Cancelled.")


# ─────────────────────────────────────────────────────
#  Startup
# ─────────────────────────────────────────────────────
async def post_init(app: Application):
    logger.info("Loading data from channel...")
    await load_from_channel(app)
    logger.info("Startup complete")


def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("series", series_cmd))
    app.add_handler(CommandHandler("vend", vend_cmd))
    app.add_handler(CommandHandler("reload", reload_cmd))
    app.add_handler(CommandHandler("index", index_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(CallbackQueryHandler(menu_cb))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("📦 Series Vending Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()