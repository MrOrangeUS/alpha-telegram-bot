from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import os
import sys
import requests
import logging
import time
from functools import wraps
from datetime import datetime

from stock import fetch_stock_data, generate_chart, ask_chatgpt
from memecoin import nova_memesnipe
from telegram import handle_telegram_command, nova_joke, get_finance_news, send_welcome_dm
from paypal import verify_ipn

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Rate Limiting ---
class RateLimit:
    def __init__(self, max_requests=30, window=60):  # 30 requests per minute
        self.max_requests = max_requests
        self.window = window
        self.requests = {}
        
    def is_allowed(self, key):
        now = time.time()
        self.cleanup(now)
        
        if key not in self.requests:
            self.requests[key] = []
            
        self.requests[key].append(now)
        return len(self.requests[key]) <= self.max_requests
        
    def cleanup(self, now):
        for key in list(self.requests.keys()):
            self.requests[key] = [t for t in self.requests[key] if t > now - self.window]
            if not self.requests[key]:
                del self.requests[key]

rate_limiter = RateLimit()

def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not rate_limiter.is_allowed(request.remote_addr):
            logger.warning(f"Rate limit exceeded for IP: {request.remote_addr}")
            return "Rate limit exceeded", 429
        return f(*args, **kwargs)
    return decorated_function

# --- ENV VARIABLES ---
load_dotenv()

# Required environment variables
REQUIRED_ENV_VARS = {
    'TELEGRAM_BOT_TOKEN': 'Telegram bot token for sending messages',
    'TELEGRAM_CHAT_ID': 'Telegram chat ID for the channel',
    'OPENAI_API_KEY': 'OpenAI API key for GPT-4 interactions',
    'POLYGON_API_KEY': 'Polygon.io API key for stock data',
    'NEWS_API_KEY': 'NewsAPI key for finance news'
}

# Validate required environment variables
missing_vars = []
for var, description in REQUIRED_ENV_VARS.items():
    if not os.getenv(var):
        missing_vars.append(f"{var} ({description})")

if missing_vars:
    logger.error("Missing required environment variables:")
    for var in missing_vars:
        logger.error(f"- {var}")
    sys.exit(1)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

app = Flask(__name__)

# ---- Alpha Drop: Main Stock Signal + Joke ----
def run_alpha_drop(chat_id, telegram_token, openai_api_key):
    try:
        symbol = "XFOR"
        logger.info(f"Starting alpha drop for {symbol}")
        
        info, hist = fetch_stock_data(symbol)
        if info and hist is not None:
            chart = generate_chart(symbol, hist)
            if not chart:
                logger.error("Failed to generate chart")
                return
                
            analysis = ask_chatgpt(symbol, info, hist, openai_api_key)
            joke = nova_joke(openai_api_key)
            final_message = f"{analysis}\n\n🦾 Nova's joke: {joke}"
            
            send_telegram_post(symbol, final_message, chart, chat_id, telegram_token)
            logger.info(f"Successfully completed alpha drop for {symbol}")
        else:
            logger.error(f"No stock data available for {symbol}")
    except Exception as e:
        logger.error(f"Error in run_alpha_drop: {str(e)}", exc_info=True)

