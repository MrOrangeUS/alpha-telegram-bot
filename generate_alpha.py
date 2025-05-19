	import yfinance as yf
import matplotlib.pyplot as plt
import openai
import requests
from datetime import datetime

openai.api_key = "your-openai-api-key"

def fetch_stock_data(symbol):
    stock = yf.Ticker(symbol)
    hist = stock.history(period="30d")
    if hist.empty:
        return None, None

    # RSI
    delta = hist['Close'].diff().dropna()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    hist['RSI'] = rsi

    return stock.info, hist

def generate_chart(symbol, hist):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6))
    ax1.plot(hist['Close'], label="Price")
    ax2.plot(hist['RSI'], label="RSI", color='purple')
    ax2.axhline(70, color='red', linestyle='--')
    ax2.axhline(30, color='green', linestyle='--')
    ax1.set_title(f"{symbol} - 30d")
    plt.tight_layout()
    filename = f"{symbol}_chart.png"
    plt.savefig(filename)
    plt.close()
    return filename

def ask_chatgpt(symbol, info, hist):
    prompt = f"""
You're a professional market analyst. The stock {symbol} has the following recent data:
- Current price: ${info.get('regularMarketPrice')}
- Volume: {info.get('volume')}
- RSI (14): {round(hist['RSI'].iloc[-1], 2)}

Give a detailed technical analysis with:
- Entry point
- Stop loss
- Price target
- Why this setup works
- Risk management notes
"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response['choices'][0]['message']['content']

# === EXAMPLE USE ===
symbol = "XFOR"
info, hist = fetch_stock_data(symbol)
if info:
    chart_file = generate_chart(symbol, hist)
    analysis = ask_chatgpt(symbol, info, hist)
    print("=== AI Analysis ===")
    print(analysis)
    print("Chart saved as:", chart_file)
