#!/usr/bin/env python3
"""
VEH Generator Bot — Telegram v2
Handles full Indian RC format: STATE + RTO + SERIES + NUMBER
Supports single-digit RTOs and 1-3 letter series.
"""

import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters, ContextTypes
)

# ═══════════════════════════════════════════════════════
#  ⚙️  CONFIG
# ═══════════════════════════════════════════════════════
BOT_TOKEN = "8044566457:AAGgWN9EqoRjUsrnMK8OmaFfnrffPs_-6Io"
ALLOWED_USERS = []          # leave empty for anyone, or [123456789]
# ═══════════════════════════════════════════════════════

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

STATE, RTO, SERIES, START_NUM, END_NUM, CONFIRM = range(6)

STATE_CODES = {
    "UP": "Uttar Pradesh", "DL": "Delhi", "HR": "Haryana",
    "MH": "Maharashtra", "KA": "Karnataka", "TN": "Tamil Nadu",
    "GJ": "Gujarat", "RJ": "Rajasthan", "MP": "Madhya Pradesh",
    "WB": "West Bengal", "AP": "Andhra Pradesh", "TS": "Telangana",
    "KL": "Kerala", "PB": "Punjab", "BR": "Bihar", "JH": "Jharkhand",
    "OD": "Odisha", "AS": "Assam", "GA": "Goa", "UK": "Uttarakhand",
    "HP": "Himachal Pradesh", "CG": "Chhattisgarh", "JK": "J&K",
    "LA": "Ladakh", "MN": "Manipur", "ML": "Meghalaya", "MZ": "Mizoram",
    "NL": "Nagaland", "TR": "Tripura", "SK": "Sikkim", "AR": "Arunachal",
    "CH": "Chandigarh", "PY": "Puducherry", "AN": "Andaman",
    "LD": "Lakshadweep", "DD": "Daman & Diu", "DN": "Dadra & N. Haveli",
}


def is_allowed(user_id):
    return not ALLOWED_USERS or user_id in ALLOWED_USERS


def generate_list(state, rto, series, start, end, pad=4):
    """Generate RC numbers with proper formatting."""
    out = []
    for i in range(start, end + 1):
        out.append(f"{state}{rto}{series}{i:0{pad}d}")
    return out


def build_menu():
    kb = [
        [InlineKeyboardButton("🚗  Generate Series", callback_data="gen")],
        [InlineKeyboardButton("📋  UP16DP (Noida)", callback_data="up16dp")],
        [InlineKeyboardButton("📋  DL9CB (Delhi)", callback_data="dl9cb")],
        [InlineKeyboardButton("📋  Parse RC", callback_data="parse")],
        [InlineKeyboardButton("❓  Help", callback_data="help")],
    ]
    return InlineKeyboardMarkup(kb)


# ─────────────────────────────────────────────────────
#  RC Parser — accepts full RC and splits it
# ─────────────────────────────────────────────────────
def parse_rc(rc):
    """
    Parse an Indian RC number into components.
    Examples:
      UP16DP0001 -> UP, 16, DP, 0001
      DL9CBL9109 -> DL, 9, CBL, 9109
      MH12AB1234 -> MH, 12, AB, 1234
    Returns (state, rto, series, number) or None if invalid.
    """
    rc = rc.upper().replace(" ", "").replace("-", "")

    # Pattern: 2 letters + 1-2 digits + 1-3 letters + 1-4 digits
    m = re.match(r"^([A-Z]{2})(\d{1,2})([A-Z]{1,3})(\d{1,4})$", rc)
    if not m:
        return None

    state, rto, series, num = m.groups()
    return state, rto, series, num


# ─────────────────────────────────────────────────────
#  Commands
# ─────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("⛔ Not authorized.")
        return ConversationHandler.END

    text = (
        "🚗  *VEH Generator Bot v2*\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "Generate Indian vehicle registration numbers.\n\n"
        "*Quick commands*\n"
        "`/parse DL9CBL9109` — split a full RC\n"
        "`/gen` — custom generator wizard\n"
        "`/up16dp` — UP16DP full series\n"
        "`/dl9cb` — DL9CB full series"
    )
    await update.message.reply_text(
        text, parse_mode="Markdown", reply_markup=build_menu()
    )
    return ConversationHandler.END


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖  *How to use*\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "*Parse an RC*\n"
        "`/parse UP16DP0001`\n"
        "`/parse DL9CBL9109`\n\n"
        "*Generate*\n"
        "`/gen` then follow prompts\n\n"
        "*Format*\n"
        "STATE (2 letters) + RTO (1-2 digits) "
        "+ SERIES (1-3 letters) + NUMBER (1-4 digits)\n\n"
        "*Examples*\n"
        "`UP16DP0001`\n"
        "`DL9CBL9109`\n"
        "`MH12AB1234`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


