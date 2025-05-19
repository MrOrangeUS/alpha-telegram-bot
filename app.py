@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    try:
        data = request.get_json()
        print("🔥 Webhook received:", data)

        # Works for both message and channel_post (groups, channels, private)
        message = data.get("message") or data.get("channel_post", {})
        text = message.get("text", "").strip().lower()
        chat_id = message.get("chat", {}).get("id")

        print("📩 Text received:", text)
        print("📢 Chat ID:", chat_id)

        # Check if the command is /drop with or without @botname
        if text.startswith("/drop"):
            base_cmd = text.split()[0]   # only command part
            if base_cmd.startswith("/drop"):
                print("✅ Detected /drop command")
                run_alpha_drop(chat_id)
                reply = "🚀 Alpha drop initiated manually!"
            else:
                print("❌ Not /drop after normalization:", base_cmd)
                reply = "Unknown command. Try /drop"
        else:
            print("❌ Command did not start with /drop:", text)
            reply = "Unknown command. Try /drop"

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": reply
        }
        requests.post(url, json=payload)

    except Exception as e:
        print("❌ Error in /webhook:", str(e))

    return "OK", 200
