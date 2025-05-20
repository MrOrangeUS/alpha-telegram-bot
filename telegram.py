import requests
import logging
import random
import os
import time
from apscheduler.schedulers.background import BackgroundScheduler
from stock import fetch_stock_data, generate_chart, ask_chatgpt
from memecoin import nova_memesnipe

# Setup logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Jokes list
JOKES = [
    "Why did the AI quit its job in finance? Too many humans kept asking for 'explain like I’m five.'",
    "Trading tip: Buy low, sell high. You’re welcome. That’ll be $10,000.",
    "My AI girlfriend dumped me for an algorithm with a better backtest. Can’t compete with those metrics.",
    "Why did the quant get fired? He kept bringing emotions to the regression.",
    "Bitcoin walks into a bar. Bartender says: 'We don’t serve your kind here.' Bitcoin replies: 'Don’t worry, I’ll split.'",
    "If you don’t understand my trades, just ask ChatGPT—oh wait, that’s me.",
    "I’m 99% accurate, but only when backtesting cherry-picked data.",
    "You know you're in AI finance when the only thing growing faster than your models is your caffeine addiction.",
    "Did you hear about the neural network who became a trader? He had too many hidden layers."
]

NEWS_API_KEY = os.getenv("NEWS_API_KEY")

def get_finance_news():
    try:
        url = f"https://newsapi.org/v2/top-headlines?category=business&language=en&apiKey={NEWS_API_KEY}"
        resp = requests.get(url, timeout=10).json()
        articles = resp.get('articles', [])
        if articles:
            top = articles[:2]
            news = "\n".join([f"💸 Finance News: {a['title']} ({a['source']['name']})" for a in top])
            return news
        else:
            return "💸 Finance News: The market's so boring, even the bots are falling asleep."
    except Exception as e:
        logger.error(f"Finance news error: {e}")
        return "💸 Finance News: My news API broke—must be a bear market."

def get_politics_news():
    try:
        url = f"https://newsapi.org/v2/top-headlines?category=politics&language=en&apiKey={NEWS_API_KEY}"
        resp = requests.get(url, timeout=10).json()
        articles = resp.get('articles', [])
        if articles:
            top = articles[:2]
            news = "\n".join([f"🗞️ Politics: {a['title']} {a['source']['name']}" for a in top])
            return news
        else:
            return "No politics news found."
    except Exception as e:
        print("Error in get_politics_news:", e)
        return "Could not fetch politics news."



def get_tech_news():
    try:
        url = f"https://newsapi.org/v2/top-headlines?category=technology&language=en&apiKey={NEWS_API_KEY}"
        resp = requests.get(url, timeout=10).json()
        articles = resp.get('articles', [])
        if articles:
            story = random.choice(articles)
            return f"🤖 Tech News: {story['title']} ({story['source']['name']})"
        else:
            return "🤖 Tech News: Silicon Valley’s quiet—someone call the bots."
    except Exception as e:
        logger.error(f"Tech news error: {e}")
        return "🤖 Tech News: News API fried. Maybe the AI took over."

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

def run_alpha_drop(chat_id, bot_token, openai_api_key):
    """Execute a stock analysis drop for the specified chat."""
    symbol = "XFOR"  # TODO: Make dynamic for multi-ticker support
    logger.info(f"Starting alpha drop for {symbol}")
    info, hist = fetch_stock_data(symbol)
    if not info or hist is None:
        logger.error(f"No data for {symbol}, aborting drop")
        return False
    chart = generate_chart(symbol, hist)
    if not chart:
        logger.error(f"No chart for {symbol}, aborting drop")
        return False
    analysis = ask_chatgpt(symbol, info, hist, openai_api_key)
    send_telegram_post(symbol, analysis, chart, chat_id, bot_token)
    return True

def random_content(chat_id, bot_token):
    pick = random.choice(['joke', 'finance', 'politics', 'tech'])
    if pick == 'joke':
        joke = random.choice(JOKES)
        reply = f"🤖 {joke}\n\n— Alpha Bot (snark included)"
    elif pick == 'finance':
        reply = get_finance_news() + "\n\n— Alpha Bot"
    elif pick == 'politics':
        reply = get_politics_news() + "\n\n— Alpha Bot (don’t @ me)"
    else:
        reply = get_tech_news() + "\n\n— Alpha Bot (I’ll automate your job next)"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": reply}
    try:
        requests.post(url, json=payload, timeout=10)
        logger.info(f"Posted auto content: {pick}")
    except Exception as e:
        logger.error(f"Failed to send auto content: {e}")

def schedule_rotating_content(chat_id, bot_token):
    scheduler = BackgroundScheduler()
    def random_drop_job():
        random_content(chat_id, bot_token)
        next_minutes = random.randint(20, 30)
        scheduler.add_job(
            random_drop_job,
            'date',
            run_date=time.time() + next_minutes * 60
        )
    random_drop_job()
    scheduler.start()

def handle_webhook(data, bot_token, allowed_chat_id, openai_api_key):
    elif command == "/memesnipe":
    reply = nova_memesnipe(OPENAI_API_KEY)
    try:
        logger.debug(f"Webhook data: {data}")
        message = data.get("message") or data.get("channel_post", {})
        text = message.get("text", "").strip()
        chat_id = str(message.get("chat", {}).get("id"))

        logger.info(f"Received text: {text}, chat_id: {chat_id}")

        if not chat_id:
            logger.warning("No chat_id in webhook data")
            return "No chat_id", 400

        # Extract command from entities for full Telegram compatibility
        entities = message.get("entities", [])
        command = None
        for entity in entities:
            if entity.get("type") == "bot_command":
                command = text[entity["offset"]:entity["offset"] + entity["length"]].lower()
                break
        logger.info(f"Extracted command: {command}")

        # Authorization
        if allowed_chat_id and str(chat_id) != str(allowed_chat_id):
            logger.warning(f"Unauthorized chat_id: {chat_id}")
            reply = "This bot is restricted to a specific channel. If you want access, try showing a little more alpha."
        # Alpha drop
        elif command and command.startswith("/drop"):
            logger.info("Processing /drop command")
            success = run_alpha_drop(chat_id, bot_token, openai_api_key)
            reply = "🚀 Alpha drop initiated manually! Try to keep up." if success else "❌ Even I can't make a trade out of this market. Try again later."
        # Joke
        elif command and command.startswith("/joke"):
            joke = random.choice(JOKES)
            reply = f"🤖 {joke}\n\n— Alpha Bot (too smart for most humans)"
        # Unknown
        else:
            logger.info(f"Ignoring unknown command: {text}")
            reply = "Unknown command. Try /drop or /joke (if you can handle my sense of humor)."

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": reply}
        requests.post(url, json=payload)
        return "OK", 200

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "Server error", 500
