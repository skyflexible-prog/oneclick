from typing import Optional, Dict, Tuple
from trading.delta_api import DeltaExchangeAPI
from utils.helpers import round_to_strike, calculate_breakeven
import logging

logger = logging.getLogger(__name__)

class StraddleStrategy:
    def __init__(self, api: DeltaExchangeAPI):
        self.api = api

    def find_atm_strike(self, spot_price: float, strike_interval: float = 500) -> float:
        """Find nearest ATM strike price"""
        return round_to_strike(spot_price, strike_interval)

    def get_option_chain(self, underlying: str = 'BTC', expiry_type: str = 'weekly') -> Optional[Dict]:
        """Fetch and organize option chain"""
        products = self.api.get_products()
        if not products:
            return None

        # Filter by underlying and expiry type
        options = {
            'calls': [],
            'puts': []
        }

        for product in products:
            symbol = product.get('symbol', '')
            if underlying.upper() not in symbol.upper():
                continue

            contract_type = product.get('contract_type', '')
            if contract_type == 'call_options':
                options['calls'].append(product)
            elif contract_type == 'put_options':
                options['puts'].append(product)

        return options

    def find_atm_options(self, spot_price: float, underlying: str = 'BTC', 
                        expiry_type: str = 'weekly') -> Optional[Tuple[Dict, Dict]]:
        """Find ATM call and put options"""
        atm_strike = self.find_atm_strike(spot_price)
        option_chain = self.get_option_chain(underlying, expiry_type)
        
        if not option_chain:
            logger.error("Failed to fetch option chain")
            return None

        # Find matching call and put at ATM strike
        atm_call = None
        atm_put = None

        for call in option_chain['calls']:
            if abs(float(call.get('strike_price', 0)) - atm_strike) < 1:
                atm_call = call
                break

        for put in option_chain['puts']:
            if abs(float(put.get('strike_price', 0)) - atm_strike) < 1:
                atm_put = put
                break

        if atm_call and atm_put:
            logger.info(f"Found ATM options at strike {atm_strike}")
            return atm_call, atm_put
        
        logger.error(f"Could not find ATM options at strike {atm_strike}")
        return None

    def get_option_premium(self, symbol: str) -> Optional[float]:
        """Get current option premium"""
        ticker = self.api.get_ticker(symbol)
        if ticker and 'mark_price' in ticker:
            return float(ticker['mark_price'])
        return None

    def calculate_straddle_details(self, call_option: Dict, put_option: Dict, 
                                   lot_size: int, direction: str) -> Dict:
        """Calculate straddle trade details"""
        call_premium = self.get_option_premium(call_option['symbol'])
        put_premium = self.get_option_premium(put_option['symbol'])
        
        if not call_premium or not put_premium:
            return None

        strike = float(call_option['strike_price'])
        total_premium = call_premium + put_premium
        total_cost = total_premium * lot_size

        upper_be, lower_be = calculate_breakeven(strike, strike, total_premium, direction)

        return {
            'call_symbol': call_option['symbol'],
            'put_symbol': put_option['symbol'],
            'call_product_id': call_option['id'],
            'put_product_id': put_option['id'],
            'strike': strike,
            'call_premium': call_premium,
            'put_premium': put_premium,
            'total_premium': total_premium,
            'total_cost': total_cost,
            'upper_breakeven': upper_be,
            'lower_breakeven': lower_be,
            'lot_size': lot_size,
            'direction': direction
        }

    def execute_straddle(self, call_product_id: int, put_product_id: int, 
                        lot_size: int, direction: str) -> Tuple[Optional[Dict], Optional[Dict]]:
        """Execute both legs of straddle"""
        side = 'buy' if direction == 'long' else 'sell'
        
        # Place call order
        call_order = self.api.place_order(call_product_id, lot_size, side)
        if not call_order:
            logger.error("Failed to place call order")
            return None, None

        # Place put order
        put_order = self.api.place_order(put_product_id, lot_size, side)
        if not put_order:
            logger.error("Failed to place put order, attempting to cancel call order")
            # Attempt rollback
            reverse_side = 'sell' if side == 'buy' else 'buy'
            self.api.place_order(call_product_id, lot_size, reverse_side)
            return None, None

        logger.info(f"Successfully executed {direction} straddle")
        return call_order, put_order

    def validate_margin(self, total_cost: float) -> bool:
        """Validate sufficient margin for trade"""
        balance = self.api.get_wallet_balance()
        if not balance:
            return False

        available_balance = float(balance[0].get('available_balance', 0))
        return available_balance >= total_cost * 1.2  # 20% buffer
