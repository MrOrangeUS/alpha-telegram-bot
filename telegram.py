import openai
import requests
import os

NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# ---- Nova's Real-Time Joke ----
def nova_joke(openai_api_key):
    openai.api_key = openai_api_key
    prompt = (
        "You are Nova Stratos, an AI quant analyst with a dry, clever sense of trading humor. "
        "Generate a witty one-liner or joke related to trading, crypto, meme coins, or the wild world of financial markets. "
        "Make sure it’s fresh and never just a cliché."
    )
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message['content']

# ---- Get Latest Finance News ----
def get_finance_news():
    try:
        url = f"https://newsapi.org/v2/top-headlines?category=business&language=en&apiKey={NEWS_API_KEY}"
        resp = requests.get(url, timeout=10).json()
        articles = resp.get('articles', [])
        if articles:
            top = articles[:2]
            news = "\n".join([f"🗞️ Finance News: {a['title']} ({a['source']['name']})" for a in top])
            return news
        else:
            return "No finance news found."
    except Exception as e:
        print("Error in get_finance_news:", e)
        return "Could not fetch finance news."

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
    requests.post(url, data=payload)
