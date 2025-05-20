import requests
import matplotlib.pyplot as plt
import numpy as np
import os

POLYGON_API_KEY = os.getenv('POLYGON_API_KEY')

def fetch_polygon_price(symbol, polygon_api_key=POLYGON_API_KEY):
    url = f"https://api.polygon.io/v2/last/trade/{symbol.upper()}?apiKey={polygon_api_key}"
    resp = requests.get(url)
    data = resp.json()
    if 'results' in data:
        price = data['results']['price']
        print(f"Polygon price for {symbol}: {price}")
        return price
    else:
        print("Polygon API error:", data)
        return None

def fetch_polygon_ohlc(symbol, polygon_api_key=POLYGON_API_KEY, limit=30):
    # Fetch last N daily candles for charting (limit=30 by default)
    # Dates here are wide; Polygon returns latest first with sort=desc
    url = (
        f"https://api.polygon.io/v2/aggs/ticker/{symbol.upper()}/range/1/day/2024-01-01/2024-12-31"
        f"?adjusted=true&sort=desc&limit={limit}&apiKey={polygon_api_key}"
    )
    resp = requests.get(url)
    data = resp.json()
    if 'results' in data:
        candles = data['results']
        # Flip to ascending order for charting
        candles = candles[::-1]
        return candles
    else:
        print("Polygon OHLC API error:", data)
        return []

def calc_rsi(closes, period=14):
    closes = np.array(closes)
    deltas = np.diff(closes)
    seed = deltas[:period]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down != 0 else 0
    rsi = np.zeros_like(closes)
    rsi[:period] = 100. - 100. / (1. + rs)
    for i in range(period, len(closes)):
        delta = deltas[i - 1]
        if delta > 0:
            upval = delta
            downval = 0.
        else:
            upval = 0.
            downval = -delta
        up = (up * (period - 1) + upval) / period
        down = (down * (period - 1) + downval) / period
        rs = up / down if down != 0 else 0
        rsi[i] = 100. - 100. / (1. + rs)
    return rsi

def fetch_stock_data(symbol):
    candles = fetch_polygon_ohlc(symbol)
    if not candles or len(candles) < 15:
        print(f"Not enough candle data for {symbol}")
        return None, None
    closes = [c['c'] for c in candles]
    rsi = calc_rsi(closes)
    info = {
        "regularMarketPrice": closes[-1],
        "volume": candles[-1]['v']
    }
    # Emulate a DataFrame for charting (for matplotlib)
    class History:
        pass
    hist = History()
    hist.index = [c['t'] for c in candles]  # Timestamps (ms)
    hist.close = closes
    hist.rsi = rsi
    hist.volumes = [c['v'] for c in candles]
    hist._candles = candles
    return info, hist

def generate_chart(symbol, hist):
    import datetime
    timestamps = [datetime.datetime.fromtimestamp(t/1000) for t in hist.index]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6))
    ax1.plot(timestamps, hist.close, label="Close Price", color='blue')
    ax1.set_title(f"{symbol} - 30 Day")
    ax1.legend()
    ax1.grid(True)
    ax2.plot(timestamps, hist.rsi, label="RSI", color='purple')
    ax2.axhline(70, color='red', linestyle='--')
    ax2.axhline(30, color='green', linestyle='--')
    ax2.legend()
    ax2.grid(True)
    plt.tight_layout()
    filename = f"/tmp/{symbol}_chart.png"
    plt.savefig(filename)
    plt.close()
    return filename
