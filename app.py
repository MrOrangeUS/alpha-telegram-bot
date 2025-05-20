from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import os
import sys
import requests

from stock import fetch_stock_data, generate_chart, ask_chatgpt
from memecoin import nova_memesnipe
from telegram import handle_telegram_command, nova_joke, get_finance_news, send_welcome_dm
from paypal import verify_ipn

# --- ENV VARIABLES ---
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

app = Flask(__name__)

# ---- Alpha Drop: Main Stock Signal + Joke ----
def run_alpha_drop(chat_id, telegram_token, openai_api_key):
    try:
        symbol = "XFOR"
        info, hist = fetch_stock_data(symbol)
        if info and hist is not None:
            chart = generate_chart(symbol, hist)
            analysis = ask_chatgpt(symbol, info, hist, openai_api_key)
            joke = nova_joke(openai_api_key)
            final_message = f"{analysis}\n\n🦾 Nova's joke: {joke}"
            send_telegram_post(symbol, final_message, chart, chat_id, telegram_token)
        else:
            print("No stock data available for drop!")
    except Exception as e:
        print("Error in run_alpha_drop:", e)


# ---- Telegram Photo Sender ----
def send_telegram_post(symbol, analysis, chart_file, chat_id, telegram_token):
    try:
        url = f"https://api.telegram.org/bot{telegram_token}/sendPhoto"
        files = {'photo': open(chart_file, 'rb')}
        data = {
            'chat_id': chat_id,
            'caption': analysis,
            'parse_mode': 'Markdown'
        }
        r = requests.post(url, files=files, data=data)
        print("Telegram photo response:", r.text)
    except Exception as e:
        print("Error in send_telegram_post:", e)

# ---- Webhook Handler ----
def handle_webhook(data, bot_token, allowed_chat_id, openai_api_key):
    message = data.get("message") or data.get("channel_post", {})
    text = message.get("text", "")

    if not text or not text.strip():
        return "🦾 I only understand text commands. Try /drop, /memesnipe, or /joke!", 200

    split_text = text.strip().split()
    if not split_text:
        return "🦾 No recognizable command. Try /drop, /memesnipe, or /joke!", 200

    command = split_text[0].split("@")[0].lower()
    chat_id = message.get("chat", {}).get("id")
    if command == "/drop":
        reply = "🚀 Alpha drop initiated manually!"
    elif command == "/joke":
        reply = nova_joke(openai_api_key) or "Nova's joke generator glitched."
    elif command == "/memesnipe":
        reply = nova_memesnipe(openai_api_key)
    elif command == "/news":
        reply = get_finance_news()    
# ...more commands...

# ...etc...

    reply = nova_joke(openai_api_key) or "Nova's joke generator glitched."


    # ...rest of your command handling...
      # Example keyword detection
    keywords = ["btc", "eth", "xfor", "doge", "pump", "ai"]
    keyword_found = next((kw for kw in keywords if kw in text.lower()), None)

    # Command logic
    if command == "/drop":
        run_alpha_drop(chat_id, bot_token, openai_api_key)
        reply = "🚀 Alpha drop initiated manually!"
    elif command == "/memesnipe":
        reply = nova_memesnipe(openai_api_key)
    elif command == "/joke":
        reply = nova_joke(openai_api_key)
    elif command == "/news":
        reply = get_finance_news()
    elif command == "/status":
        reply = "🤖 Nova Stratos is online and ready!"
    elif keyword_found:
        reply = f"👀 You mentioned *{keyword_found.upper()}* — want the latest update? Try /drop or /memesnipe."
    else:
        reply = "Unknown command. Try /drop, /memesnipe, /joke, or /news."

    # Send reply (text only)
    import requests
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": reply,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)
    return "OK", 200

# ---- PayPal IPN Handler ----
@app.route('/paypal-ipn', methods=['POST'])
def paypal_ipn():
    data = request.form.to_dict()
    if not verify_ipn(data):
        return "Invalid IPN", 400
    if data.get('payment_status') == "Completed" and data.get('mc_gross') == '97.00':
        username = data.get('custom')
        if username:
            send_welcome_dm(username, TELEGRAM_BOT_TOKEN)
    return "OK", 200

# ---- Telegram Webhook ----
@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    try:
        data = request.get_json()
        if not data:
            print("No JSON data in webhook")
            return "No data", 400
        return handle_webhook(data, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, OPENAI_API_KEY)
    except Exception as e:
        import traceback
        print(f"Webhook route error: {e}")
        traceback.print_exc()  # <--- Add this line for full stack trace!
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

# ---- Start Everything ----
if __name__ == '__main__':
    init_scheduler()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
