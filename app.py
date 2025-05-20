from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
import os
import sys
from telegram import nova_joke

# --- Import functions from your modules ---
from stock import ask_chatgpt, fetch_stock_data, generate_chart
from telegram import send_welcome_dm
from paypal import verify_ipn

from dotenv import load_dotenv
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

app = Flask(__name__)

# ---- Alpha Drop ----
def run_alpha_drop(chat_id, telegram_token, openai_api_key):
    symbol = "XFOR"
    info, hist = fetch_stock_data(symbol)
    if info and hist is not None:
        chart = generate_chart(symbol, hist)
        analysis = ask_chatgpt(symbol, info, hist, openai_api_key)
        joke = nova_joke(openai_api_key)
        final_message = f"{analysis}\n\n🦾 Nova's joke: {joke}"
        send_telegram_post(symbol, final_message, chart, chat_id, telegram_token)

# ---- Telegram Message Handler ----
def send_telegram_post(symbol, analysis, chart_file, chat_id, telegram_token):
    url = f"https://api.telegram.org/bot{telegram_token}/sendPhoto"
    files = {'photo': open(chart_file, 'rb')}
    data = {
        'chat_id': chat_id,
        'caption': analysis,
        'parse_mode': 'Markdown'
    }
    requests.post(url, files=files, data=data)

# ---- Webhook Handler ----
def handle_webhook(data, telegram_token, openai_api_key):
    try:
        message = data.get("message") or data.get("channel_post", {})
        text = message.get("text", "").strip().lower()
        chat_id = message.get("chat", {}).get("id")
        print("📩 Text received:", text)
        print("📢 Chat ID:", chat_id)

        command = text.split()[0].split("@")[0]

        # Keyword scanning
        keywords = ["btc", "eth", "pump", "news", "ai", "alert", "xfor", "imnn"]
        keyword_found = next((kw for kw in keywords if kw in text), None)

        if command == "/drop":
            print("✅ Detected /drop")
            run_alpha_drop(chat_id, telegram_token, openai_api_key)
            reply = "🚀 Alpha drop initiated manually!"
        elif command == "/status":
            reply = "🤖 Bot is online and ready!"
        elif keyword_found:
            reply = f"👀 You mentioned *{keyword_found.upper()}* — want the latest update? Try /drop for fresh analysis."
        else:
            reply = "Unknown command. Try /drop"

        url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": reply,
            "parse_mode": "Markdown"
        }
        requests.post(url, json=payload)
        return "OK", 200
    except Exception as e:
        print("❌ Webhook error in handle_webhook:", e)
        return "Error", 500

# ---- Flask Routes ----
@app.route('/paypal-ipn', methods=['POST'])
def paypal_ipn():
    data = request.form.to_dict()
    if not verify_ipn(data):
        return "Invalid IPN", 400
    if data.get('payment_status') == "Completed" and data.get('mc_gross') == '97.00':
        username = data.get('custom')
        if username:
            send_welcome_dm(username)
    return "OK", 200

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    try:
        data = request.get_json()
        if not data:
            print("No JSON data in webhook")
            return "No data", 400
        result, status = handle_webhook(
            data,
            TELEGRAM_BOT_TOKEN,
            OPENAI_API_KEY
        )
        return result, status
    except Exception as e:
        print(f"Webhook route error: {e}")
        return "Server error", 500

# ---- Scheduler ----
def init_scheduler():
    try:
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            lambda: run_alpha_drop(TELEGRAM_CHAT_ID, TELEGRAM_BOT_TOKEN, OPENAI_API_KEY),
            'interval',
            hours=4,
            misfire_grace_time=300,
            id='alpha_drop'
        )
        scheduler.start()
        print("📅 Scheduler started, dropping alpha every 4 hours")
    except Exception as e:
        print(f"Scheduler init error: {e}")
        sys.exit(1)

# ---- Joke ----
def handle_webhook(data, bot_token, allowed_chat_id, openai_api_):
    # ... previous code ...
    command = text.split()[0].split("@")[0]
    if command == "/drop":
        # drop logic
        reply = "Alpha drop..."
    elif command == "/status":
        reply = "Bot is online!"
    elif command == "/joke":
        reply = nova_joke(openai_api_key)
    elif command == "/memesnipe":
        reply = nova_memesnipe(openai_api_key)
    elif keyword_found:
        reply = f"..."
    else:
        reply = "Unknown command. Try /drop or /memesnipe."
    # ... send reply code here ...

# ---- Start Everything ----
if __name__ == '__main__':
    init_scheduler()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
