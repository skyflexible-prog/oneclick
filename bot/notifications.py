# bot/notifications.py - FIXED VERSION

from telegram import Bot
from telegram.constants import ParseMode
from config.database import Database
from utils.logger import bot_logger
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class NotificationService:
    """Service for sending trading notifications"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
    
    async def send_order_fill_notification(
        self, 
        user_id: int, 
        order: Dict, 
        fill_type: str = "ENTRY"
    ):
        """Send notification when an order is filled"""
        try:
            # ✅ FIXED: Map fields from stored order data
            symbol = order.get('symbol', 'N/A')
            side = order.get('side', 'N/A').upper()
            price = float(order.get('price') or 0)
            size = int(order.get('size') or 0)
            order_type = order.get('order_type', 'N/A')
            
            # Log for debugging
            bot_logger.info(f"Notification data: symbol={symbol}, side={side}, price={price}, size={size}, type={order_type}")
            
            # Determine emoji based on fill type
            emoji_map = {
                "ENTRY": "🎯",
                "STOP_LOSS": "🛑",
                "TAKE_PROFIT": "💰"
            }
            emoji = emoji_map.get(fill_type, "📊")
            
            # Build notification message
            if fill_type == "ENTRY":
                message = f"{emoji} <b>Order Filled - Entry</b>\n\n"
                message += f"<b>Symbol:</b> {symbol}\n"
                message += f"<b>Side:</b> {side}\n"
                message += f"<b>Fill Price:</b> ${price:.2f}\n"
                message += f"<b>Size:</b> {size}\n"
                message += f"<b>Type:</b> {order_type}\n"
                message += f"<b>Time:</b> {datetime.utcnow().strftime('%H:%M:%S UTC')}"
                
            elif fill_type == "STOP_LOSS":
                message = f"{emoji} <b>Stop-Loss Triggered</b>\n\n"
                message += f"<b>Symbol:</b> {symbol}\n"
                message += f"<b>Side:</b> {side}\n"
                message += f"<b>Fill Price:</b> ${price:.2f}\n"
                message += f"<b>Size:</b> {size}\n"
                message += f"<b>Time:</b> {datetime.utcnow().strftime('%H:%M:%S UTC')}\n\n"
                message += "⚠️ <i>Position closed by stop-loss</i>"
                
            elif fill_type == "TAKE_PROFIT":
                message = f"{emoji} <b>Take-Profit Hit!</b>\n\n"
                message += f"<b>Symbol:</b> {symbol}\n"
                message += f"<b>Side:</b> {side}\n"
                message += f"<b>Fill Price:</b> ${price:.2f}\n"
                message += f"<b>Size:</b> {size}\n"
                message += f"<b>Time:</b> {datetime.utcnow().strftime('%H:%M:%S UTC')}\n\n"
                message += "🎉 <i>Target reached!</i>"
            
            # Send notification
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
            
            bot_logger.info(f"✅ Order fill notification sent to user {user_id}: {fill_type}")
            
        except Exception as e:
            bot_logger.error(f"❌ Error sending order fill notification: {e}")
            import traceback
            bot_logger.error(traceback.format_exc())


class OrderFillTracker:
    """Track order states and detect fills"""
    
    @staticmethod
    async def check_order_fills(user_id: int, api_id: str, current_orders: List[Dict]):
        """Check for order fills by comparing current orders with stored state"""
        try:
            db = Database.get_database()
            
            # Get stored order states
            stored_orders = await db.order_states.find({
                'user_id': user_id,
                'api_id': api_id,
                'state': 'pending'
            }).to_list(None)
            
            bot_logger.info(f"Found {len(stored_orders)} pending orders in database")
            
            filled_orders = []
            
            # Check which orders are no longer in current orders
            stored_order_ids = {order['order_id'] for order in stored_orders}
            current_order_ids = {order.get('id') for order in current_orders}
            
            potentially_filled = stored_order_ids - current_order_ids
            
            bot_logger.info(f"Potentially filled orders: {potentially_filled}")
            
            for filled_id in potentially_filled:
                stored_order = next(
                    (o for o in stored_orders if o['order_id'] == filled_id), 
                    None
                )
                
                if stored_order:
                    # Mark as filled
                    await db.order_states.update_one(
                        {'_id': stored_order['_id']},
                        {
                            '$set': {
                                'state': 'filled',
                                'filled_at': datetime.utcnow()
                            }
                        }
                    )
                    
                    filled_orders.append(stored_order)
                    bot_logger.info(f"✅ Detected filled order: {filled_id} - {stored_order.get('symbol')}")
            
            # Update/insert current order states (minimal data)
            for order in current_orders:
                order_id = order.get('id')
                symbol = order.get('product_symbol')
                
                await db.order_states.update_one(
                    {
                        'user_id': user_id,
                        'api_id': api_id,
                        'order_id': order_id
                    },
                    {
                        '$set': {
                            'user_id': user_id,
                            'api_id': api_id,
                            'order_id': order_id,
                            'state': order.get('state', 'pending'),
                            'order_type': order.get('stop_order_type', 'entry'),
                            'symbol': symbol,
                            'side': order.get('side'),
                            'size': order.get('size'),
                            'price': order.get('stop_price') or order.get('limit_price') or order.get('average_fill_price'),
                            'reduce_only': order.get('reduce_only', False),
                            'updated_at': datetime.utcnow()
                        }
                    },
                    upsert=True
                )
                
                bot_logger.info(f"📝 Updated order state: {order_id} - {symbol}")
            
            return filled_orders
            
        except Exception as e:
            bot_logger.error(f"❌ Error checking order fills: {e}")
            import traceback
            bot_logger.error(traceback.format_exc())
            return []
    
    @staticmethod
    def determine_fill_type(order: Dict) -> str:
        """Determine if order is entry, stop-loss, or take-profit"""
        order_type = order.get('order_type', '')
        reduce_only = order.get('reduce_only', False)
        
        bot_logger.info(f"Determining fill type: order_type={order_type}, reduce_only={reduce_only}")
        
        if reduce_only:
            if 'stop_loss' in order_type.lower():
                return "STOP_LOSS"
            elif 'take_profit' in order_type.lower():
                return "TAKE_PROFIT"
            else:
                return "STOP_LOSS"
        else:
            return "ENTRY"
            
