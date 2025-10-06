import re
from typing import Optional, Tuple


class InputValidator:
    """Validate user inputs"""
    
    @staticmethod
    def validate_api_key(api_key: str) -> Tuple[bool, str]:
        """Validate Delta Exchange API key format"""
        if not api_key or len(api_key.strip()) == 0:
            return False, "API key cannot be empty"
        
        api_key = api_key.strip()
        
        if len(api_key) < 20:
            return False, "API key too short"
        
        if not re.match(r'^[A-Za-z0-9_-]+$', api_key):
            return False, "API key contains invalid characters"
        
        return True, "Valid"
    
    @staticmethod
    def validate_api_secret(api_secret: str) -> Tuple[bool, str]:
        """Validate Delta Exchange API secret format"""
        if not api_secret or len(api_secret.strip()) == 0:
            return False, "API secret cannot be empty"
        
        api_secret = api_secret.strip()
        
        if len(api_secret) < 20:
            return False, "API secret too short"
        
        return True, "Valid"
    
    @staticmethod
    def validate_nickname(nickname: str) -> Tuple[bool, str]:
        """Validate API/strategy nickname"""
        if not nickname or len(nickname.strip()) == 0:
            return False, "Nickname cannot be empty"
        
        nickname = nickname.strip()
        
        if len(nickname) < 3:
            return False, "Nickname must be at least 3 characters"
        
        if len(nickname) > 50:
            return False, "Nickname must be less than 50 characters"
        
        if not re.match(r'^[A-Za-z0-9_ -]+$', nickname):
            return False, "Nickname can only contain letters, numbers, spaces, underscores, and hyphens"
        
        return True, "Valid"
    
    @staticmethod
    def validate_lot_size(lot_size_str: str) -> Tuple[bool, str, Optional[int]]:
        """Validate lot size input"""
        try:
            lot_size = int(lot_size_str.strip())
            
            if lot_size <= 0:
                return False, "Lot size must be greater than 0", None
            
            if lot_size > 100:
                return False, "Lot size seems too large (max 100)", None
            
            return True, "Valid", lot_size
        
        except ValueError:
            return False, "Lot size must be a number", None
    
    @staticmethod
    def validate_percentage(percent_str: str, allow_zero: bool = False) -> Tuple[bool, str, Optional[float]]:
        """Validate percentage input"""
        try:
            percent = float(percent_str.strip())
            
            if not allow_zero and percent <= 0:
                return False, "Percentage must be greater than 0", None
            
            if percent < 0:
                return False, "Percentage cannot be negative", None
            
            if percent > 100:
                return False, "Percentage cannot exceed 100%", None
            
            return True, "Valid", percent
        
        except ValueError:
            return False, "Percentage must be a number", None
    
    @staticmethod
    def validate_capital(capital_str: str) -> Tuple[bool, str, Optional[float]]:
        """Validate capital/amount input"""
        try:
            capital = float(capital_str.strip())
            
            if capital <= 0:
                return False, "Capital must be greater than 0", None
            
            if capital < 1000:
                return False, "Minimum capital is ₹1000", None
            
            if capital > 10000000:  # 1 crore
                return False, "Capital seems too large", None
            
            return True, "Valid", capital
        
        except ValueError:
            return False, "Capital must be a number", None
    
    @staticmethod
    def validate_strike_offset(offset_str: str) -> Tuple[bool, str, Optional[int]]:
        """Validate strike offset input"""
        try:
            offset = int(offset_str.strip())
            
            if offset < -10 or offset > 10:
                return False, "Strike offset must be between -10 and +10", None
            
            return True, "Valid", offset
        
        except ValueError:
            return False, "Strike offset must be a number", None
    
    @staticmethod
    def sanitize_text(text: str, max_length: int = 100) -> str:
        """Sanitize text input"""
        # Remove special characters except basic ones
        text = re.sub(r'[^A-Za-z0-9 _.,!?-]', '', text)
        # Truncate to max length
        return text[:max_length].strip()


# Create global validator instance
validator = InputValidator()
