import requests
import matplotlib.pyplot as plt
import numpy as np
import openai
import os
import tempfile
import logging
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/stock.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

POLYGON_API_KEY = os.getenv('POLYGON_API_KEY')

def fetch_polygon_price(symbol, polygon_api_key=POLYGON_API_KEY):
    try:
        if not polygon_api_key:
            logger.error("Polygon API key not configured")
            return None
            
        url = f"https://api.polygon.io/v2/last/trade/{symbol.upper()}?apiKey={polygon_api_key}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        
        data = resp.json()
        if 'results' in data:
            price = data['results']['price']
            logger.info(f"Fetched price for {symbol}: {price}")
            return price
        else:
            logger.error(f"Polygon API error: {data.get('error', 'Unknown error')}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error fetching price for {symbol}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching price for {symbol}: {str(e)}")
        return None

def fetch_polygon_ohlc(symbol, polygon_api_key=POLYGON_API_KEY, limit=30):
    try:
        if not polygon_api_key:
            logger.error("Polygon API key not configured")
            return []
            
        # Calculate date range dynamically
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)  # Get 90 days of data
        
        url = (
            f"https://api.polygon.io/v2/aggs/ticker/{symbol.upper()}/range/1/day/"
            f"{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
            f"?adjusted=true&sort=desc&limit={limit}&apiKey={polygon_api_key}"
        )
        
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        
        data = resp.json()
        if 'results' in data:
            candles = data['results'][::-1]  # oldest to newest
            logger.info(f"Fetched {len(candles)} candles for {symbol}")
            return candles
        else:
            logger.error(f"Polygon OHLC API error: {data.get('error', 'Unknown error')}")
            return []
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error fetching OHLC for {symbol}: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching OHLC for {symbol}: {str(e)}")
        return []

def calc_rsi(closes, period=14):
    try:
        closes = np.array(closes)
        deltas = np.diff(closes)
        
        if len(deltas) < period:
            logger.error(f"Not enough data points for RSI calculation. Need {period}, got {len(deltas)}")
            return np.zeros_like(closes)
            
        seed = deltas[:period]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / down if down != 0 else float('inf')
        
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
            rs = up / down if down != 0 else float('inf')
            rsi[i] = 100. - 100. / (1. + rs)
            
        return rsi
        
    except Exception as e:
        logger.error(f"Error calculating RSI: {str(e)}")
        return np.zeros_like(closes)

def calculate_technical_indicators(hist):
    """Calculate additional technical indicators."""
    try:
        closes = np.array(hist.close)
        volumes = np.array(hist.volumes)
        
        # Calculate moving averages
        ma20 = np.convolve(closes, np.ones(20)/20, mode='valid')
        ma50 = np.convolve(closes, np.ones(50)/50, mode='valid')
        
        # Calculate volume SMA
        vol_sma = np.convolve(volumes, np.ones(20)/20, mode='valid')
        
        # Calculate Bollinger Bands
        period = 20
        std = np.std(closes[-period:])
        middle_band = ma20[-1]
        upper_band = middle_band + (std * 2)
        lower_band = middle_band - (std * 2)
        
        # Current price position
        current_price = closes[-1]
        price_vs_ma20 = (current_price / ma20[-1] - 1) * 100 if len(ma20) > 0 else 0
        price_vs_ma50 = (current_price / ma50[-1] - 1) * 100 if len(ma50) > 0 else 0
        
        # Volume analysis
        avg_volume = np.mean(volumes[-20:])
        current_volume = volumes[-1]
        volume_ratio = current_volume / avg_volume
        
        return {
            'ma20': ma20[-1] if len(ma20) > 0 else None,
            'ma50': ma50[-1] if len(ma50) > 0 else None,
            'upper_band': upper_band,
            'lower_band': lower_band,
            'price_vs_ma20': price_vs_ma20,
            'price_vs_ma50': price_vs_ma50,
            'volume_ratio': volume_ratio
        }
        
    except Exception as e:
        logger.error(f"Error calculating technical indicators: {str(e)}")
        return {}

def fetch_stock_data(symbol):
    try:
        logger.info(f"Fetching stock data for {symbol}")
        
        candles = fetch_polygon_ohlc(symbol)
        if not candles or len(candles) < 15:
            logger.error(f"Not enough candle data for {symbol}")
            return None, None
            
        closes = [c['c'] for c in candles]
        volumes = [c['v'] for c in candles]
        
        rsi = calc_rsi(closes)
        
        class History:
            pass
            
        hist = History()
        hist.index = [c['t'] for c in candles]  # Timestamps (ms)
        hist.close = closes
        hist.rsi = rsi
        hist.volumes = volumes
        hist._candles = candles
        
        # Calculate additional technical indicators
        tech_indicators = calculate_technical_indicators(hist)
        
        info = {
            "regularMarketPrice": closes[-1],
            "volume": volumes[-1],
            "technical_indicators": tech_indicators
        }
        
        logger.info(f"Successfully fetched and processed data for {symbol}")
        return info, hist
        
    except Exception as e:
        logger.error(f"Error in fetch_stock_data for {symbol}: {str(e)}")
        return None, None

