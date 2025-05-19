def run_alpha_drop(chat_id, bot_token, openai_api_key):
    symbol = "XFOR"  # Or rotate
    logger.info(f"Starting alpha drop for {symbol}")
    info, hist = fetch_stock_data(symbol)
    if not info or hist is None:
        logger.error(f"No data for {symbol}, aborting drop")
        return False
    chart = generate_chart(symbol, hist)
    if not chart:
        logger.error(f"No chart for {symbol}, aborting drop")
        return False
    # PASS openai_api_key TO ask_chatgpt!
    analysis = ask_chatgpt(symbol, info, hist, openai_api_key)
    send_telegram_post(symbol, analysis, chart, chat_id, bot_token)
    return True

def handle_webhook(data, bot_token, allowed_chat_id, openai_api_key):
    try:
        logger.debug(f"Webhook data: {data}")
        message = data.get("message") or data.get("channel_post", {})
        text = message.get("text", "").strip()
        chat_id = str(message.get("chat", {}).get("id"))

        logger.info(f"Received text: {text}, chat_id: {chat_id}")

        if not chat_id:
            logger.warning("No chat_id in webhook data")
            return "No chat_id", 400

        entities = message.get("entities", [])
        command = None
        for entity in entities:
            if entity.get("type") == "bot_command":
                command = text[entity["offset"]:entity["offset"] + entity["length"]].lower()
                break
        logger.info(f"Extracted command: {command}")

        if allowed_chat_id and str(chat_id) != str(allowed_chat_id):
            logger.warning(f"Unauthorized chat_id: {chat_id}")
            reply = "This bot is restricted to a specific channel."
        elif command and command.startswith("/drop"):
            logger.info("Processing /drop command")
            # PASS openai_api_key TO run_alpha_drop!
            success = run_alpha_drop(chat_id, bot_token, openai_api_key)
            reply = "🚀 Alpha drop initiated manually!" if success else "❌ Failed to drop alpha. Try again later."
        else:
            logger.info(f"Ignoring unknown command: {text}")
            reply = "Unknown command. Try /drop"

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": reply}
        requests.post(url, json=payload)
        return "OK", 200

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "Server error", 500
