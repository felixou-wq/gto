"""
🤖 AI Telegram Bot - Fully Fixed for Render
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

# Reminders storage
reminders = {}

# ===== TELEGRAM BOT =====
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

async def start(update: Update, context):
    await update.message.reply_text("""🤖 *AI Bot Online!*

Just message me to chat!

/research <topic> - Search web
/remind <time> <msg> - Set reminder  
/remind every 1h <msg> - Recurring
/reminders - View reminders
/clear - Clear chat
""", parse_mode="Markdown")

async def chat(update: Update, context):
    user_id = update.effective_user.id
    msg = update.message.text
    await update.message.chat.send_action("typing")
    reply = ask_ai(msg, user_id)
    if len(reply) > 4000:
        for i in range(0, len(reply), 4000):
            await update.message.reply_text(reply[i:i+4000])
    else:
        await update.message.reply_text(reply)

async def research(update: Update, context):
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
                results.append(f"📌 {r['title']}\n{r['body'][:150]}...\n🔗 {r['href']}")
        await update.message.reply_text(f"🔍 {query}\n\n" + "\n\n".join(results)[:4000])
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def set_reminder(update: Update, context):
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
        if "h" in interval.lower():
            mins = int(interval.lower().replace("h", "")) * 60
        elif "m" in interval.lower():
            mins = int(interval.lower().replace("m", ""))
        else:
            mins = int(interval) * 60
        reminders[user_id].append({
            "chat_id": chat_id, "msg": msg, "recurring": True,
            "interval": mins, "next": datetime.now() + timedelta(minutes=mins)
        })
        await update.message.reply_text(f"✅ Every {mins}min: {msg}")
    else:
        time_str = context.args[0]
        msg = " ".join(context.args[1:])
        try:
            h, m = map(int, time_str.split(":"))
            now = datetime.now()
            trigger = now.replace(hour=h, minute=m, second=0)
            if trigger <= now:
                trigger += timedelta(days=1)
            reminders[user_id].append({"chat_id": chat_id, "msg": msg, "trigger": trigger, "recurring": False})
            await update.message.reply_text(f"✅ Set for {trigger.strftime('%m/%d %H:%M')}: {msg}")
        except:
            await update.message.reply_text("❌ Use format: 14:30")

async def view_reminders(update: Update, context):
    user_id = update.effective_user.id
    user_reminders = reminders.get(user_id, [])
    if not user_reminders:
        await update.message.reply_text("📭 No reminders")
        return
    text = "⏰ Your Reminders:\n\n"
    for i, r in enumerate(user_reminders, 1):
        if r["recurring"]:
            text += f"{i}. 🔄 Every {r['interval']}min\n   {r['msg']}\n\n"
        else:
            text += f"{i}. 📅 {r['trigger'].strftime('%m/%d %H:%M')}\n   {r['msg']}\n\n"
    await update.message.reply_text(text)

async def clear(update: Update, context):
    history[update.effective_user.id] = []
    await update.message.reply_text("✅ Cleared!")

# Background reminder checker
import asyncio
import threading

async def check_reminders(bot):
    while True:
        try:
            now = datetime.now()
            for user_id, user_reminders in reminders.items():
                for i, r in enumerate(user_reminders):
                    should_trigger = False
                    if r["recurring"] and now >= r["next"]:
                        should_trigger = True
                        user_reminders[i]["next"] = now + timedelta(minutes=r["interval"])
                    elif not r["recurring"] and r.get("trigger") and now >= r["trigger"]:
                        should_trigger = True
                        user_reminders[i]["trigger"] = None
                    if should_trigger:
                        try:
                            await bot.send_message(r["chat_id"], f"⏰ REMINDER!\n\n{r['msg']}")
                        except:
                            pass
        except:
            pass
        await asyncio.sleep(30)

def main():
    if not TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not set!")
        return
    if not GROQ_KEY:
        print("❌ GROQ_API_KEY not set!")
        return
    
    print("=" * 40)
    print("🤖 Bot Starting...")
    print("=" * 40)
    
    # Build app
    app = Application.builder().token(TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("research", research))
    app.add_handler(CommandHandler("remind", set_reminder))
    app.add_handler(CommandHandler("reminders", view_reminders))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    
    # Start reminder checker
    async def post_init(application):
        asyncio.create_task(check_reminders(application.bot))
    
    app.post_init = post_init
    
    print("✅ Bot Running!")
    print("=" * 40)
    
    # Run with proper event loop
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
