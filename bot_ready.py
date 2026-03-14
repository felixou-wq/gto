"""
🤖 SIMPLE AI BOT - Ready to Run!
Uses Environment Variables for security
"""

import os

# Get keys from environment variables (safer!)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# ============================================
# DON'T CHANGE ANYTHING BELOW
# ============================================

import threading
import time
from datetime import datetime, timedelta
from collections import defaultdict

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ChatAction
import requests
from duckduckgo_search import DDGS
from fpdf import FPDF

# Memory
chats = {}
reminders_data = {}

# ============================================
# AI FUNCTION
# ============================================

def ask_ai(message, history=[]):
    """Ask Groq AI"""
    messages = [{"role": "system", "content": "You are a helpful AI assistant."}] + history + [{"role": "user", "content": message}]
    
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 4096
            },
            timeout=60
        )
        if r.status_code == 200:
            return r.json()['choices'][0]['message']['content']
        else:
            return f"API Error: {r.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"

# ============================================
# HELPER FUNCTIONS  
# ============================================

def search_web(query):
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                results.append(f"📌 {r['title']}\n{r['body'][:150]}...\n🔗 {r['href']}\n")
    except:
        pass
    return f"🔍 Results: {query}\n\n" + "\n".join(results) if results else "No results"

def make_pdf(text, title="Document"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, title, ln=True, align="C")
    pdf.ln(10)
    pdf.multi_cell(0, 7, text.encode('latin-1', 'replace').decode('latin-1'))
    filename = f"output_{datetime.now().strftime('%H%M%S')}.pdf"
    pdf.output(filename)
    return filename

# ============================================
# TELEGRAM COMMANDS
# ============================================

async def start(update, context):
    await update.message.reply_text("""
🤖 *AI BOT READY!*

*Commands:*
- Just send message to chat!

/research <topic> - Search web
/pdf <text> - Make PDF
/remind <time> <msg> - Set reminder
/remind every 1h <msg> - Recurring
/reminders - View all
/clear - Clear chat

*Example:*
/remind every 1h Eye compress!
""", parse_mode="Markdown")

async def chat(update, context):
    user_id = update.effective_user.id
    msg = update.message.text
    
    if user_id not in chats:
        chats[user_id] = []
    
    chats[user_id].append({"role": "user", "content": msg})
    
    await update.message.chat.send_action("typing")
    reply = ask_ai(msg, chats[user_id])
    
    chats[user_id].append({"role": "assistant", "content": reply})
    chats[user_id] = chats[user_id][-20:]
    
    if len(reply) > 4000:
        for i in range(0, len(reply), 4000):
            await update.message.reply_text(reply[i:i+4000])
    else:
        await update.message.reply_text(reply)

async def research(update, context):
    if not context.args:
        await update.message.reply_text("Usage: /research <topic>")
        return
    query = " ".join(context.args)
    await update.message.chat.send_action("typing")
    results = search_web(query)
    await update.message.reply_text(results[:4000])

async def pdf_cmd(update, context):
    if not context.args:
        await update.message.reply_text("Usage: /pdf <your text>")
        return
    text = " ".join(context.args)
    filename = make_pdf(text)
    with open(filename, 'rb') as f:
        await update.message.reply_document(f, caption="📄 Your PDF!")

