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
        prompt = f"""prompt = f"""You are an elite AI market analyst for a private Telegram alpha channel. Your job is to produce a deeply researched, actionable trade setup for {symbol}, based on all the latest technical, volume, trend, and news data below, plus any macro or sector sentiment. 
**If the options chain is liquid, always recommend the most profitable call or put options contract as well as the stock play.**

- Ticker: {symbol}
- Current Price: {current_price}
- RSI (14): {rsi_val}
- Volume: {volume}

Instructions:
1. Do deep technical analysis. Detect breakouts, reversals, price patterns, or divergences. State why.
2. Scan for news, macro conditions, or sector trends affecting the ticker and reference them if relevant.
3. Output an actionable trade:
   - **Direction** (Long/Short/No Trade)
   - **Entry Price**
   - **Stop Loss**
   - **Two Price Targets** (conservative/aggressive)
4. **Options Play:** 
   - Suggest the most profitable call or put (whichever matches your thesis) with:
     - **Strike Price**
     - **Expiration Date**
     - **Entry Price** (option premium)
     - **Profit Target**
   - Use only near-the-money, next-month contracts unless you see a better opportunity.
   - If options volume is too low or no clear edge, state "No optimal options play."

5. Justify the setup with 1-2 sharp sentences using technical, volume, AND news/macro logic.

6. End with: "Posted by AI Alpha Club | More: @xxx"

**Format your answer exactly like this:**
""""""
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            timeout=10
        )
        analysis = response.choices[0].message['content'].strip()
        return analysis
    except Exception as e:
        logger.error(f"ChatGPT failed for {symbol}: {e}")
        return "Analysis unavailable. Try again later.\nFollow @MemeDIYGenZX for more chaos!"
