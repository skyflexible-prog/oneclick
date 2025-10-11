from cryptography.fernet import Fernet
from config.settings import ENCRYPTION_KEY
import logging

logger = logging.getLogger(__name__)

class Encryptor:
    def __init__(self):
        if not ENCRYPTION_KEY:
            raise ValueError("ENCRYPTION_KEY not set in environment")
        self.cipher = Fernet(ENCRYPTION_KEY.encode())

    def encrypt(self, data: str) -> bytes:
        """Encrypt string data"""
        return self.cipher.encrypt(data.encode())

    def decrypt(self, encrypted_data: bytes) -> str:
        """Decrypt encrypted data"""
        return self.cipher.decrypt(encrypted_data).decode()

def calculate_breakeven(call_strike: float, put_strike: float, 
                       total_premium: float, direction: str) -> tuple:
    """Calculate breakeven points for straddle/strangle"""
    if direction == 'long':
        upper_be = call_strike + total_premium
        lower_be = put_strike - total_premium
    else:  # short
        upper_be = call_strike + total_premium
        lower_be = put_strike - total_premium
    
    return upper_be, lower_be

def calculate_pnl(call_entry: float, put_entry: float, call_exit: float, 
                 put_exit: float, lot_size: int, direction: str) -> float:
    """Calculate P&L for straddle/strangle position"""
    if direction == 'long':
        call_pnl = (call_exit - call_entry) * lot_size
        put_pnl = (put_exit - put_entry) * lot_size
    else:  # short
        call_pnl = (call_entry - call_exit) * lot_size
        put_pnl = (put_entry - put_exit) * lot_size
    
    return call_pnl + put_pnl

def format_currency(amount: float) -> str:
    """Format amount as Indian Rupees"""
    return f"₹{amount:,.2f}"

def round_to_strike(price: float, strike_interval: float = 500) -> float:
    """Round price to nearest strike interval"""
    return round(price / strike_interval) * strike_interval
    
