from typing import Dict, List, Optional, Callable
from trading.delta_api import DeltaExchangeAPI
from utils.logger import trade_logger
import asyncio


class PositionMonitor:
    """Monitor positions and trigger alerts"""
    
    def __init__(self, api: DeltaExchangeAPI):
        self.api = api
        self.monitoring_tasks = {}
    
    async def get_position_pnl(self, symbol: str) -> Optional[float]:
        """Get current P&L for a position"""
        try:
            positions = await self.api.get_positions(symbol)
            
            if 'result' in positions and positions['result']:
                position = positions['result'][0]
                return float(position.get('realized_pnl', 0)) + float(position.get('unrealized_pnl', 0))
            
            return None
        
        except Exception as e:
            trade_logger.error(f"Error fetching position P&L: {e}")
            return None
    
    async def get_position_details(self, symbol: str) -> Optional[Dict]:
        """Get detailed position information"""
        try:
            positions = await self.api.get_positions(symbol)
            
            if 'result' in positions and positions['result']:
                position = positions['result'][0]
                
                return {
                    "symbol": position.get('product_symbol'),
                    "size": int(position.get('size', 0)),
                    "entry_price": float(position.get('entry_price', 0)),
                    "mark_price": float(position.get('mark_price', 0)),
                    "unrealized_pnl": float(position.get('unrealized_pnl', 0)),
                    "realized_pnl": float(position.get('realized_pnl', 0)),
                    "margin": float(position.get('margin', 0)),
                    "liquidation_price": float(position.get('liquidation_price', 0))
                }
            
            return None
        
        except Exception as e:
            trade_logger.error(f"Error fetching position details: {e}")
            return None
    
    async def get_all_positions(self) -> List[Dict]:
        """Get all open positions"""
        try:
            positions = await self.api.get_positions()
            
            if 'result' in positions:
                return [
                    {
                        "symbol": pos.get('product_symbol'),
                        "size": int(pos.get('size', 0)),
                        "entry_price": float(pos.get('entry_price', 0)),
                        "unrealized_pnl": float(pos.get('unrealized_pnl', 0)),
                        "realized_pnl": float(pos.get('realized_pnl', 0))
                    }
                    for pos in positions['result']
                    if int(pos.get('size', 0)) != 0
                ]
            
            return []
        
        except Exception as e:
            trade_logger.error(f"Error fetching all positions: {e}")
            return []
    
    async def monitor_straddle_position(
        self,
        trade_id: str,
        call_symbol: str,
        put_symbol: str,
        entry_premium: float,
        stop_loss_pct: float,
        target_pct: Optional[float] = None,
        callback: Optional[Callable] = None,
        poll_interval: int = 30
    ):
        """Monitor straddle position and trigger alerts on SL/Target hit"""
        try:
            trade_logger.info(f"Starting position monitor for trade {trade_id}")
            
            stop_loss_level = entry_premium * (1 - stop_loss_pct / 100)
            target_level = entry_premium * (1 + target_pct / 100) if target_pct else None
            
            while True:
                # Get current position values
                call_pos = await self.get_position_details(call_symbol)
                put_pos = await self.get_position_details(put_symbol)
                
                if not call_pos or not put_pos:
                    trade_logger.warning(f"Position closed or not found for trade {trade_id}")
                    break
                
                # Calculate current straddle premium
                current_premium = call_pos['mark_price'] + put_pos['mark_price']
                
                # Calculate total P&L
                total_pnl = call_pos['unrealized_pnl'] + put_pos['unrealized_pnl']
                
                trade_logger.info(
                    f"Trade {trade_id} - Current Premium: {current_premium}, "
                    f"Entry: {entry_premium}, P&L: {total_pnl}"
                )
                
                # Check stop loss
                if current_premium <= stop_loss_level:
                    trade_logger.warning(f"Stop loss hit for trade {trade_id}")
                    if callback:
                        await callback({
                            "type": "stop_loss",
                            "trade_id": trade_id,
                            "current_premium": current_premium,
                            "pnl": total_pnl
                        })
                    break
                
                # Check target
                if target_level and current_premium >= target_level:
                    trade_logger.info(f"Target hit for trade {trade_id}")
                    if callback:
                        await callback({
                            "type": "target",
                            "trade_id": trade_id,
                            "current_premium": current_premium,
                            "pnl": total_pnl
                        })
                    break
                
                await asyncio.sleep(poll_interval)
        
        except asyncio.CancelledError:
            trade_logger.info(f"Position monitor cancelled for trade {trade_id}")
        except Exception as e:
            trade_logger.error(f"Error in position monitor: {e}")
    
    def start_monitoring(
        self,
        trade_id: str,
        call_symbol: str,
        put_symbol: str,
        entry_premium: float,
        stop_loss_pct: float,
        target_pct: Optional[float] = None,
        callback: Optional[Callable] = None
    ):
        """Start monitoring position in background task"""
        task = asyncio.create_task(
            self.monitor_straddle_position(
                trade_id, call_symbol, put_symbol,
                entry_premium, stop_loss_pct, target_pct, callback
            )
        )
        self.monitoring_tasks[trade_id] = task
        trade_logger.info(f"Started background monitoring for trade {trade_id}")
    
    def stop_monitoring(self, trade_id: str):
        """Stop monitoring a specific position"""
        if trade_id in self.monitoring_tasks:
            self.monitoring_tasks[trade_id].cancel()
            del self.monitoring_tasks[trade_id]
            trade_logger.info(f"Stopped monitoring for trade {trade_id}")
    
    def stop_all_monitoring(self):
        """Stop all monitoring tasks"""
        for trade_id in list(self.monitoring_tasks.keys()):
            self.stop_monitoring(trade_id)
        trade_logger.info("Stopped all monitoring tasks")
    
    async def calculate_straddle_pnl(
        self,
        call_entry: float,
        put_entry: float,
        call_exit: float,
        put_exit: float,
        lot_size: int,
        is_long: bool
    ) -> float:
        """Calculate straddle P&L"""
        if is_long:
            # Long straddle: profit when exit > entry
            call_pnl = (call_exit - call_entry) * lot_size
            put_pnl = (put_exit - put_entry) * lot_size
        else:
            # Short straddle: profit when entry > exit
            call_pnl = (call_entry - call_exit) * lot_size
            put_pnl = (put_entry - put_exit) * lot_size
        
        total_pnl = call_pnl + put_pnl
        return round(total_pnl, 2)
      
