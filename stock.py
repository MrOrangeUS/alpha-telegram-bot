import yfinance as yf
import matplotlib.pyplot as plt
import openai
import logging
import tempfile
import os

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

def fetch_stock_data(symbol):
    """Fetch 30-day stock data and calculate RSI."""
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="30d", interval="1d")
        if hist.empty:
            logger.warning(f"No data for {symbol}")
            return None, None
        # Calculate RSI (14-period)
        delta = hist['Close'].diff().dropna()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
        rs = gain / loss
        hist['RSI'] = 100 - (100 / (1 + rs))
        logger.info(f"Fetched stock data for {symbol}")
        return stock.info, hist
    except Exception as e:
        logger.error(f"Failed to fetch stock data for {symbol}: {e}")
        return None, None

def generate_chart(symbol, hist):
    """Generate a price + RSI chart, save to temp file."""
    try:
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
            ax1.plot(hist.index, hist['Close'], label="Close Price", color='blue', linewidth=2)
            ax1.set_title(f"{symbol} - 30 Day Price & RSI", fontsize=12)
            ax1.set_ylabel("Price (USD)", fontsize=10)
            ax1.legend(loc='upper left')
            ax1.grid(True, linestyle='--', alpha=0.7)
            ax2.plot(hist.index, hist['RSI'], label="RSI (14)", color='purple', linewidth=2)
            ax2.axhline(70, color='red', linestyle='--', alpha=0.8)
            ax2.axhline(30, color='green', linestyle='--', alpha=0.8)
            ax2.set_ylabel("RSI", fontsize=10)
            ax2.legend(loc='upper left')
            ax2.grid(True, linestyle='--', alpha=0.7)
            plt.tight_layout()
            plt.savefig(tmp.name, dpi=150, bbox_inches='tight')
            plt.close(fig)
            logger.info(f"Generated chart for {symbol}: {tmp.name}")
            return tmp.name
    except Exception as e:
        logger.error(f"Failed to generate chart for {symbol}: {e}")
        return None

def ask_chatgpt(symbol, info, hist, openai_api_key):
    """Query ChatGPT for a trade setup."""
    try:
        openai.api_key = openai_api_key
        rsi_val = round(hist['RSI'].dropna().iloc[-1], 2) if not hist['RSI'].dropna().empty else "N/A"
        current_price = info.get('regularMarketPrice', 'N/A')
        volume = info.get('volume', 'N/A')
        prompt = f"""You're an elite trading analyst. For {symbol}:
- Current Price: {current_price}
- RSI (14): {rsi_val}
- Volume: {volume}
Provide a concise trade setup with:
- Entry
- Stop Loss
- Price Target
- Reasoning
- Risk/reward summary
End with: "Follow @MemeDIYGenZX for more chaos!"
Keep it under 200 words."""
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            timeout=10
        )
        analysis = response.choices[0].message['content'].strip()
        logger.info(f"Generated ChatGPT analysis for {symbol}")
        return analysis
    except Exception as e:
        logger.error(f"ChatGPT failed for {symbol}: {e}")
        return "Analysis unavailable. Try again later.\nFollow @MemeDIYGenZX for more chaos!"
