from typing import List, Dict, Optional
from trading.delta_api import DeltaExchangeAPI
from database.crud import TradeCRUD
from utils.helpers import calculate_pnl
import logging
import asyncio

logger = logging.getLogger(__name__)

class PositionMonitor:
    def __init__(self, api: DeltaExchangeAPI):
        self.api = api
        self.trade_crud = TradeCRUD()

    def get_active_positions_details(self) -> Optional[List[Dict]]:
        """Fetch all active positions with details"""
        positions = self.api.get_positions()
        if not positions:
            return []
        
        detailed_positions = []
        
        for position in positions:
            if float(position.get('size', 0)) == 0:
                continue
            
            product_id = position.get('product_id')
            symbol = position.get('symbol')
            size = float(position.get('size', 0))
            entry_price = float(position.get('entry_price', 0))
            
            # Get current market price
            ticker = self.api.get_ticker(symbol)
            current_price = float(ticker.get('mark_price', 0)) if ticker else 0
            
            # Calculate unrealized P&L
            if size > 0:  # Long position
                unrealized_pnl = (current_price - entry_price) * abs(size)
            else:  # Short position
                unrealized_pnl = (entry_price - current_price) * abs(size)
            
            detailed_positions.append({
                'product_id': product_id,
                'symbol': symbol,
                'size': size,
                'entry_price': entry_price,
                'current_price': current_price,
                'unrealized_pnl': unrealized_pnl,
                'pnl_percentage': (unrealized_pnl / (entry_price * abs(size))) * 100 if entry_price > 0 else 0
            })
        
        return detailed_positions

    def check_stop_loss_target(self, trade_id: str, stop_loss_pct: float, 
                              target_pct: Optional[float] = None) -> Optional[str]:
        """Check if stop loss or target hit"""
        trade = self.trade_crud.get_trade_by_id(trade_id)
        if not trade or trade['status'] != 'active':
            return None
        
        call_symbol = trade['call_symbol']
        put_symbol = trade['put_symbol']
        call_entry = trade['call_entry_price']
        put_entry = trade['put_entry_price']
        lot_size = trade['lot_size']
        direction = trade.get('direction', 'long')
        
        # Get current prices
        call_ticker = self.api.get_ticker(call_symbol)
        put_ticker = self.api.get_ticker(put_symbol)
        
        if not call_ticker or not put_ticker:
            return None
        
        call_current = float(call_ticker.get('mark_price', 0))
        put_current = float(put_ticker.get('mark_price', 0))
        
        # Calculate current P&L
        current_pnl = calculate_pnl(call_entry, put_entry, call_current, 
                                    put_current, lot_size, direction)
        
        entry_cost = (call_entry + put_entry) * lot_size
        pnl_pct = (current_pnl / entry_cost) * 100 if entry_cost > 0 else 0
        
        # Check stop loss
        if pnl_pct <= -stop_loss_pct:
            return 'stop_loss'
        
        # Check target
        if target_pct and pnl_pct >= target_pct:
            return 'target'
        
        return None

    def monitor_all_active_trades(self, user_id: str, stop_loss_pct: float, 
                                  target_pct: Optional[float] = None) -> List[Dict]:
        """Monitor all active trades for a user"""
        active_trades = self.trade_crud.get_active_trades(user_id)
        alerts = []
        
        for trade in active_trades:
            trade_id = str(trade['_id'])
            trigger = self.check_stop_loss_target(trade_id, stop_loss_pct, target_pct)
            
            if trigger:
                alerts.append({
                    'trade_id': trade_id,
                    'trigger': trigger,
                    'trade': trade
                })
        
        return alerts
                                      
