import requests
import logging
import re
import time
import hashlib
from typing import Dict, Tuple, Optional, Set
from datetime import datetime, timedelta
from collections import OrderedDict

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/paypal.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
VERIFY_URL_SANDBOX = "https://ipnpb.sandbox.paypal.com/cgi-bin/webscr"
VERIFY_URL_PROD = "https://ipnpb.paypal.com/cgi-bin/webscr"
REQUEST_TIMEOUT = 15  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
PAYMENT_AMOUNT = 97.00
ACCEPTED_CURRENCIES = {'USD', 'EUR', 'GBP'}
MAX_PROCESSED_PAYMENTS = 1000  # Maximum number of processed payment hashes to store

# Create a session for connection pooling
session = requests.Session()
session.headers.update({
    'content-type': 'application/x-www-form-urlencoded',
    'user-agent': 'Python-IPN-Verification-Script'
})

class PayPalIPNError(Exception):
    """Custom exception for PayPal IPN errors."""
    pass

class ProcessedPayments:
    """Thread-safe storage for processed payment hashes with automatic cleanup."""
    def __init__(self, max_size: int = MAX_PROCESSED_PAYMENTS):
        self.max_size = max_size
        self.payments = OrderedDict()
        
    def add(self, payment_hash: str) -> None:
        """Add a payment hash with timestamp."""
        self.payments[payment_hash] = time.time()
        if len(self.payments) > self.max_size:
            # Remove oldest entries
            while len(self.payments) > self.max_size * 0.8:  # Remove 20% when full
                self.payments.popitem(last=False)
                
    def __contains__(self, payment_hash: str) -> bool:
        """Check if payment hash exists."""
        return payment_hash in self.payments
        
    def cleanup_old_entries(self, max_age_hours: int = 24) -> None:
        """Remove entries older than max_age_hours."""
        cutoff_time = time.time() - (max_age_hours * 3600)
        for payment_hash, timestamp in list(self.payments.items()):
            if timestamp < cutoff_time:
                del self.payments[payment_hash]

# Global storage for processed payments
processed_payments = ProcessedPayments()

def verify_ipn(data: Dict, sandbox: bool = False) -> bool:
    """
    Verify PayPal IPN request with improved error handling.
    
    Args:
        data: The IPN data to verify
        sandbox: Whether to use sandbox environment
        
    Returns:
        bool: True if verification successful, False otherwise
    """
    verify_url = VERIFY_URL_SANDBOX if sandbox else VERIFY_URL_PROD
    verify_data = {'cmd': '_notify-validate', **data}
    
    for attempt in range(MAX_RETRIES):
        try:
            response = session.post(
                verify_url,
                data=verify_data,
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            
            is_verified = response.text == "VERIFIED"
            logger.info(f"IPN verification attempt {attempt + 1}: {'Success' if is_verified else 'Failed'}")
            return is_verified
            
        except requests.exceptions.Timeout:
            logger.warning(f"IPN verification timeout on attempt {attempt + 1}/{MAX_RETRIES}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
        except requests.exceptions.RequestException as e:
            logger.error(f"IPN verification request failed: {str(e)}")
            if attempt == MAX_RETRIES - 1:
                raise PayPalIPNError(f"IPN verification failed after {MAX_RETRIES} attempts")
            time.sleep(RETRY_DELAY * (attempt + 1))
            
    return False

def validate_ipn_data(data: Dict) -> Tuple[bool, Optional[str]]:
    """
    Validate IPN data format and required fields.
    
    Args:
        data: The IPN data to validate
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Invalid data format"
        
    required_fields = {
        'payment_status',
        'mc_gross',
        'txn_id',
        'custom',  # username field
        'mc_currency'
    }
    
    missing_fields = required_fields - set(data.keys())
    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"
        
    # Validate payment status
    if data['payment_status'] != "Completed":
        return True, None  # Valid but not completed
        
    # Validate currency
    if data['mc_currency'] not in ACCEPTED_CURRENCIES:
        return False, f"Invalid currency: {data['mc_currency']}"
        
    # Validate amount format and value
    try:
        amount = float(data['mc_gross'])
        if amount != PAYMENT_AMOUNT:
            return False, f"Invalid payment amount: {amount} {data['mc_currency']}"
    except (ValueError, TypeError):
        return False, f"Invalid amount format: {data['mc_gross']}"
        
    # Validate username format
    username = data['custom'].strip()
    if not username or not re.match(r'^[a-zA-Z0-9_]{3,32}$', username):
        return False, f"Invalid username format: {username}"
        
    return True, None

def calculate_ipn_hash(data: Dict) -> str:
    """
    Calculate a unique hash for the IPN transaction.
    
    Args:
        data: The IPN data
        
    Returns:
        str: Unique hash for the transaction
    """
    # Create a string of key transaction data
    hash_input = f"{data.get('txn_id', '')}:{data.get('mc_gross', '')}:{data.get('payment_status', '')}"
    
    # Calculate SHA-256 hash
    return hashlib.sha256(hash_input.encode()).hexdigest()

def process_ipn(data: Dict, bot_token: str) -> Tuple[str, int]:
    """
    Process PayPal IPN with enhanced validation.
    
    Args:
        data: The IPN data to process
        bot_token: Telegram bot token
        
    Returns:
        Tuple[str, int]: (response_message, http_status_code)
    """
    try:
        start_time = time.time()
        logger.info("Starting IPN processing")
        
        # Cleanup old processed payments periodically
        processed_payments.cleanup_old_entries()
        
        # Basic validation
        is_valid, error_msg = validate_ipn_data(data)
        if not is_valid:
            logger.warning(f"IPN validation failed: {error_msg}")
            return error_msg, 400
            
        # Skip non-completed payments early
        if data['payment_status'] != "Completed":
            logger.info(f"Skipping non-completed payment: {data['payment_status']}")
            return "OK", 200
            
        # Verify with PayPal
        if not verify_ipn(data):
            logger.warning("PayPal IPN verification failed")
            return "Invalid IPN", 400
            
        # Check for duplicate transaction
        txn_hash = calculate_ipn_hash(data)
        if txn_hash in processed_payments:
            logger.info(f"Duplicate IPN detected: {data.get('txn_id')}")
            return "OK", 200
            
        # Process the payment
        try:
            username = data['custom'].strip()
            from telegram import send_welcome_dm  # Avoid circular import
            
            send_welcome_dm(username, bot_token)
            processed_payments.add(txn_hash)
            
            duration = time.time() - start_time
            logger.info(
                f"Successfully processed IPN for @{username} "
                f"(txn_id: {data.get('txn_id')}, "
                f"amount: {data.get('mc_gross')} {data.get('mc_currency')}) "
                f"in {duration:.2f}s"
            )
            return "OK", 200
            
        except Exception as e:
            logger.error(f"Failed to send welcome DM: {str(e)}", exc_info=True)
            return "Failed to send welcome message", 500
            
    except PayPalIPNError as e:
        logger.error(f"PayPal IPN Error: {str(e)}", exc_info=True)
        return "PayPal IPN verification failed", 400
    except Exception as e:
        logger.error(f"Unexpected error in process_ipn: {str(e)}", exc_info=True)
        return "Server error", 500

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