async def remind(update, context):
    if len(context.args) < 2:
        await update.message.reply_text("Usage:\n/remind 14:30 Message\n/remind every 1h Message")
        return
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if user_id not in reminders_data:
        reminders_data[user_id] = []
    
    # Recurring reminder
    if context.args[0].lower() == "every":
        interval = context.args[1]
        message = " ".join(context.args[2:])
        
        if "h" in interval.lower():
            mins = int(interval.lower().replace("h", "")) * 60
        elif "m" in interval.lower():
            mins = int(interval.lower().replace("m", ""))
        else:
            mins = 60
        
        reminder = {
            "chat_id": chat_id,
            "message": message,
            "recurring": True,
            "interval_minutes": mins,
            "next_time": datetime.now() + timedelta(minutes=mins)
        }
        reminders_data[user_id].append(reminder)
        await update.message.reply_text(f"✅ *Recurring Reminder Set!*\n📝 {message}\n⏱ Every {mins} minutes", parse_mode="Markdown")
        return
    
    # One-time reminder
    time_str = context.args[0]
    message = " ".join(context.args[1:])
    
    try:
        hour, minute = map(int, time_str.split(":"))
        now = datetime.now()
        trigger = now.replace(hour=hour, minute=minute, second=0)
        if trigger <= now:
            trigger += timedelta(days=1)
        
        reminder = {
            "chat_id": chat_id,
            "message": message,
            "trigger_time": trigger,
            "recurring": False
        }
        reminders_data[user_id].append(reminder)
        await update.message.reply_text(f"✅ *Reminder Set!*\n📝 {message}\n📅 {trigger.strftime('%Y-%m-%d %H:%M')}", parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ Use format: 14:30")

async def view_reminders(update, context):
    user_id = update.effective_user.id
    user_reminders = reminders_data.get(user_id, [])
    
    if not user_reminders:
        await update.message.reply_text("📭 No reminders yet!")
        return
    
    text = "⏰ *Your Reminders:*\n\n"
    for i, r in enumerate(user_reminders, 1):
        if r.get("recurring"):
            text += f"{i}. 🔄 Every {r['interval_minutes']}min\n   📝 {r['message']}\n\n"
        else:
            text += f"{i}. 📅 {r['trigger_time'].strftime('%m/%d %H:%M')}\n   📝 {r['message']}\n\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def clear(update, context):
    chats[update.effective_user.id] = []
    await update.message.reply_text("✅ Chat cleared!")

# ============================================
# REMINDER CHECKER (runs in background)
# ============================================

async def check_reminders(app):
    """Check and send reminders"""
    now = datetime.now()
    
    for user_id, reminders in reminders_data.items():
        for i, r in enumerate(reminders):
            should_trigger = False
            
            if r.get("recurring"):
                if now >= r["next_time"]:
                    should_trigger = True
                    reminders[i]["next_time"] = now + timedelta(minutes=r["interval_minutes"])
            else:
                if "trigger_time" in r and r["trigger_time"] and now >= r["trigger_time"]:
                    should_trigger = True
                    reminders[i]["trigger_time"] = None
            
            if should_trigger:
                try:
                    await app.bot.send_message(
                        chat_id=r["chat_id"],
                        text=f"⏰ *REMINDER!*\n\n{r['message']}",
                        parse_mode="Markdown"
                    )
                except:
                    pass

def reminder_loop(app):
    """Background thread for reminders"""
    import asyncio
    while True:
        try:
            asyncio.run(check_reminders(app))
        except:
            pass
        time.sleep(30)

# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    # Check if keys exist
    if not TELEGRAM_TOKEN:
        print("❌ ERROR: TELEGRAM_BOT_TOKEN not set!")
        print("Set it as environment variable")
        exit(1)
    if not GROQ_API_KEY:
        print("❌ ERROR: GROQ_API_KEY not set!")
        print("Set it as environment variable")
        exit(1)
    
    print("=" * 40)
    print("🤖 AI BOT STARTING...")
    print("=" * 40)
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("research", research))
    app.add_handler(CommandHandler("pdf", pdf_cmd))
    app.add_handler(CommandHandler("remind", remind))
    app.add_handler(CommandHandler("reminders", view_reminders))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    
    # Start reminder checker
    reminder_thread = threading.Thread(target=reminder_loop, args=(app,), daemon=True)
    reminder_thread.start()
    
    print("✅ Bot is running!")
    print("📱 Go to Telegram and message your bot")
    print("=" * 40)
    
    app.run_polling()
