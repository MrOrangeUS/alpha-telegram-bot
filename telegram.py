import requests
import logging
from stock import fetch_stock_data, generate_chart, ask_chatgpt

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def send_welcome_dm(username, bot_token):
    """Send a welcome DM to a new subscriber."""
    msg = """🚀 You’re in.

Welcome to *DAILY ALPHA* — my private signal channel.

✅ New plays drop every 4 hours  
✅ Turn on notifications  
✅ Tap the pinned post for the latest alpha

Link is yours — don’t share it.
Next move hits soon.

– @MrOrangeUS"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {'chat_id': f"@{username}", 'text': msg, 'parse_mode': 'Markdown'}
    try:
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Sent welcome DM to @{username}")
    except Exception as e:
        logger.error(f"Failed to send DM to @{username}: {e}")

def send_telegram_post(symbol, analysis, chart_file, chat_id, bot_token):
    """Post stock analysis with chart to Telegram channel."""
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    try:
        with open(chart_file, 'rb') as f:
            files = {'photo': f}
            caption = f"📈 *ALPHA DROP – ${symbol}*\n\n{analysis}"
            data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'Markdown'}
            response = requests.post(url, files=files, data=data, timeout=10)
            response.raise_for_status()
            logger.info(f"Posted alpha for {symbol} to chat {chat_id}")
    except Exception as e:
        logger.error(f"Failed to post to Telegram for {symbol}: {e}")
    finally:
        if chart_file and os.path.exists(chart_file):
            os.remove(chart_file)
            logger.info(f"Deleted chart file: {chart_file}")

def run_alpha_drop(chat_id, bot_token):
    """Execute a stock analysis drop for the specified chat."""
    symbol = "XFOR"  # TODO: Replace with dynamic symbol selection
    logger.info(f"Starting alpha drop for {symbol}")
    info, hist = fetch_stock_data(symbol)
    if not info or hist is None:
        logger.error(f"No data for {symbol}, aborting drop")
        return False
    chart = generate_chart(symbol, hist)
    if not chart:
        logger.error(f"No chart for {symbol}, aborting drop")
        return False
    analysis = ask_chatgpt(symbol, info, hist)
    send_telegram_post(symbol, analysis, chart, chat_id, bot_token)
    return True

def handle_webhook(data, bot_token, allowed_chat_id):
    """Process Telegram webhook data and handle commands."""
    try:
        logger.debug(f"Webhook data: {data}")
        message = data.get("message") or data.get("channel_post", {})
        text = message.get("text", "").strip().lower()
        chat_id = message.get("chat", {}).get("id")

        logger.info(f"Received text: {text}, chat_id: {chat_id}")

        if not chat_id:
            logger.warning("No chat_id in webhook data")
            return "No chat_id", 400

        if str(chat_id) != allowed_chat_id:
            logger.warning(f"Unauthorized chat_id: {chat_id}")
            reply = "This bot is restricted to a specific channel."
        elif text.startswith("/drop"):
            logger.info("Processing /drop command")
            success = run_alpha_drop(chat_id, bot_token)
            reply = "🚀 Alpha drop initiated manually!" if success else "❌ Failed to drop alpha. Try again later."
        else:
            logger.info(f"Ignoring unknown command: {text}")
            reply = "Unknown command. Try /drop"

        url = f"https://api.telegram.org/@aiagentalphacalls_bot
