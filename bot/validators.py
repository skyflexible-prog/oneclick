import re
from typing import Optional, Tuple

def validate_lot_size(lot_size_str: str) -> Tuple[bool, Optional[int], str]:
    """Validate lot size input"""
    try:
        lot_size = int(lot_size_str)
        if lot_size <= 0:
            return False, None, "Lot size must be positive"
        if lot_size > 1000:
            return False, None, "Lot size too large (max 1000)"
        return True, lot_size, "Valid"
    except ValueError:
        return False, None, "Invalid number format"

def validate_percentage(pct_str: str) -> Tuple[bool, Optional[float], str]:
    """Validate percentage input"""
    try:
        pct = float(pct_str)
        if pct < 0:
            return False, None, "Percentage cannot be negative"
        if pct > 100:
            return False, None, "Percentage cannot exceed 100%"
        return True, pct, "Valid"
    except ValueError:
        return False, None, "Invalid percentage format"

def validate_api_credentials(api_key: str, api_secret: str) -> Tuple[bool, str]:
    """Validate API key and secret format"""
    if len(api_key) < 10:
        return False, "API key too short"
    if len(api_secret) < 10:
        return False, "API secret too short"
    if ' ' in api_key or ' ' in api_secret:
        return False, "API credentials cannot contain spaces"
    return True, "Valid"

def validate_strategy_name(name: str) -> Tuple[bool, str]:
    """Validate strategy name"""
    if len(name) < 3:
        return False, "Strategy name too short (min 3 characters)"
    if len(name) > 50:
        return False, "Strategy name too long (max 50 characters)"
    if not re.match(r'^[a-zA-Z0-9_\s]+$', name):
        return False, "Strategy name can only contain letters, numbers, spaces, and underscores"
    return True, "Valid"

def validate_strike_offset(offset_str: str) -> Tuple[bool, Optional[int], str]:
    """Validate strike offset"""
    try:
        offset = int(offset_str)
        if offset < 0:
            return False, None, "Offset cannot be negative"
        if offset > 20:
            return False, None, "Offset too large (max 20 strikes)"
        return True, offset, "Valid"
    except ValueError:
        return False, None, "Invalid offset format"
        
