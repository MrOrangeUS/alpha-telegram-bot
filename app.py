from flask import Flask, request
from telegram import handle_webhook, run_alpha_drop
from paypal import verify_ipn, send_welcome_dm
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import logging
import os
import sys
import os
os.makedirs('logs', exist_ok=True)

# Initialize Flask app
app = Flask(__name__)

# Load environment variables
load_dotenv()

# Config
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Validate env vars
required_vars = {
    'TELEGRAM_BOT_TOKEN': TELEGRAM_BOT_TOKEN,
    'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    'OPENAI_API_KEY': OPENAI_API_KEY
}
missing_vars = [key for key, value in required_vars.items() if not value]
if missing_vars:
    print(f"🚨 Missing environment variables: {', '.join(missing_vars)}")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Log startup
logger.info("🚀 Bot starting up... Ready to drop alpha and chaos!")

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    """Handle Telegram webhook for commands like /drop."""
    try:
        data = request.get_json()
        if not data:
            logger.warning("No JSON data in webhook")
            return "No data", 400
        result, status = handle_webhook(data, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        return result, status
    except Exception as e:
        logger.error(f"Webhook route error: {e}")
        return "Server error", 500

@app.route('/paypal-ipn', methods=['POST'])
def paypal_ipn():
    """Process PayPal IPN for new subscribers."""
    try:
        data = request.form.to_dict()
        if not verify_ipn(data):
            logger.warning("Invalid IPN received")
            return "Invalid IPN", 400
        if data.get('payment_status') == "Completed" and data.get('mc_gross') == '97.00':
            username = data.get('custom', '').strip()
            if username and username.isalnum():  # Basic sanitization
                send_welcome_dm(username, TELEGRAM_BOT_TOKEN)
                logger.info(f"Processed IPN for @{username}")
            else:
                logger.warning(f"Invalid username in IPN: {username}")
        return "OK", 200
    except Exception as e:
        logger.error(f"PayPal IPN error: {e}")
        return "Server error", 500

@app.route('/test-drop', methods=['GET'])
def test_drop():
    """Test alpha drop locally."""
    try:
        logger.info("Initiating test alpha drop")
        success = run_alpha_drop(TELEGRAM_CHAT_ID, TELEGRAM_BOT_TOKEN)
        return "Test drop initiated" if success else "Test drop failed", 200
    except Exception as e:
        logger.error(f"Test drop error: {e}")
        return "Test drop error", 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return "Bot is alive and chaotic!", 200

def init_scheduler():
    """Initialize background scheduler for alpha drops."""
    try:
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            lambda: run_alpha_drop(TELEGRAM_CHAT_ID, TELEGRAM_BOT_TOKEN),
            'interval',
            hours=4,
            misfire_grace_time=300,
            id='alpha_drop'
        )
        scheduler.start()
        logger.info("📅 Scheduler started, dropping alpha every 4 hours")
    except Exception as e:
        logger.error(f"Scheduler init error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    # Create logs directory if missing
    os.makedirs('logs', exist_ok=True)
    # Initialize scheduler
    init_scheduler()
    # Run Flask app
    logger.info("🌌 Flask app launching on port 5000...")
    app.run(host='0.0.0.0', port=5000, debug=False)
