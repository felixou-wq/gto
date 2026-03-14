"""
🤖 AI Telegram Bot - Compatible with all Python versions
"""

import os
import sys
import requests
from datetime import datetime, timedelta

# Get keys from environment
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")

# Memory
history = {}
reminders = {}

def ask_ai(message, user_id):
    if user_id not in history:
        history[user_id] = []
    history[user_id].append({"role": "user", "content": message})
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "system", "content": "You are helpful."}] + history[user_id][-10:],
                "max_tokens": 2000
            },
            timeout=30
        )
        if r.status_code == 200:
            reply = r.json()['choices'][0]['message']['content']
            history[user_id].append({"role": "assistant", "content": reply})
            return reply
        return f"API Error: {r.status_code}"
    except Exception as e:
        return f"Error: {e}"

# ===== SIMPLE TELEGRAM BOT =====
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

async def start(update, context):
    await update.message.reply_text("""🤖 AI Bot!

Message me to chat!

/research <topic>
/remind 14:30 Message
/remind every 1h Message
/reminders
/clear
""")

async def chat(update, context):
    user_id = update.effective_user.id
    msg = update.message.text
    await update.message.chat.send_action("typing")
    reply = ask_ai(msg, user_id)
    await update.message.reply_text(reply[:4000] if len(reply) > 4000 else reply)

async def research(update, context):
    if not context.args:
        await update.message.reply_text("Usage: /research <topic>")
        return
    query = " ".join(context.args)
    await update.message.chat.send_action("typing")
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                results.append(f"📌 {r['title']}\n{r['body'][:100]}...\n{r['href']}")
        await update.message.reply_text("\n\n".join(results)[:4000] or "No results")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def remind(update, context):
    if len(context.args) < 2:
        await update.message.reply_text("Usage:\n/remind 14:30 Message\n/remind every 1h Message")
        return
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if user_id not in reminders:
        reminders[user_id] = []
    
    if context.args[0].lower() == "every":
        interval = context.args[1]
        msg = " ".join(context.args[2:])
        mins = int(interval.lower().replace("h", "").replace("m", "")) * (60 if "h" in interval.lower() else 1)
        reminders[user_id].append({"chat_id": chat_id, "msg": msg, "recurring": True, "interval": mins, "next": datetime.now() + timedelta(minutes=mins)})
        await update.message.reply_text(f"✅ Every {mins}min: {msg}")
    else:
        try:
            h, m = map(int, context.args[0].split(":"))
            msg = " ".join(context.args[1:])
            now = datetime.now()
            trigger = now.replace(hour=h, minute=m, second=0)
            if trigger <= now: trigger += timedelta(days=1)
            reminders[user_id].append({"chat_id": chat_id, "msg": msg, "trigger": trigger})
            await update.message.reply_text(f"✅ {trigger.strftime('%m/%d %H:%M')}: {msg}")
        except:
            await update.message.reply_text("❌ Use: 14:30")

async def view_reminders(update, context):
    user_reminders = reminders.get(update.effective_user.id, [])
    if not user_reminders:
        await update.message.reply_text("No reminders")
        return
    text = "⏰ Reminders:\n"
    for i, r in enumerate(user_reminders, 1):
        if r.get("recurring"):
            text += f"{i}. 🔄 {r['interval']}min - {r['msg'][:30]}\n"
        else:
            text += f"{i}. 📅 {r['trigger'].strftime('%m/%d %H:%M')} - {r['msg'][:30]}\n"
    await update.message.reply_text(text)

async def clear(update, context):
    history[update.effective_user.id] = []
    await update.message.reply_text("✅ Cleared!")

async def check_reminders(app):
    while True:
        now = datetime.now()
        for user_id, user_reminders in list(reminders.items()):
            for i, r in enumerate(user_reminders):
                trigger = False
                if r.get("recurring") and now >= r["next"]:
                    trigger = True
                    reminders[user_id][i]["next"] = now + timedelta(minutes=r["interval"])
                elif not r.get("recurring") and r.get("trigger") and now >= r["trigger"]:
                    trigger = True
                    reminders[user_id][i]["trigger"] = None
                if trigger:
                    try:
                        await app.bot.send_message(r["chat_id"], f"⏰ REMINDER!\n\n{r['msg']}")
                    except:
                        pass
        import asyncio
        await asyncio.sleep(30)

def main():
    if not TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set!")
        sys.exit(1)
    if not GROQ_KEY:
        print("❌ GROQ_API_KEY not set!")
        sys.exit(1)
    
    print("=" * 40)
    print("🤖 Bot Starting...")
    print("=" * 40)
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("research", research))
    application.add_handler(CommandHandler("remind", remind))
    application.add_handler(CommandHandler("reminders", view_reminders))
    application.add_handler(CommandHandler("clear", clear))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    
    # Add post init for reminder checker
    import asyncio
    async def post_init(app):
        asyncio.create_task(check_reminders(app))
    application.post_init = post_init
    
    print("✅ Bot Running!")
    print("=" * 40)
    
    application.run_polling()

if __name__ == "__main__":
    main()
