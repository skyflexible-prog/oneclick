# trading/strangle_calculator.py

from typing import Tuple, List, Dict, Optional
from utils.logger import bot_logger
import math


class StrangleCalculator:
    """Calculate strikes and stop-loss for strangle strategy"""
    
    @staticmethod
    def calculate_strikes(
        spot_price: float,
        method: str,
        strike_type: Optional[str],
        value: float,
        asset: str = "BTC"
    ) -> Tuple[float, float]:
        """
        Calculate call and put strikes for strangle
        
        Args:
            spot_price: Current spot price
            method: "percentage" or "atm_offset"
            strike_type: "otm" or "itm" (only for percentage)
            value: Percentage (1-50) or offset (1-10)
            asset: "BTC" or "ETH"
        
        Returns:
            (call_strike, put_strike)
        """
        try:
            if method == "percentage":
                pct = value / 100
                
                if strike_type == "otm":
                    # OTM: Call above spot, Put below spot
                    call_strike = spot_price * (1 + pct)
                    put_strike = spot_price * (1 - pct)
                else:  # itm
                    # ITM: Call below spot, Put above spot (unusual)
                    call_strike = spot_price * (1 - pct)
                    put_strike = spot_price * (1 + pct)
                
                bot_logger.info(f"Calculated {strike_type.upper()} strikes with {value}%:")
                bot_logger.info(f"  Call: ${call_strike:.2f}")
                bot_logger.info(f"  Put: ${put_strike:.2f}")
            
            elif method == "atm_offset":
                # Strike intervals based on asset
                strike_interval = 1000 if asset == "BTC" else 50
                
                # Round spot to nearest strike
                atm_strike = round(spot_price / strike_interval) * strike_interval
                
                # Apply offset
                call_strike = atm_strike + (value * strike_interval)
                put_strike = atm_strike - (value * strike_interval)
                
                bot_logger.info(f"Calculated ATM±{value} strikes:")
                bot_logger.info(f"  ATM: ${atm_strike:.2f}")
                bot_logger.info(f"  Call: ${call_strike:.2f} (+{value})")
                bot_logger.info(f"  Put: ${put_strike:.2f} (-{value})")
            
            else:
                raise ValueError(f"Invalid strike method: {method}")
            
            return (call_strike, put_strike)
        
        except Exception as e:
            bot_logger.error(f"Error calculating strikes: {e}")
            raise
    
    @staticmethod
    def find_nearest_strikes(
        target_call: float,
        target_put: float,
        option_chain: List[Dict],
        expiry: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Find the nearest available strikes in option chain
        
        Args:
            target_call: Target call strike
            target_put: Target put strike
            option_chain: List of available options
            expiry: Expiry date (e.g., "111025")
        
        Returns:
            (call_symbol, put_symbol)
        """
        try:
            # Filter options by expiry
            expiry_options = [
                opt for opt in option_chain
                if expiry in opt.get('symbol', '')
            ]
            
            if not expiry_options:
                bot_logger.error(f"No options found for expiry: {expiry}")
                return (None, None)
            
            # Separate calls and puts
            calls = [opt for opt in expiry_options if opt.get('symbol', '').startswith('C-')]
            puts = [opt for opt in expiry_options if opt.get('symbol', '').startswith('P-')]
            
            # Find nearest call
            call_symbol = None
            min_call_diff = float('inf')
            
            for call in calls:
                strike = float(call.get('strike_price', 0))
                diff = abs(strike - target_call)
                if diff < min_call_diff:
                    min_call_diff = diff
                    call_symbol = call.get('symbol')
            
            # Find nearest put
            put_symbol = None
            min_put_diff = float('inf')
            
            for put in puts:
                strike = float(put.get('strike_price', 0))
                diff = abs(strike - target_put)
                if diff < min_put_diff:
                    min_put_diff = diff
                    put_symbol = put.get('symbol')
            
            bot_logger.info(f"Found nearest strikes:")
            bot_logger.info(f"  Call: {call_symbol}")
            bot_logger.info(f"  Put: {put_symbol}")
            
            return (call_symbol, put_symbol)
        
        except Exception as e:
            bot_logger.error(f"Error finding nearest strikes: {e}")
            return (None, None)
    
    @staticmethod
    def calculate_stop_loss(
        entry_price: float,
        trigger_method: str,
        trigger_value: float,
        limit_method: str,
        limit_value: float,
        direction: str
    ) -> Tuple[float, float]:
        """
        Calculate stop-loss trigger and limit prices
        
        Args:
            entry_price: Total entry cost (call + put premium)
            trigger_method: "percentage", "numerical", or "multiple"
            trigger_value: Value for trigger
            limit_method: Same as trigger_method
            limit_value: Value for limit
            direction: "long" or "short"
        
        Returns:
            (trigger_price, limit_price)
        """
        try:
            # For long strangle: SL triggers when price increases (loss)
            # For short strangle: SL triggers when price increases (loss)
            
            # Calculate trigger
            if trigger_method == "percentage":
                trigger = entry_price * (1 + trigger_value / 100)
            elif trigger_method == "numerical":
                trigger = entry_price + trigger_value
            else:  # multiple
                trigger = entry_price * trigger_value
            
            # Calculate limit
            if limit_method == "percentage":
                limit = entry_price * (1 + limit_value / 100)
            elif limit_method == "numerical":
                limit = entry_price + limit_value
            else:  # multiple
                limit = entry_price * limit_value
            
            bot_logger.info(f"Calculated stop-loss:")
            bot_logger.info(f"  Entry: ${entry_price:.2f}")
            bot_logger.info(f"  Trigger: ${trigger:.2f}")
            bot_logger.info(f"  Limit: ${limit:.2f}")
            
            return (trigger, limit)
        
        except Exception as e:
            bot_logger.error(f"Error calculating stop-loss: {e}")
            raise
              
