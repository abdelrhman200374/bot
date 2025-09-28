import json
import logging
import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from keep_alive import keep_alive

# ==== الإعدادات ====
BOT_TOKEN = "8013467792:AAGiE2fNVOP-riTSAjPg8CYH8PL6CQ2pKBc"
CONTENT_CHANNEL_ID = -1002977863836
DATA_FILE = "data.json"
SESSION_FILE = "sessions.json"
USERS_FILE = "users.json"
POSTS_FILE = "posts_map.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ───────────────────────────────
# أدوات JSON
# ───────────────────────────────
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ───────────────────────────────
# /start
# ───────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return

    data = load_json(DATA_FILE, {"terms": {}})
    users = load_json(USERS_FILE, [])
    sessions = load_json(SESSION_FILE, {})
    uid = str(update.effective_user.id)

    sessions[uid] = {"level": "root", "last_msg_id": 0}
    save_json(SESSION_FILE, sessions)

    if int(uid) not in users:
        users.append(int(uid))
        save_json(USERS_FILE, users)

    keyboard = [[t] for t in data.get("terms", {}).keys()]
    keyboard.append(["📊 التقارير"])
    await update.message.reply_text("🎓 اختر الترم:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

# ───────────────────────────────
# handle_message
# ───────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user:
        return

    data = load_json(DATA_FILE, {"terms": {}})
    users = load_json(USERS_FILE, [])
    sessions = load_json(SESSION_FILE, {})
    uid = str(update.effective_user.id)
    msg = (update.message.text or "").strip()
    session = sessions.get(uid, {"level": "root"})

    # زر الرجوع
    if msg == "⬅️ رجوع":
        level = session.get("level", "root")

        if level == "lecture":
            session["level"] = "section"
            term = session["term"]
            section = session["section"]
            lectures = data["terms"][term][section]
            keyboard = [[l] for l in lectures.keys()] + [["⬅️ رجوع"]]
            await update.message.reply_text(f"📖 {section}:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

        elif level == "section":
            session["level"] = "term"
            term = session["term"]
            sections = {k: v for k, v in data["terms"][term].items() if k != "📊 التقارير"}
            keyboard = [[s] for s in sections.keys()] + [["⬅️ رجوع"]]
            await update.message.reply_text(f"📚 {term}:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

        elif level == "term":
            session["level"] = "root"
            keyboard = [[t] for t in data.get("terms", {}).keys()]
            keyboard.append(["📊 التقارير"])
            await update.message.reply_text("🎓 اختر الترم:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

        elif level == "reports":
            session["level"] = "term"
            term = session["term"]
            reports = data["terms"][term].get("📊 التقارير", {})
            keyboard = [[week] for week in sorted(reports.keys())] + [["⬅️ رجوع"]]
            await update.message.reply_text("📊 اختر الأسبوع:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

        save_json(SESSION_FILE, sessions)
        return

    # اختيار الترم
    if msg in data.get("terms", {}):
        session["level"] = "term"
        session["term"] = msg
        save_json(SESSION_FILE, sessions)
        sections = {k: v for k, v in data["terms"][msg].items() if k != "📊 التقارير"}
        keyboard = [[s] for s in sections.keys()] + [["⬅️ رجوع"]]
        await update.message.reply_text(f"📚 {msg}:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return

    # اختيار قسم داخل الترم الحالي
    if session.get("level") in ["term", "section"]:
        term = session["term"]
        term_sections = data["terms"][term]
        if msg in term_sections:
            session["level"] = "section"
            session["section"] = msg
            save_json(SESSION_FILE, sessions)
            lectures = term_sections[msg]
            keyboard = [[l] for l in lectures.keys()] + [["⬅️ رجوع"]]
            await update.message.reply_text(f"📖 {msg}:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
            return

    # اختيار محاضرة داخل القسم الحالي
    if session.get("level") == "section":
        term = session["term"]
        section = session["section"]
        lectures = data["terms"][term][section]
        if msg in lectures:
            session["level"] = "lecture"
            session["lecture"] = msg
            save_json(SESSION_FILE, sessions)
            content = lectures[msg]
            keyboard = []
            if "audio" in content: keyboard.append(["🎧 مقطع صوتي"])
            if "video" in content: keyboard.append(["🎥 فيديو"])
            if "document" in content: keyboard.append(["📘 كتاب"])
            if "photo" in content: keyboard.append(["🖼️ صور"])
            if "text" in content: keyboard.append(["📝 ملاحظات"])
            keyboard.append(["⬅️ رجوع"])
            await update.message.reply_text(f"🎓 اختر نوع المحتوى في المحاضرة **{msg}**:",
                                            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
            return

    # إرسال المحتوى
    if session.get("level") == "lecture":
        term = session["term"]
        section = session["section"]
        lecture = session["lecture"]
        content = data["terms"][term][section][lecture]
        try:
            if msg == "🎧 مقطع صوتي" and "audio" in content:
                await context.bot.copy_message(chat_id=update.effective_chat.id,
                                               from_chat_id=CONTENT_CHANNEL_ID,
                                               message_id=int(content["audio"]))
            elif msg == "🎥 فيديو" and "video" in content:
                await context.bot.copy_message(chat_id=update.effective_chat.id,
                                               from_chat_id=CONTENT_CHANNEL_ID,
                                               message_id=int(content["video"]))
            elif msg == "📘 كتاب" and "document" in content:
                docs = content["document"]
                if not isinstance(docs, list):
                    docs = [docs]
                for doc_id in docs:
                    await context.bot.copy_message(chat_id=update.effective_chat.id,
                                                   from_chat_id=CONTENT_CHANNEL_ID,
                                                   message_id=int(doc_id))
            elif msg == "🖼️ صور" and "photo" in content:
                photos = content["photo"]
                if not isinstance(photos, list):
                    photos = [photos]
                for photo_id in photos:
                    await context.bot.copy_message(chat_id=update.effective_chat.id,
                                                   from_chat_id=CONTENT_CHANNEL_ID,
                                                   message_id=int(photo_id))
            elif msg == "📝 ملاحظات" and "text" in content:
                await update.message.reply_text(content["text"])
        except Exception as e:
            logger.exception("حدث خطأ أثناء إرسال المحتوى:")
            await update.message.reply_text("❌ حدث خطأ أثناء إرسال المحتوى.")

    # زر التقارير
    if msg == "📊 التقارير":
        term = session.get("term", "الترم الأول")  # اختر الترم الحالي
        term_reports = data.get("terms", {}).get(term, {}).get("📊 التقارير", {})
        if not term_reports:
            await update.message.reply_text("لا توجد تقارير متاحة.")
            return
        keyboard = [[week] for week in sorted(term_reports.keys())] + [["⬅️ رجوع"]]
        session["level"] = "reports"
        session["reports"] = term_reports
        save_json(SESSION_FILE, sessions)
        await update.message.reply_text("📊 اختر الأسبوع:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return

    # اختيار أسبوع من التقارير أو أي تقرير
    if session.get("level") == "reports":
        week_reports = session.get("reports", {})
        if msg in week_reports:
            report_content = week_reports[msg]
            # إرسال أي نوع محتوى متاح
            if "photo" in report_content:
                photos = report_content["photo"]
                if not isinstance(photos, list):
                    photos = [photos]
                for photo_id in photos:
                    try:
                        await context.bot.copy_message(
                            chat_id=update.effective_chat.id,
                            from_chat_id=CONTENT_CHANNEL_ID,
                            message_id=int(photo_id)
                        )
                    except Exception as e:
                        logger.exception(f"حدث خطأ أثناء إرسال تقرير {msg}:")
            if "document" in report_content:
                docs = report_content["document"]
                if not isinstance(docs, list):
                    docs = [docs]
                for doc_id in docs:
                    await context.bot.copy_message(
                        chat_id=update.effective_chat.id,
                        from_chat_id=CONTENT_CHANNEL_ID,
                        message_id=int(doc_id)
                    )
            if "text" in report_content:
                await update.message.reply_text(report_content["text"])
            return

# ───────────────────────────────
# forward_post → من القناة للطلاب
# ───────────────────────────────
async def forward_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    post = update.channel_post
    if not post:
        return
    users = load_json(USERS_FILE, [])
    posts_map = load_json(POSTS_FILE, {})
    posts_map.setdefault(str(post.message_id), {})
    for uid in users:
        try:
            if post.text:
                sent = await context.bot.send_message(uid, post.text)
            elif post.photo:
                sent = await context.bot.send_photo(uid, photo=post.photo[-1].file_id, caption=post.caption or "")
            elif post.video:
                sent = await context.bot.send_video(uid, video=post.video.file_id, caption=post.caption or "")
            elif post.document:
                sent = await context.bot.send_document(uid, document=post.document.file_id, caption=post.caption or "")
            else:
                continue
            posts_map[str(post.message_id)][str(uid)] = sent.message_id
        except Exception as e:
            logger.warning(f"❌ {uid}: {e}")
    save_json(POSTS_FILE, posts_map)

# ───────────────────────────────
# main
# ───────────────────────────────
def main():
    keep_alive()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, forward_post))
    app.run_polling()

if __name__ == "__main__":
    main()