# ---- Telegram Photo Sender ----
def send_telegram_post(symbol, analysis, chart_file, chat_id, telegram_token):
    try:
        url = f"https://api.telegram.org/bot{telegram_token}/sendPhoto"
        
        # Verify file exists and is readable
        if not os.path.exists(chart_file):
            logger.error(f"Chart file not found: {chart_file}")
            return
            
        if not os.access(chart_file, os.R_OK):
            logger.error(f"Chart file not readable: {chart_file}")
            return
            
        with open(chart_file, 'rb') as f:
            files = {'photo': f}
            data = {
                'chat_id': chat_id,
                'caption': analysis,
                'parse_mode': 'Markdown'
            }
            response = requests.post(url, files=files, data=data)
            response.raise_for_status()
            
            logger.info(f"Successfully sent Telegram post for {symbol}")
            
            # Cleanup the chart file
            try:
                os.remove(chart_file)
                logger.debug(f"Cleaned up chart file: {chart_file}")
                
                # Clean up old chart files
                charts_dir = os.path.dirname(chart_file)
                current_time = time.time()
                for old_file in os.listdir(charts_dir):
                    file_path = os.path.join(charts_dir, old_file)
                    # Remove files older than 1 hour
                    if os.path.isfile(file_path) and current_time - os.path.getmtime(file_path) > 3600:
                        try:
                            os.remove(file_path)
                            logger.debug(f"Cleaned up old chart file: {file_path}")
                        except Exception as e:
                            logger.warning(f"Failed to cleanup old chart file {file_path}: {str(e)}")
            except Exception as e:
                logger.warning(f"Failed to cleanup chart file: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error in send_telegram_post: {str(e)}", exc_info=True)

# ---- Webhook Handler ----
def handle_webhook(data, bot_token, allowed_chat_id, openai_api_key):
    try:
        message = data.get("message") or data.get("channel_post", {})
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        username = message.get("from", {}).get("username", "unknown")

        logger.info(f"Received command '{text}' from @{username}")

        if not text or not text.strip():
            return "🦾 I only understand text commands. Try /drop, /memesnipe, or /joke!", 200

        split_text = text.strip().split()
        if not split_text:
            return "🦾 No recognizable command. Try /drop, /memesnipe, or /joke!", 200

        command = split_text[0].split("@")[0].lower()
        
        # Keyword detection
        keywords = ["btc", "eth", "xfor", "doge", "pump", "ai"]
        keyword_found = next((kw for kw in keywords if kw in text.lower()), None)

        # Command logic
        start_time = time.time()
        try:
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
        finally:
            duration = time.time() - start_time
            logger.info(f"Command '{command}' processed in {duration:.2f}s")

        # Send reply
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": reply,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return "OK", 200

    except Exception as e:
        logger.error(f"Webhook handler error: {str(e)}", exc_info=True)
        return "Server error", 500

# ---- PayPal IPN Handler ----
@app.route('/paypal-ipn', methods=['POST'])
@rate_limit
def paypal_ipn():
    try:
        data = request.form.to_dict()
        logger.info("Received PayPal IPN")
        
        if not verify_ipn(data):
            logger.warning("Invalid IPN received")
            return "Invalid IPN", 400
            
        if data.get('payment_status') == "Completed" and data.get('mc_gross') == '97.00':
            username = data.get('custom')
            if username:
                logger.info(f"Processing completed payment for @{username}")
                send_welcome_dm(username, TELEGRAM_BOT_TOKEN)
                logger.info(f"Welcome message sent to @{username}")
            else:
                logger.warning("Completed payment but no username provided")
        else:
            logger.info("Ignored non-matching IPN")
            
        return "OK", 200
    except Exception as e:
        logger.error(f"PayPal IPN error: {str(e)}", exc_info=True)
        return "Server error", 500

# ---- Telegram Webhook ----
@app.route('/webhook', methods=['POST'])
@rate_limit
def telegram_webhook():
    try:
        data = request.get_json()
        if not data:
            logger.warning("No JSON data in webhook")
            return "No data", 400
        return handle_webhook(data, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, OPENAI_API_KEY)
    except Exception as e:
        logger.error(f"Telegram webhook error: {str(e)}", exc_info=True)
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
            id='alpha_drop',
            next_run_time=datetime.now()  # Run immediately on startup
        )
        scheduler.start()
        logger.info("Scheduler started, dropping alpha every 4 hours")
    except Exception as e:
        logger.error(f"Scheduler initialization error: {str(e)}", exc_info=True)
        sys.exit(1)

# ---- Start Everything ----
if __name__ == '__main__':
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Initialize scheduler
    init_scheduler()
    
    # Start Flask app
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port)