def generate_chart(symbol, hist):
    try:
        logger.info(f"Generating chart for {symbol}")
        
        timestamps = [datetime.fromtimestamp(t/1000) for t in hist.index]
        
        # Create figure with subplots
        fig = plt.figure(figsize=(12, 8))
        gs = plt.GridSpec(3, 1, height_ratios=[2, 1, 1])
        
        # Price and MA subplot
        ax1 = fig.add_subplot(gs[0])
        ax1.plot(timestamps, hist.close, label="Price", color='blue')
        
        # Add moving averages if available
        closes = np.array(hist.close)
        if len(closes) >= 20:
            ma20 = np.convolve(closes, np.ones(20)/20, mode='valid')
            ma50 = np.convolve(closes, np.ones(50)/50, mode='valid')
            ax1.plot(timestamps[-len(ma20):], ma20, label="MA20", color='orange', linestyle='--')
            if len(ma50) > 0:
                ax1.plot(timestamps[-len(ma50):], ma50, label="MA50", color='red', linestyle='--')
        
        ax1.set_title(f"{symbol} - Technical Analysis")
        ax1.legend()
        ax1.grid(True)
        
        # Volume subplot
        ax2 = fig.add_subplot(gs[1])
        ax2.bar(timestamps, hist.volumes, label="Volume", color='gray', alpha=0.5)
        ax2.legend()
        ax2.grid(True)
        
        # RSI subplot
        ax3 = fig.add_subplot(gs[2])
        ax3.plot(timestamps, hist.rsi, label="RSI", color='purple')
        ax3.axhline(70, color='red', linestyle='--')
        ax3.axhline(30, color='green', linestyle='--')
        ax3.legend()
        ax3.grid(True)
        
        plt.tight_layout()
        
        # Save chart
        temp_dir = tempfile.gettempdir()
        filename = os.path.join(temp_dir, f"{symbol}_chart.png")
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()
        
        if not os.path.exists(filename):
            raise Exception(f"Failed to save chart to {filename}")
            
        logger.info(f"Successfully generated chart for {symbol}")
        return filename
        
    except Exception as e:
        logger.error(f"Error generating chart for {symbol}: {str(e)}")
        return None

# === GPT-Powered Analysis as Nova Stratos ===
def ask_chatgpt(symbol, info, hist, openai_api_key):
    try:
        if not openai_api_key:
            logger.error("OpenAI API key not configured")
            return "⚠️ AI analysis service not configured"

        openai.api_key = openai_api_key
        rsi_val = round(hist.rsi[-1], 2)
        tech = info.get('technical_indicators', {})
        
        # Prepare technical analysis summary
        technical_summary = f"""
Current Price: ${info['regularMarketPrice']:.2f}
RSI (14): {rsi_val:.2f}
Volume: {info['volume']:,} (x{tech.get('volume_ratio', 0):.2f} avg)
MA20: ${tech.get('ma20', 0):.2f} ({tech.get('price_vs_ma20', 0):.1f}% from price)
MA50: ${tech.get('ma50', 0):.2f} ({tech.get('price_vs_ma50', 0):.1f}% from price)
Bollinger Bands:
- Upper: ${tech.get('upper_band', 0):.2f}
- Lower: ${tech.get('lower_band', 0):.2f}
"""
        
        prompt = f"""Act as Nova Stratos, an AI quant analyst built to detect high-probability breakout trades and market inefficiencies.
Always speak with precision, directness, and futuristic confidence. Your audience includes serious traders, but also some who want to learn your logic.

Analyze this opportunity:
Symbol: {symbol}
{technical_summary}

1. Clearly explain in 2-3 sentences what makes this setup stand out right now.  
2. Return a trading plan with:
    - Nova's Entry
    - Nova's Stop Loss
    - Nova's Target
3. Explain *why* (including key technical patterns, unusual price/volume behavior, or recent news/sentiment)
4. End with a risk management tip and a one-sentence summary as if you're teaching a newer trader.
5. Label this as generated by Nova Stratos at the end.
"""

        logger.info(f"Requesting analysis for {symbol}")
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are Nova Stratos, an AI quant analyst specializing in technical analysis and breakout detection."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=750
        )
        
        if not response.choices:
            logger.error("No response from OpenAI API")
            return "Error: Could not generate analysis"
            
        logger.info(f"Successfully generated analysis for {symbol}")
        return response.choices[0].message.content

    except openai.error.AuthenticationError:
        logger.error("OpenAI API authentication failed")
        return "⚠️ AI service authentication failed"
    except openai.error.APIError as e:
        logger.error(f"OpenAI API error: {str(e)}")
        return "⚠️ AI service temporarily unavailable"
    except Exception as e:
        logger.error(f"Unexpected error in ask_chatgpt: {str(e)}")
        return "⚠️ Could not complete stock analysis"
