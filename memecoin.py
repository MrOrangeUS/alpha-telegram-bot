import requests
import openai
import os
import logging
import time
import sys
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Dict, List, Optional, Union
import gc

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/memecoin.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
TRENDING_URL = "https://api.coingecko.com/api/v3/search/trending"
SENTIMENT_URL = "https://api.coingecko.com/api/v3/coins/{}/sentiment"

MEME_COINS = [
    "pepe", "dogecoin", "floki", "bonk", "wojak", 
    "dogwifhat", "shiba-inu", "baby-doge-coin"
]

REQUEST_TIMEOUT = 15  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
CACHE_TTL = 300  # 5 minutes

# Create a session for connection pooling
session = requests.Session()
session.headers.update({
    'User-Agent': 'Python-Memecoin-Bot',
    'Accept': 'application/json'
})

class CoinGeckoRateLimit:
    def __init__(self, calls_per_minute=30, burst_limit=35, memory_limit_mb=100):
        self.calls_per_minute = calls_per_minute
        self.burst_limit = burst_limit
        self.calls = []
        self.last_reset = time.time()
        self.memory_limit = memory_limit_mb * 1024 * 1024  # Convert to bytes
        
    def check_memory_usage(self) -> None:
        """Monitor memory usage of the rate limiter."""
        try:
            memory_size = sys.getsizeof(self.calls)
            if memory_size > self.memory_limit:
                logger.warning(f"Rate limiter memory usage high: {memory_size / 1024 / 1024:.2f}MB")
                self.calls = self.calls[-self.calls_per_minute:]  # Keep only recent calls
                gc.collect()  # Force garbage collection
        except Exception as e:
            logger.error(f"Error checking memory usage: {str(e)}")
        
    def wait_if_needed(self) -> None:
        now = time.time()
        
        # Reset counter if a minute has passed
        if now - self.last_reset >= 60:
            self.calls = []
            self.last_reset = now
            self.check_memory_usage()
            return
        
        self.calls = [call for call in self.calls if call > now - 60]
        
        if len(self.calls) >= self.calls_per_minute:
            sleep_time = 60 - (now - self.calls[0])
            if sleep_time > 0:
                logger.info(f"Rate limit reached, waiting {sleep_time:.2f} seconds")
                time.sleep(sleep_time)
                
        # Emergency brake for burst protection
        if len(self.calls) >= self.burst_limit:
            logger.warning("Burst limit reached, enforcing cooldown")
            time.sleep(5)  # Force cooldown
            
        self.calls.append(now)

rate_limiter = CoinGeckoRateLimit()

