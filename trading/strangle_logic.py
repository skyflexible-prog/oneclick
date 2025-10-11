from typing import Optional, Dict, Tuple, List
from trading.delta_api import DeltaExchangeAPI
from utils.helpers import round_to_strike, calculate_breakeven
import logging

logger = logging.getLogger(__name__)

class StrangleStrategy:
    def __init__(self, api: DeltaExchangeAPI):
        self.api = api

    def find_atm_strike(self, spot_price: float, strike_interval: float = 500) -> float:
        """Find nearest ATM strike price"""
        return round_to_strike(spot_price, strike_interval)

    def calculate_otm_strikes(self, atm_strike: float, call_offset: int, 
                            put_offset: int, strike_interval: float = 500) -> Tuple[float, float]:
        """Calculate OTM call and put strikes"""
        call_strike = atm_strike + (call_offset * strike_interval)
        put_strike = atm_strike - (put_offset * strike_interval)
        return call_strike, put_strike

    def get_option_chain(self, underlying: str = 'BTC', expiry_type: str = 'weekly') -> Optional[Dict]:
        """Fetch and organize option chain"""
        products = self.api.get_products()
        if not products:
            return None

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

    def find_otm_options(self, call_strike: float, put_strike: float, 
                        underlying: str = 'BTC', expiry_type: str = 'weekly') -> Optional[Tuple[Dict, Dict]]:
        """Find OTM call and put options at specified strikes"""
        option_chain = self.get_option_chain(underlying, expiry_type)
        
        if not option_chain:
            logger.error("Failed to fetch option chain")
            return None

        otm_call = None
        otm_put = None

        # Find matching call at OTM strike
        for call in option_chain['calls']:
            if abs(float(call.get('strike_price', 0)) - call_strike) < 1:
                otm_call = call
                break

        # Find matching put at OTM strike
        for put in option_chain['puts']:
            if abs(float(put.get('strike_price', 0)) - put_strike) < 1:
                otm_put = put
                break

        if otm_call and otm_put:
            logger.info(f"Found OTM options: Call@{call_strike}, Put@{put_strike}")
            return otm_call, otm_put
        
        logger.error(f"Could not find OTM options at specified strikes")
        return None

    def get_option_premium(self, symbol: str) -> Optional[float]:
        """Get current option premium"""
        ticker = self.api.get_ticker(symbol)
        if ticker and 'mark_price' in ticker:
            return float(ticker['mark_price'])
        return None

    def calculate_strangle_details(self, call_option: Dict, put_option: Dict, 
                                   atm_strike: float, lot_size: int, 
                                   direction: str, atm_straddle_premium: Optional[float] = None) -> Dict:
        """Calculate strangle trade details with comparison to straddle"""
        call_premium = self.get_option_premium(call_option['symbol'])
        put_premium = self.get_option_premium(put_option['symbol'])
        
        if not call_premium or not put_premium:
            return None

        call_strike = float(call_option['strike_price'])
        put_strike = float(put_option['strike_price'])
        total_premium = call_premium + put_premium
        total_cost = total_premium * lot_size

        upper_be, lower_be = calculate_breakeven(call_strike, put_strike, total_premium, direction)
        breakeven_range = upper_be - lower_be

        result = {
            'call_symbol': call_option['symbol'],
            'put_symbol': put_option['symbol'],
            'call_product_id': call_option['id'],
            'put_product_id': put_option['id'],
            'atm_strike': atm_strike,
            'call_strike': call_strike,
            'put_strike': put_strike,
            'call_premium': call_premium,
            'put_premium': put_premium,
            'total_premium': total_premium,
            'total_cost': total_cost,
            'upper_breakeven': upper_be,
            'lower_breakeven': lower_be,
            'breakeven_range': breakeven_range,
            'lot_size': lot_size,
            'direction': direction,
            'call_offset': int((call_strike - atm_strike) / 500),
            'put_offset': int((atm_strike - put_strike) / 500)
        }

        # Add comparison if ATM straddle premium provided
        if atm_straddle_premium:
            cost_savings_pct = ((atm_straddle_premium - total_premium) / atm_straddle_premium) * 100
            result['atm_straddle_premium'] = atm_straddle_premium
            result['cost_savings_pct'] = cost_savings_pct

        return result

    def execute_strangle(self, call_product_id: int, put_product_id: int, 
                        lot_size: int, direction: str) -> Tuple[Optional[Dict], Optional[Dict]]:
        """Execute both legs of strangle"""
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

        logger.info(f"Successfully executed {direction} strangle")
        return call_order, put_order

    def validate_margin(self, total_cost: float) -> bool:
        """Validate sufficient margin for trade"""
        balance = self.api.get_wallet_balance()
        if not balance:
            return False

        available_balance = float(balance[0].get('available_balance', 0))
        return available_balance >= total_cost * 1.2  # 20% buffer

    def compare_with_straddle(self, spot_price: float, call_offset: int, 
                             put_offset: int, underlying: str = 'BTC') -> Optional[Dict]:
        """Compare strangle with ATM straddle"""
        from trading.straddle_logic import StraddleStrategy
        
        straddle = StraddleStrategy(self.api)
        atm_strike = self.find_atm_strike(spot_price)
        
        # Get ATM straddle details
        atm_options = straddle.find_atm_options(spot_price, underlying)
        if not atm_options:
            return None
        
        atm_call, atm_put = atm_options
        atm_call_premium = self.get_option_premium(atm_call['symbol'])
        atm_put_premium = self.get_option_premium(atm_put['symbol'])
        atm_total = atm_call_premium + atm_put_premium
        
        # Get OTM strangle details
        call_strike, put_strike = self.calculate_otm_strikes(atm_strike, call_offset, put_offset)
        otm_options = self.find_otm_options(call_strike, put_strike, underlying)
        
        if not otm_options:
            return None
        
        otm_call, otm_put = otm_options
        otm_call_premium = self.get_option_premium(otm_call['symbol'])
        otm_put_premium = self.get_option_premium(otm_put['symbol'])
        otm_total = otm_call_premium + otm_put_premium
        
        cost_savings = ((atm_total - otm_total) / atm_total) * 100
        
        return {
            'straddle': {
                'strike': atm_strike,
                'total_premium': atm_total,
                'call_premium': atm_call_premium,
                'put_premium': atm_put_premium
            },
            'strangle': {
                'call_strike': call_strike,
                'put_strike': put_strike,
                'total_premium': otm_total,
                'call_premium': otm_call_premium,
                'put_premium': otm_put_premium
            },
            'cost_savings_pct': cost_savings,
            'cost_difference': atm_total - otm_total
        }
                               
