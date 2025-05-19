import requests
import logging
import re

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

def verify_ipn(data):
    """Verify PayPal IPN request."""
    verify_url = "https://ipnpb.paypal.com/cgi-bin/webscr"
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    verify_data = {'cmd': '_notify-validate', **data}
    try:
        response = requests.post(verify_url, data=verify_data, headers=headers, timeout=10)
        response.raise_for_status()
        is_verified = response.text == "VERIFIED"
        logger.info(f"IPN verification: {'Success' if is_verified else 'Failed'}")
        return is_verified
    except Exception as e:
        logger.error(f"IPN verification failed: {e}")
        return False

def process_ipn(data, bot_token, processed_payments=None):
    """Process PayPal IPN and send welcome DM for valid payments."""
    if processed_payments is None:
        processed_payments = set()  # In-memory store for demo; use DB in production

    try:
        if not verify_ipn(data):
            logger.warning("Invalid IPN received")
            return "Invalid IPN", 400

        payment_status = data.get('payment_status')
        amount = data.get('mc_gross')
        username = data.get('custom', '').strip()
        txn_id = data.get('txn_id', '')

        # Validate payment
        if payment_status != "Completed":
            logger.info(f"Ignoring non-completed payment: {payment_status}")
            return "OK", 200
        if amount != '97.00':
            logger.warning(f"Invalid payment amount: {amount}")
            return "OK", 200
        if not username or not re.match(r'^[a-zA-Z0-9_]{3,32}$', username):
            logger.warning(f"Invalid username: {username}")
            return "OK", 200
        if not txn_id:
            logger.warning("Missing transaction ID")
            return "OK", 200

        # Prevent duplicate processing
        if txn_id in processed_payments:
            logger.info(f"Duplicate IPN for txn_id: {txn_id}")
            return "OK", 200
        processed_payments.add(txn_id)

        # Send welcome DM
        from telegram import send_welcome_dm  # Avoid circular import
        send_welcome_dm(username, bot_token)
        logger.info(f"Processed IPN for @{username}, txn_id: {txn_id}")
        return "OK", 200

    except Exception as e:
        logger.error(f"IPN processing error: {e}")
        return "Server error", 500