def make_request(url: str, params: Optional[Dict] = None, retries: int = MAX_RETRIES) -> Dict:
    """Make a rate-limited request with retries and proper error handling."""
    response = None
    for attempt in range(retries):
        try:
            rate_limiter.wait_if_needed()
            response = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.warning(f"Request timeout on attempt {attempt + 1}/{retries}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
        except requests.exceptions.RequestException as e:
            if response and response.status_code == 429:
                logger.warning("Rate limit exceeded, backing off...")
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                logger.error(f"Request failed: {str(e)}")
                if attempt == retries - 1:
                    raise
    raise Exception("Max retries exceeded")

def ttl_hash(seconds: int = CACHE_TTL):
    """Return the same value within `seconds` time period."""
    return round(time.time() / seconds)

@lru_cache(maxsize=1)
def fetch_memecoin_prices(vs_currency: str = "usd", _cache_buster: int = ttl_hash()) -> Dict:
    """Fetch current prices and 24h changes for meme coins."""
    try:
        params = {
            "ids": ",".join(MEME_COINS),
            "vs_currencies": vs_currency,
            "include_24hr_change": "true",
            "include_24hr_vol": "true",
            "include_market_cap": "true"
        }
        
        logger.info("Fetching memecoin prices from CoinGecko")
        data = make_request(COINGECKO_URL, params)
        
        if not data:
            logger.error("No data received from CoinGecko API")
            return {}
            
        result = {}
        for coin in MEME_COINS:
            if coin in data:
                result[coin] = {
                    "price": data[coin][vs_currency],
                    "change": data[coin].get(f"{vs_currency}_24h_change", 0),
                    "volume": data[coin].get(f"{vs_currency}_24h_vol", 0),
                    "market_cap": data[coin].get(f"{vs_currency}_market_cap", 0)
                }
                
        logger.info(f"Successfully fetched prices for {len(result)} meme coins")
        return result
        
    except Exception as e:
        logger.error(f"Error fetching memecoin prices: {str(e)}", exc_info=True)
        return {}

def fetch_coin_sentiment(coin_id: str) -> Optional[Dict]:
    """Fetch social sentiment data for a specific coin."""
    try:
        url = SENTIMENT_URL.format(coin_id)
        data = make_request(url)
        
        return {
            "sentiment_votes_up_percentage": data.get("sentiment_votes_up_percentage", 50),
            "sentiment_votes_down_percentage": data.get("sentiment_votes_down_percentage", 50)
        }
    except Exception as e:
        logger.warning(f"Could not fetch sentiment for {coin_id}: {str(e)}")
        return None

def calculate_market_metrics(prices: Dict) -> Dict:
    """Calculate market-wide metrics for meme coins."""
    try:
        if not prices:
            return {}
            
        total_market_cap = sum(coin["market_cap"] for coin in prices.values())
        total_volume = sum(coin["volume"] for coin in prices.values())
        avg_change = sum(coin["change"] for coin in prices.values()) / len(prices)
        
        # Calculate volatility and additional metrics
        changes = [coin["change"] for coin in prices.values()]
        volatility = sum((c - avg_change) ** 2 for c in changes) / len(changes)
        
        # Add market dominance calculation
        market_dominance = {
            coin: (data["market_cap"] / total_market_cap * 100) 
            for coin, data in prices.items()
        }
        
        return {
            "total_market_cap": total_market_cap,
            "total_volume": total_volume,
            "average_change": avg_change,
            "market_volatility": volatility,
            "market_dominance": market_dominance
        }
    except Exception as e:
        logger.error(f"Error calculating market metrics: {str(e)}", exc_info=True)
        return {}

def top_meme_breakouts(prices: Dict, min_percent_change: float = 10) -> List:
    """Identify breakout meme coins based on price action and volume."""
    try:
        if not prices:
            return []
            
        movers = []
        avg_volume = sum(data["volume"] for data in prices.values()) / len(prices)
        
        for coin, data in prices.items():
            if not isinstance(data, dict) or "change" not in data:
                logger.warning(f"Invalid data format for coin {coin}")
                continue
                
            # Enhanced breakout detection
            price_significant = abs(data["change"]) >= min_percent_change
            volume_significant = data["volume"] > avg_volume * 1.5
            
            if price_significant or volume_significant:
                sentiment = fetch_coin_sentiment(coin)
                
                movers.append((coin, {
                    **data,
                    "sentiment": sentiment if sentiment else {"sentiment_votes_up_percentage": 50},
                    "volume_ratio": data["volume"] / avg_volume if avg_volume else 1
                }))
                
        # Sort by combined score of price change, volume, and sentiment
        movers.sort(key=lambda x: (
            abs(x[1]["change"]) * 
            (x[1]["volume_ratio"]) * 
            (x[1]["sentiment"]["sentiment_votes_up_percentage"] / 50)
        ), reverse=True)
        
        logger.info(f"Found {len(movers)} breakout coins")
        return movers
        
    except Exception as e:
        logger.error(f"Error in top_meme_breakouts: {str(e)}", exc_info=True)
        return []

@lru_cache(maxsize=1)
def fetch_trending_coins(_cache_buster: int = ttl_hash()) -> List:
    """Fetch trending coins from CoinGecko."""
    try:
        logger.info("Fetching trending coins from CoinGecko")
        data = make_request(TRENDING_URL)
        trending = []
        
        for item in data.get("coins", []):
            coin_data = item.get("item", {})
            trending.append({
                "id": coin_data.get("id"),
                "symbol": coin_data.get("symbol"),
                "market_cap_rank": coin_data.get("market_cap_rank"),
                "score": coin_data.get("score"),
                "price_btc": coin_data.get("price_btc", 0)
            })
            
        logger.info(f"Found {len(trending)} trending coins")
        return trending
        
    except Exception as e:
        logger.error(f"Error fetching trending coins: {str(e)}", exc_info=True)
        return []

def ask_gpt_memecoin_breakout(breakouts: List, trending: List, openai_api_key: str) -> str:
    """Generate AI analysis of meme coin movements."""
    try:
        if not openai_api_key:
            logger.error("OpenAI API key not configured")
            return "⚠️ AI analysis service not configured"

        openai.api_key = openai_api_key
        
        # Calculate market-wide metrics
        market_metrics = calculate_market_metrics(dict(breakouts))
        
        # Format breakout coins information with enhanced metrics
        coins_info = []
        for coin, info in breakouts:
            sentiment = info.get("sentiment", {}).get("sentiment_votes_up_percentage", 50)
            volume_ratio = info.get("volume_ratio", 1)
            market_dom = market_metrics.get("market_dominance", {}).get(coin, 0)
            
            coins_info.append(
                f"{coin.upper()}: ${info['price']:.6f} ({info['change']:+.2f}% 24h) "
                f"| Volume: ${info['volume']:,.0f} ({volume_ratio:.1f}x avg) "
                f"| Market Dom: {market_dom:.1f}% "
                f"| Sentiment: {'🟢' if sentiment > 50 else '🔴'} {sentiment:.0f}%"
            )
        coins_text = "\n".join(coins_info) or "No major price breakouts detected."

        # Format trending coins information
        trending_memes = [t for t in trending if t["id"] in MEME_COINS]
        trending_text = "\n".join([
            f"{t['symbol'].upper()}: Rank #{t['market_cap_rank']} "
            f"(Score: {t['score']:.1f}, BTC: {t['price_btc']:.8f})"
            for t in trending_memes
        ]) or "No meme coins are trending right now."

        prompt = f"""Act as Nova Stratos, an AI quant and meme coin momentum hunter. Analyze the current meme coin market:

Market Overview:
- Total Market Cap: ${market_metrics.get('total_market_cap', 0):,.0f}
- 24h Volume: ${market_metrics.get('total_volume', 0):,.0f}
- Average Change: {market_metrics.get('average_change', 0):+.2f}%
- Market Volatility: {market_metrics.get('market_volatility', 0):.2f}

Breakout Coins:
{coins_text}

Trending on CoinGecko:
{trending_text}

For each significant mover:
1. Analyze the price action, volume patterns, and market dominance
2. Consider social sentiment and market ranking
3. Provide a clear risk assessment
4. Suggest entry zones if applicable

Wrap up with:
- Overall market sentiment for meme coins
- Nova's confidence score (1-10) for catching meme waves today
- Key risk management tips
- Potential catalysts to watch

Sign off with: "Generated by Nova Stratos 🤖"
"""
        logger.info("Requesting AI analysis for meme coins")
        
        try:
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are Nova Stratos, an AI quant analyst specializing in meme coin momentum and social sentiment analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=750,
                timeout=20
            )
            
            if not response.choices:
                logger.error("No response from OpenAI API")
                return "Error: Could not generate analysis"
                
            logger.info("Successfully generated meme coin analysis")
            return response.choices[0].message.content

        except openai.error.Timeout:
            logger.error("OpenAI API timeout")
            return "⚠️ AI analysis timed out, please try again"
        except openai.error.APIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return "⚠️ AI service temporarily unavailable"
        except openai.error.RateLimitError:
            logger.error("OpenAI rate limit exceeded")
            return "⚠️ AI service rate limit exceeded, please try again later"

    except Exception as e:
        logger.error(f"Unexpected error in ask_gpt_memecoin_breakout: {str(e)}", exc_info=True)
        return "⚠️ Could not complete meme coin analysis"

def nova_memesnipe(openai_api_key: str) -> str:
    """Main function to analyze meme coin opportunities."""
    try:
        logger.info("Starting meme coin analysis")
        start_time = time.time()
        
        prices = fetch_memecoin_prices()
        if not prices:
            return "⚠️ Could not fetch meme coin data"
            
        movers = top_meme_breakouts(prices, min_percent_change=10)
        trending = fetch_trending_coins()
        
        analysis = ask_gpt_memecoin_breakout(movers, trending, openai_api_key)
        
        duration = time.time() - start_time
        logger.info(f"Completed meme coin analysis in {duration:.2f}s")
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error in nova_memesnipe: {str(e)}", exc_info=True)
        return "⚠️ Could not complete meme coin analysis"

def cleanup():
    """Cleanup resources when shutting down."""
    try:
        session.close()
        logger.info("Cleaned up HTTP session")
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")

# Register cleanup handler
import atexit
atexit.register(cleanup)

# Example CLI test
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    try:
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        if not OPENAI_API_KEY:
            logger.error("OPENAI_API_KEY not set")
            sys.exit(1)
            
        print(nova_memesnipe(OPENAI_API_KEY))
        
    except Exception as e:
        logger.error(f"CLI test error: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        cleanup()
