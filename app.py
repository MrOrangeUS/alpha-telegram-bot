from flask import Flask, request
from paypal import verify_ipn
from telegram import send_welcome_dm
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import logging
import os
import sys
from flask import Flask
app = Flask(__name__)


# ... existing config/loading code ...

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    try:
        data = request.get_json()
        if not data:
            logger.warning("No JSON data in webhook")
            return "No data", 400
        # PASS OPENAI_API_KEY HERE
        result, status = handle_webhook(
            data,
            TELEGRAM_BOT_TOKEN,
            TELEGRAM_CHAT_ID,
            OPENAI_API_KEY
        )
        return result, status
    except Exception as e:
        logger.error(f"Webhook route error: {e}")
        return "Server error", 500

def init_scheduler():
    try:
        scheduler = BackgroundScheduler()
        # PASS OPENAI_API_KEY HERE TOO!
        scheduler.add_job(
            lambda: run_alpha_drop(TELEGRAM_CHAT_ID, TELEGRAM_BOT_TOKEN, OPENAI_API_KEY),
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
