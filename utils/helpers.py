from cryptography.fernet import Fernet
from config.settings import settings
from datetime import datetime, timedelta
import re
from typing import Optional


class Encryptor:
    """Handle encryption and decryption of sensitive data"""
    
    def __init__(self):
        self.cipher = Fernet(settings.encryption_key.encode())
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext string"""
        return self.cipher.encrypt(plaintext.encode()).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext string"""
        return self.cipher.decrypt(ciphertext.encode()).decode()


# Initialize global encryptor
encryptor = Encryptor()


def format_currency(amount: float) -> str:
    """Format amount as Indian currency"""
    return f"₹{amount:,.2f}"


def format_percentage(value: float) -> str:
    """Format value as percentage"""
    return f"{value:.2f}%"


def calculate_pnl(entry_price: float, exit_price: float, lot_size: int, is_long: bool) -> float:
    """Calculate profit and loss"""
    if is_long:
        pnl = (exit_price - entry_price) * lot_size
    else:
        pnl = (entry_price - exit_price) * lot_size
    return round(pnl, 2)


def validate_api_key(api_key: str) -> bool:
    """Validate Delta Exchange API key format"""
    # Delta API keys are typically alphanumeric with specific length
    pattern = r'^[A-Za-z0-9]{20,}$'
    return bool(re.match(pattern, api_key))


def validate_telegram_id(telegram_id: int) -> bool:
    """Validate Telegram user ID"""
    return telegram_id > 0 and telegram_id < 10**10


def is_admin(telegram_id: int) -> bool:
    """Check if user is admin"""
    return telegram_id in settings.admin_ids_list


def get_expiry_date(expiry_type: str) -> Optional[datetime]:
    """Calculate expiry date based on type (daily, weekly, monthly)"""
    now = datetime.utcnow()
    
    if expiry_type == "daily":
        # Next day same time
        return now + timedelta(days=1)
    elif expiry_type == "weekly":
        # Next Friday
        days_ahead = 4 - now.weekday()  # Friday is 4
        if days_ahead <= 0:
            days_ahead += 7
        return now + timedelta(days=days_ahead)
    elif expiry_type == "monthly":
        # Last Friday of current month
        next_month = now.month + 1 if now.month < 12 else 1
        year = now.year if now.month < 12 else now.year + 1
        # Calculate last Friday logic here
        return now + timedelta(days=30)
    
    return None


def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent injection attacks"""
    # Remove special characters except alphanumeric, space, underscore, dash
    return re.sub(r'[^A-Za-z0-9 _\-.]', '', text)


def format_timestamp(dt: datetime) -> str:
    """Format datetime for display"""
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def calculate_strike_offset(spot_price: float, offset: int, strike_interval: float = 500.0) -> float:
    """Calculate strike price with offset from ATM"""
    atm_strike = round(spot_price / strike_interval) * strike_interval
    return atm_strike + (offset * strike_interval)
  
