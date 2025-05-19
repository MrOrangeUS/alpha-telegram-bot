from flask import Flask, request
import requests

app = Flask(__name__)

# === CONFIG ===
TELEGRAM_BOT_TOKEN = '7837275219:AAHNL3m4HcpYO2eIMd7xdM2zPiAGSZy49N0'
TELEGRAM_CHANNEL_LINK = 'https://t.me/+MKqVoWpn4cFiYjIx  # Optional: link to your Telegram channel

# === VERIFY IPN WITH PAYPAL ===
def verify_ipn(data):
    verify_url = "https://ipnpb.paypal.com/cgi-bin/webscr"
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    verify_data = {'cmd': '_notify-validate'}
    verify_data.update(data)
    response = requests.post(verify_url, data=verify_data, headers=headers)
    return response.text == "VERIFIED"

# === SEND TELEGRAM DM ===
def send_auto_dm(username):
    msg = """
🚀 You’re in.

Welcome to *DAILY ALPHA* — my private signal channel.

✅ New plays drop every 4 hours  
✅ Turn on notifications  
✅ Tap the pinned post for the latest alpha

Link is yours — don’t share it.
Next move hits soon.

– @MrOrangeUS
"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': f"@{username}",
        'text': msg,
        'parse_mode': 'Markdown'
    }
    response = requests.post(url, data=payload)
    print(f"DM sent to @{username}: {response.status_code} - {response.text}")
    return response

# === PAYPAL IPN LISTENER ===
@app.route('/paypal-ipn', methods=['POST'])
def paypal_ipn():
    data = request.form.to_dict()
    print("IPN Received:", data)

    if not verify_ipn(data):
        print("Invalid IPN.")
        return "Invalid IPN", 400

    if data.get('payment_status') == "Completed" and data.get('mc_gross') == '97.00':
        telegram_username = data.get('custom')  # The buyer must enter their @username at checkout
        if telegram_username:
            send_auto_dm(telegram_username)
            return "Success", 200
        else:
            print("No @username found in custom field.")
    else:
        print("Ignored IPN: not a completed $97 payment.")

    return "Ignored", 200

# === RUN THE APP ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
