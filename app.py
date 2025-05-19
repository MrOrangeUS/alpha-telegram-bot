from flask import Flask, request
import requests
import yfinance as yf
import matplotlib.pyplot as plt
import openai
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import os

app = Flask(__name__)

# === CONFIG ===
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

openai.api_key = OPENAI_API_KEY

# === PAYPAL IPN + WELCOME DM ===
def verify_ipn(data):
    verify_url = "https://ipnpb.paypal.com/cgi-bin/webscr"
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    verify_data = {'cmd': '_notify-validate'}
    verify_data.update(data)
    response = requests.post(verify_url, data=verify_data, headers=headers)
    return response.text == "VERIFIED"

def send_welcome_dm(username):
    msg = """🚀 You’re in.

Welcome to *DAILY ALPHA* — my private signal channel.

✅ New plays drop every 4 hours  
✅ Turn on notifications  
✅ Tap the pinned post for the latest alpha

Link is yours — don’t share it.
Next move hits soon.

– @MrOrangeUS"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': f"@{username}", 'text': msg, 'parse_mode': 'Markdown'}
    requests.post(url, data=payload)

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
@app.route(f'/webhook/{TELEGRAM_BOT_TOKEN}', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    message = data.get("message", {})
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")

    if text == "/drop":
        run_alpha_drop()
        reply = "🚀 Alpha drop initiated manually!"
    else:
        reply = "Unknown command. Try /drop"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": reply
    }
    requests.post(url, json=payload)
    return "OK", 200
# === AI ANALYSIS + CHART GENERATION ===
def fetch_stock_data(symbol):
    stock = yf.Ticker(symbol)
    hist = stock.history(period="30d")
    if hist.empty:
        return None, None
    delta = hist['Close'].diff().dropna()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    hist['RSI'] = rsi
    return stock.info, hist

def generate_chart(symbol, hist):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6))
    ax1.plot(hist['Close'], label="Close Price", color='blue')
    ax2.plot(hist['RSI'], label="RSI", color='purple')
    ax2.axhline(70, color='red', linestyle='--')
    ax2.axhline(30, color='green', linestyle='--')
    ax1.set_title(f"{symbol} - 30 Day")
    plt.tight_layout()
    filename = f"{symbol}_chart.png"
    plt.savefig(filename)
    plt.close()
    return filename

def ask_chatgpt(symbol, info, hist):
    rsi_val = round(hist['RSI'].dropna().iloc[-1], 2)
    prompt = f"""You're an elite trading analyst. Based on the following:

Symbol: {symbol}
Current Price: {info.get('regularMarketPrice')}
RSI (14): {rsi_val}
Volume: {info.get('volume')}

Give a trade setup with:
- Entry
- Stop Loss
- Price Target
- Reasoning
- Risk/reward summary
"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message['content']

def send_telegram_post(symbol, analysis, chart_file):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    files = {'photo': open(chart_file, 'rb')}
    caption = f"📈 *ALPHA DROP – ${symbol}*\n\n{analysis}"
    data = {
        'chat_id': TELEGRAM_CHAT_ID,
        'caption': caption,
        'parse_mode': 'Markdown'
    }
    requests.post(url, files=files, data=data)

def run_alpha_drop():
    symbol = "XFOR"
    info, hist = fetch_stock_data(symbol)
    if info and hist is not None:
        chart = generate_chart(symbol, hist)
        analysis = ask_chatgpt(symbol, info, hist)
        send_telegram_post(symbol, analysis, chart)

# === SCHEDULED JOB ===
scheduler = BackgroundScheduler()
scheduler.add_job(run_alpha_drop, 'interval', hours=4)
scheduler.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
