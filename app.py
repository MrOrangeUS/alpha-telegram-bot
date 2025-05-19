from flask import Flask, request
import requests

app = Flask(__name__)

# === CONFIG ===
TELEGRAM_BOT_TOKEN = 'your-telegram-bot-token'
TELEGRAM_CHANNEL_LINK = 'https://t.me/your_private_channel_link'

# === VERIFY IPN ===
def verify_ipn(data):
    verify_url = "https://ipnpb.paypal.com/cgi-bin/webscr"
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    verify_data = {'cmd': '_notify-validate'}
    verify_data.update(data)
    response = requests.post(verify_url, data=verify_data, headers=headers)
    return response.text == "VERIFIED"

# === SEND AUTO-DM ON PAYMENT ===
def send_auto_dm(username):
    msg = """
🚀 You’re in.

Welcome to *DAILY ALPHA* — my private signal channel.

✅ New plays drop every 4 hours  
✅ Turn on notifications  
✅ Tap the pinned post for the latest alpha

Link is yours — don’t share it.
Next move hits soon.

– @YourUsername
"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': f"@{username}",
        'text': msg,
        'parse_mode': 'Markdown'
    }
    return requests.post(url, data=payload)

# === IPN ENDPOINT ===
@app.route('/paypal-ipn', methods=['POST'])
def paypal_ipn():
    data = request.form.to_dict()
    if not verify_ipn(data):
        return "Invalid IPN", 400

    if data.get('payment_status') == "Completed" and data.get('mc_gross') == '97.00':
        telegram_username = data.get('custom')  # Must be filled during checkout
        if telegram_username:
            send_auto_dm(telegram_username)
            return "Success", 200
    return "Ignored", 200

if __name__ == '__main__':
    app.run(port=5000)
