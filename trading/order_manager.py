from typing import Dict, Optional
from trading.delta_api import DeltaExchangeAPI
from utils.logger import trade_logger
import asyncio


class OrderManager:
    """Manage order lifecycle and tracking"""
    
    def __init__(self, api: DeltaExchangeAPI):
        self.api = api
    
    async def wait_for_order_fill(
        self,
        order_id: str,
        timeout: int = 60,
        poll_interval: int = 2
    ) -> Dict:
        """Wait for order to be filled"""
        elapsed = 0
        
        while elapsed < timeout:
            try:
                order = await self.api.get_order(order_id)
                
                if 'result' in order:
                    order_data = order['result']
                    status = order_data.get('state', '')
                    
                    if status == 'filled':
                        trade_logger.info(f"Order {order_id} filled")
                        return {
                            "status": "filled",
                            "fill_price": float(order_data.get('average_fill_price', 0)),
                            "filled_size": int(order_data.get('size', 0)),
                            "order": order_data
                        }
                    elif status in ['cancelled', 'rejected']:
                        trade_logger.warning(f"Order {order_id} {status}")
                        return {
                            "status": status,
                            "order": order_data
                        }
                
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
            
            except Exception as e:
                trade_logger.error(f"Error checking order status: {e}")
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
        
        trade_logger.warning(f"Order {order_id} fill timeout")
        return {"status": "timeout"}
    
    async def place_stop_loss_order(
        self,
        symbol: str,
        side: str,
        size: int,
        stop_price: float
    ) -> Dict:
        """Place stop loss order"""
        try:
            result = await self.api.place_order(
                symbol=symbol,
                side=side,
                order_type="stop_market_order",
                size=size,
                stop_price=stop_price,
                reduce_only=True
            )
            
            if 'error' not in result:
                trade_logger.info(f"Stop loss order placed: {symbol} at {stop_price}")
            
            return result
        
        except Exception as e:
            trade_logger.error(f"Error placing stop loss: {e}")
            return {"error": str(e)}
    
    async def place_take_profit_order(
        self,
        symbol: str,
        side: str,
        size: int,
        limit_price: float
    ) -> Dict:
        """Place take profit order"""
        try:
            result = await self.api.place_order(
                symbol=symbol,
                side=side,
                order_type="limit_order",
                size=size,
                limit_price=limit_price,
                reduce_only=True,
                post_only=True
            )
            
            if 'error' not in result:
                trade_logger.info(f"Take profit order placed: {symbol} at {limit_price}")
            
            return result
        
        except Exception as e:
            trade_logger.error(f"Error placing take profit: {e}")
            return {"error": str(e)}
    
    async def modify_order(
        self,
        order_id: str,
        new_size: Optional[int] = None,
        new_price: Optional[float] = None
    ) -> Dict:
        """Modify existing order"""
        try:
            data = {}
            if new_size:
                data['size'] = new_size
            if new_price:
                data['limit_price'] = str(new_price)
            
            # Note: Delta API might not support order modification
            # This is a placeholder - check actual API capabilities
            trade_logger.info(f"Attempting to modify order {order_id}")
            
            # You may need to cancel and replace instead
            return {"error": "Order modification not supported - use cancel and replace"}
        
        except Exception as e:
            trade_logger.error(f"Error modifying order: {e}")
            return {"error": str(e)}
    
    async def cancel_order_safe(self, order_id: str) -> Dict:
        """Safely cancel order with error handling"""
        try:
            result = await self.api.cancel_order(order_id)
            
            if 'error' not in result:
                trade_logger.info(f"Order {order_id} cancelled successfully")
            else:
                trade_logger.warning(f"Failed to cancel order {order_id}: {result.get('error')}")
            
            return result
        
        except Exception as e:
            trade_logger.error(f"Error cancelling order: {e}")
            return {"error": str(e)}
    
    async def get_order_status(self, order_id: str) -> Optional[str]:
        """Get current order status"""
        try:
            order = await self.api.get_order(order_id)
            
            if 'result' in order:
                return order['result'].get('state')
            
            return None
        
        except Exception as e:
            trade_logger.error(f"Error fetching order status: {e}")
            return None
    
    async def get_fill_price(self, order_id: str) -> Optional[float]:
        """Get average fill price for order"""
        try:
            order = await self.api.get_order(order_id)
            
            if 'result' in order:
                return float(order['result'].get('average_fill_price', 0))
            
            return None
        
        except Exception as e:
            trade_logger.error(f"Error fetching fill price: {e}")
            return None


class BracketOrderManager:
    """Manage bracket orders (entry + SL + TP)"""
    
    def __init__(self, api: DeltaExchangeAPI):
        self.api = api
        self.order_manager = OrderManager(api)
    
    async def place_bracket(
        self,
        symbol: str,
        side: str,
        size: int,
        entry_type: str = "market",
        entry_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Dict:
        """Place bracket order with entry, stop loss, and take profit"""
        try:
            # Place entry order
            if entry_type == "market":
                entry_order = await self.api.place_market_order(symbol, side, size)
            else:
                if not entry_price:
                    return {"success": False, "error": "Entry price required for limit order"}
                entry_order = await self.api.place_limit_order(symbol, side, size, entry_price)
            
            if 'error' in entry_order:
                return {"success": False, "error": "Entry order failed", "details": entry_order}
            
            entry_id = entry_order['result']['id']
            
            # Wait for entry order fill
            fill_result = await self.order_manager.wait_for_order_fill(entry_id)
            
            if fill_result['status'] != 'filled':
                return {"success": False, "error": "Entry order not filled", "details": fill_result}
            
            # Place stop loss and take profit
            exit_side = "sell" if side == "buy" else "buy"
            
            sl_order = None
            tp_order = None
            
            if stop_loss:
                sl_order = await self.order_manager.place_stop_loss_order(
                    symbol, exit_side, size, stop_loss
                )
            
            if take_profit:
                tp_order = await self.order_manager.place_take_profit_order(
                    symbol, exit_side, size, take_profit
                )
            
            return {
                "success": True,
                "entry_order": entry_order['result'],
                "fill_price": fill_result['fill_price'],
                "stop_loss_order": sl_order.get('result') if sl_order and 'error' not in sl_order else None,
                "take_profit_order": tp_order.get('result') if tp_order and 'error' not in tp_order else None
            }
        
        except Exception as e:
            trade_logger.error(f"Error placing bracket order: {e}")
            return {"success": False, "error": str(e)}
    
    async def cancel_bracket(
        self,
        entry_id: Optional[str] = None,
        sl_id: Optional[str] = None,
        tp_id: Optional[str] = None
    ) -> Dict:
        """Cancel all orders in bracket"""
        results = {}
        
        if entry_id:
            results['entry_cancelled'] = await self.order_manager.cancel_order_safe(entry_id)
        
        if sl_id:
            results['sl_cancelled'] = await self.order_manager.cancel_order_safe(sl_id)
        
        if tp_id:
            results['tp_cancelled'] = await self.order_manager.cancel_order_safe(tp_id)
        
        return results
      