async def parse_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Parse a full RC number."""
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("⛔ Not authorized.")
        return

    args = ctx.args
    if not args:
        await update.message.reply_text(
            "Usage: `/parse DL9CBL9109`",
            parse_mode="Markdown"
        )
        return

    rc = "".join(args)
    parsed = parse_rc(rc)

    if not parsed:
        await update.message.reply_text(
            f"❌ Could not parse `{rc}`\n"
            f"Expected format: STATE + RTO + SERIES + NUMBER\n"
            f"Example: `DL9CBL9109`",
            parse_mode="Markdown"
        )
        return

    state, rto, series, num = parsed

    text = (
        f"📋  *RC Breakdown*\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"State:   `{state}`  ({STATE_CODES.get(state, 'Unknown')})\n"
        f"RTO:     `{rto}`\n"
        f"Series:  `{series}`\n"
        f"Number:  `{num}`\n\n"
        f"Full:    `{state}{rto}{series}{num}`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def up16dp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("⛔ Not authorized.")
        return

    await update.message.reply_text("⏳ Generating UP16DP0001 → UP16DP9999...")
    numbers = generate_list("UP", "16", "DP", 1, 9999)
    txt = "\n".join(numbers)
    await update.message.reply_document(
        document=txt.encode("utf-8"),
        filename="up16dp.txt",
        caption=f"✅ UP16DP series — {len(numbers)} numbers"
    )


async def dl9cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("⛔ Not authorized.")
        return

    await update.message.reply_text("⏳ Generating DL9CB0001 → DL9CB9999...")
    numbers = generate_list("DL", "9", "CB", 1, 9999)
    txt = "\n".join(numbers)
    await update.message.reply_document(
        document=txt.encode("utf-8"),
        filename="dl9cb.txt",
        caption=f"✅ DL9CB series — {len(numbers)} numbers"
    )


# ─────────────────────────────────────────────────────
#  Custom generator — full RC wizard
# ─────────────────────────────────────────────────────
async def gen_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("⛔ Not authorized.")
        return ConversationHandler.END

    await update.message.reply_text(
        "🚗  *Custom Generator*\n\n"
        "You can either:\n"
        "• Send a full RC prefix like `DL9CBL` and I'll auto-fill\n"
        "• Send a full RC like `DL9CBL9109` to start from that number\n"
        "• Send `/cancel` to abort",
        parse_mode="Markdown"
    )
    return STATE


async def got_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Accept a full RC like DL9CBL9109 OR just the prefix DL9CBL."""
    raw = update.message.text.strip().upper().replace(" ", "")

    # Try to parse full RC first
    parsed = parse_rc(raw)
    if parsed:
        state, rto, series, num = parsed
        ctx.user_data["state"] = state
        ctx.user_data["rto"] = rto
        ctx.user_data["series"] = series
        ctx.user_data["start"] = int(num)
        ctx.user_data["end"] = 9999
        ctx.user_data["pad"] = len(num)

        preview = "\n".join(generate_list(state, rto, series,
                                          int(num), min(int(num) + 4, 9999),
                                          len(num)))
        await update.message.reply_text(
            f"✅ Parsed!\n\n"
            f"State:   `{state}` ({STATE_CODES.get(state, 'Unknown')})\n"
            f"RTO:     `{rto}`\n"
            f"Series:  `{series}`\n"
            f"Start:   `{num}`\n"
            f"End:     `9999`\n\n"
            f"Preview:\n```\n{preview}\n```\n\n"
            f"Reply *yes* to generate or *no* to cancel.",
            parse_mode="Markdown"
        )
        return CONFIRM

    # Otherwise try prefix-only (letters + digits)
    m = re.match(r"^([A-Z]{2})(\d{1,2})([A-Z]{1,3})$", raw)
    if m:
        state, rto, series = m.groups()
        ctx.user_data["state"] = state
        ctx.user_data["rto"] = rto
        ctx.user_data["series"] = series
        await update.message.reply_text(
            f"✅ Prefix: `{state}{rto}{series}`\n\n"
            f"Send the *range* — format `START-END`\n"
            f"Example: `1-9999`",
            parse_mode="Markdown"
        )
        return START_NUM

    await update.message.reply_text(
        "❌ Invalid format.\n\n"
        "Try:\n"
        "• Full RC: `DL9CBL9109`\n"
        "• Prefix:  `DL9CBL`\n"
        "• Or /cancel",
        parse_mode="Markdown"
    )
    return STATE


