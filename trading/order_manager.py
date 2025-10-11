from typing import Optional, Dict, List
from trading.delta_api import DeltaExchangeAPI
import logging
import time

logger = logging.getLogger(__name__)

class OrderManager:
    def __init__(self, api: DeltaExchangeAPI):
        self.api = api

    def monitor_order_fill(self, order_id: int, max_wait_seconds: int = 30) -> Optional[Dict]:
        """Monitor order until filled or timeout"""
        start_time = time.time()
        
        while time.time() - start_time < max_wait_seconds:
            order_status = self.api.get_order_status(order_id)
            
            if not order_status:
                logger.error(f"Failed to fetch order status for {order_id}")
                return None
            
            state = order_status.get('state', '')
            
            if state in ['filled', 'closed']:
                logger.info(f"Order {order_id} filled")
                return order_status
            elif state in ['cancelled', 'rejected']:
                logger.warning(f"Order {order_id} {state}")
                return None
            
            time.sleep(1)
        
        logger.warning(f"Order {order_id} monitoring timeout")
        return None

    def close_position_by_product(self, product_id: int) -> Optional[Dict]:
        """Close a specific position"""
        return self.api.close_position(product_id)

    def get_fill_price(self, order: Dict) -> Optional[float]:
        """Extract average fill price from order"""
        if order and 'average_fill_price' in order:
            return float(order['average_fill_price'])
        return None

    def validate_order_execution(self, call_order: Dict, put_order: Dict) -> bool:
        """Validate both orders executed successfully"""
        if not call_order or not put_order:
            return False
        
        call_filled = call_order.get('state') in ['filled', 'closed']
        put_filled = put_order.get('state') in ['filled', 'closed']
        
        return call_filled and put_filled
        
