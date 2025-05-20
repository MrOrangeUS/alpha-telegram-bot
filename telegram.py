import openai
import requests
import os
import random
from jokes import nova_joke

NEWS_API_KEY = os.getenv("NEWS_API_KEY")



# ---- Nova's Real-Time Comedian Joke ----
def random_comedian_joke(openai_api_key, topic="trading, crypto, meme coins, or financial markets"):
    openai.api_key = openai_api_key
    comedian = random.choice(COMEDIANS)
    prompt = (
        f"Act as {comedian}, the legendary stand-up comedian. "
        f"Make a brand new, sharp, clever joke about {topic} as if you're performing live. "
        f"Channel the exact comedic style, voice, and attitude of {comedian}. "
        f"Don't recycle classic bits; make it original and relevant to modern trading, markets, or crypto culture. "
        f"Deliver it as a one-liner or a short bit, and sign off with '- {comedian}'."
    )
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content


# ---- Get Latest Finance News ----
def get_finance_news():
    try:
        if not NEWS_API_KEY:
            print("NEWS_API_KEY not configured")
            return "📰 News service not configured"

        url = f"https://newsapi.org/v2/top-headlines?category=business&language=en&apiKey={NEWS_API_KEY}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()  # Will raise an exception for 4XX/5XX status codes
        
        data = resp.json()
        if 'status' in data and data['status'] != 'ok':
            print(f"News API error: {data.get('message', 'Unknown error')}")
            return "Could not fetch finance news: API error"
            
        articles = data.get('articles', [])
        if not articles:
            return "No finance news available at the moment."
            
        top = articles[:2]
        news = "\n".join([f"🗞️ Finance News: {a['title']} ({a['source']['name']})" for a in top])
        return news

    except requests.exceptions.RequestException as e:
        print(f"News API request error: {e}")
        return "Could not fetch finance news: Network error"
    except Exception as e:
        print(f"Unexpected error in get_finance_news: {e}")
        return "Could not fetch finance news: Internal error"

# ---- Unified Command Handler (example) ----
def handle_telegram_command(command, openai_api_key, keyword_found=None):
    command = command.split()[0].split("@")[0].lower()

    if command == "/joke":
        return nova_joke(openai_api_key)
    elif command == "/news":
        return get_finance_news()
    elif command == "/status":
        return "🤖 Nova Stratos is online and ready!"
    elif keyword_found:
        return f"👀 You mentioned *{keyword_found.upper()}* — want the latest update? Try /drop or /memesnipe."
    else:
        return "Unknown command. Try /drop, /memesnipe, /joke, or /news."

# ---- Send Welcome DM ----
def send_welcome_dm(username, bot_token):
    msg = """🚀 You're in.

Welcome to *DAILY ALPHA* — my private signal channel.

✅ New plays drop every 4 hours  
✅ Turn on notifications  
✅ Tap the pinned post for the latest alpha

Link is yours — don't share it.
Next move hits soon.

– @MrOrangeUS"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {'chat_id': f"@{username}", 'text': msg, 'parse_mode': 'Markdown'}
    requests.post(url, data=payload)