async def got_range(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().replace(" ", "")
    if "-" not in txt:
        await update.message.reply_text("❌ Format: `START-END`. Try again or /cancel.",
                                        parse_mode="Markdown")
        return START_NUM

    try:
        start_s, end_s = txt.split("-", 1)
        start, end = int(start_s), int(end_s)
    except ValueError:
        await update.message.reply_text("❌ Invalid numbers. Try again or /cancel.")
        return START_NUM

    if start < 0 or end < start or end > 99999:
        await update.message.reply_text("❌ Range must be 0–99999 and start ≤ end.")
        return START_NUM

    ctx.user_data["start"] = start
    ctx.user_data["end"] = end

    st = ctx.user_data["state"]
    rto = ctx.user_data["rto"]
    ser = ctx.user_data["series"]
    pad = max(len(str(start)), 4)
    total = end - start + 1

    preview = "\n".join(generate_list(st, rto, ser, start,
                                      min(start + 4, end), pad))

    await update.message.reply_text(
        f"📋  *Confirm*\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"Prefix:  `{st}{rto}{ser}`\n"
        f"Range:   `{start:0{pad}d}` → `{end:0{pad}d}`\n"
        f"Total:   *{total}* numbers\n\n"
        f"Preview:\n```\n{preview}\n```\n\n"
        f"Send *yes* to generate, *no* to cancel.",
        parse_mode="Markdown"
    )
    return CONFIRM


async def got_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ans = update.message.text.strip().lower()
    if ans not in ("yes", "y", "no", "n"):
        await update.message.reply_text("Send *yes* or *no*.", parse_mode="Markdown")
        return CONFIRM

    if ans in ("no", "n"):
        await update.message.reply_text("❌ Cancelled.")
        return ConversationHandler.END

    st = ctx.user_data["state"]
    rto = ctx.user_data["rto"]
    ser = ctx.user_data["series"]
    start = ctx.user_data["start"]
    end = ctx.user_data["end"]
    pad = max(len(str(start)), 4)

    await update.message.reply_text("⏳ Generating...")

    numbers = generate_list(st, rto, ser, start, end, pad)
    txt = "\n".join(numbers)
    filename = f"{st}{rto}{ser}_{start:0{pad}d}-{end:0{pad}d}.txt"

    await update.message.reply_document(
        document=txt.encode("utf-8"),
        filename=filename,
        caption=f"✅ Generated *{len(numbers)}* numbers\n"
                f"Prefix: `{st}{rto}{ser}`\n"
                f"Range: `{start:0{pad}d}` → `{end:0{pad}d}`",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


# ─────────────────────────────────────────────────────
#  Inline menu
# ─────────────────────────────────────────────────────
async def menu_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "gen":
        await q.message.reply_text("Send /gen to start.")
    elif q.data == "up16dp":
        await up16dp(q, ctx)
    elif q.data == "dl9cb":
        await dl9cb(q, ctx)
    elif q.data == "parse":
        await q.message.reply_text("Send `/parse DL9CBL9109`",
                                   parse_mode="Markdown")
    elif q.data == "help":
        await help_cmd(q, ctx)


# ─────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("gen", gen_start)],
        states={
            STATE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, got_input)],
            RTO:       [MessageHandler(filters.TEXT & ~filters.COMMAND, got_input)],
            SERIES:    [MessageHandler(filters.TEXT & ~filters.COMMAND, got_input)],
            START_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_range)],
            CONFIRM:   [MessageHandler(filters.TEXT & ~filters.COMMAND, got_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("parse", parse_cmd))
    app.add_handler(CommandHandler("up16dp", up16dp))
    app.add_handler(CommandHandler("dl9cb", dl9cb))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(menu_cb))

    print("🚗 VEH Generator Bot v2 running...")
    app.run_polling()


if __name__ == "__main__":
    main()