from datetime import datetime
from typing import Optional, Dict, Any

class UserModel:
    @staticmethod
    def create(telegram_id: int, username: str, first_name: str) -> Dict[str, Any]:
        return {
            'telegram_id': telegram_id,
            'username': username,
            'first_name': first_name,
            'created_at': datetime.utcnow(),
            'is_active': True,
            'daily_loss_limit_pct': 10.0,
            'max_loss_per_trade_pct': 5.0
        }

class APICredentialModel:
    @staticmethod
    def create(user_id: str, nickname: str, api_key_encrypted: bytes, 
               api_secret_encrypted: bytes) -> Dict[str, Any]:
        return {
            'user_id': user_id,
            'nickname': nickname,
            'api_key_encrypted': api_key_encrypted,
            'api_secret_encrypted': api_secret_encrypted,
            'is_active': True,
            'created_at': datetime.utcnow()
        }

class StrategyModel:
    @staticmethod
    def create(user_id: str, api_id: str, name: str, strategy_type: str,
               lot_size: int, direction: str, **kwargs) -> Dict[str, Any]:
        base = {
            'user_id': user_id,
            'api_id': api_id,
            'name': name,
            'strategy_type': strategy_type,  # 'straddle' or 'strangle'
            'lot_size': lot_size,
            'direction': direction,  # 'long' or 'short'
            'stop_loss_pct': kwargs.get('stop_loss_pct', 20.0),
            'target_pct': kwargs.get('target_pct'),
            'expiry_type': kwargs.get('expiry_type', 'weekly'),
            'strike_offset': kwargs.get('strike_offset', 0),
            'max_capital': kwargs.get('max_capital'),
            'trailing_sl': kwargs.get('trailing_sl', False),
            'created_at': datetime.utcnow()
        }
        
        # Add strangle-specific fields
        if strategy_type == 'strangle':
            base.update({
                'call_strike_offset': kwargs.get('call_strike_offset', 2),
                'put_strike_offset': kwargs.get('put_strike_offset', 2),
                'strike_selection_method': kwargs.get('strike_selection_method', 'fixed_distance'),
                'percentage_move': kwargs.get('percentage_move', 5.0),
                'min_premium_ratio': kwargs.get('min_premium_ratio', 0.3),
                'max_premium_ratio': kwargs.get('max_premium_ratio', 0.7)
            })
        
        return base

class TradeModel:
    @staticmethod
    def create(user_id: str, api_id: str, strategy_id: str, strategy_type: str,
               call_symbol: str, put_symbol: str, strike: float, **kwargs) -> Dict[str, Any]:
        return {
            'user_id': user_id,
            'api_id': api_id,
            'strategy_id': strategy_id,
            'strategy_type': strategy_type,
            'call_symbol': call_symbol,
            'put_symbol': put_symbol,
            'atm_strike': kwargs.get('atm_strike'),
            'call_strike': kwargs.get('call_strike', strike),
            'put_strike': kwargs.get('put_strike', strike),
            'spot_at_entry': kwargs.get('spot_at_entry'),
            'entry_time': datetime.utcnow(),
            'exit_time': None,
            'call_entry_price': kwargs.get('call_entry_price'),
            'put_entry_price': kwargs.get('put_entry_price'),
            'call_exit_price': None,
            'put_exit_price': None,
            'lot_size': kwargs.get('lot_size'),
            'pnl': 0.0,
            'status': 'active',  # active, closed, partial
            'stop_loss_pct': kwargs.get('stop_loss_pct'),
            'target_pct': kwargs.get('target_pct'),
            'upper_breakeven': kwargs.get('upper_breakeven'),
            'lower_breakeven': kwargs.get('lower_breakeven')
        }
                   
