# bot/notifications.py - COMPLETE FIX

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
            # ✅ FIXED: Enhanced field extraction with multiple fallbacks
            symbol = order.get('symbol')
            if not symbol or symbol == 'N/A':
                symbol = order.get('product_symbol', 'Unknown')
            
            side = order.get('side')
            if not side or side == 'N/A':
                side = 'Unknown'
            side = side.upper()
            
            # Try multiple price fields with priority
            price = None
            for price_field in ['price', 'stop_price', 'limit_price', 'average_fill_price']:
                price = order.get(price_field)
                if price and float(price) > 0:
                    break
            
            price = float(price) if price else 0.0
            
            size = order.get('size')
            size = int(size) if size else 0
            
            order_type = order.get('order_type')
            if not order_type:
                order_type = order.get('stop_order_type', 'Unknown')
            
            # Enhanced logging for debugging
            bot_logger.info(f"📊 Notification fields extracted:")
            bot_logger.info(f"   Symbol: {symbol}")
            bot_logger.info(f"   Side: {side}")
            bot_logger.info(f"   Price: {price}")
            bot_logger.info(f"   Size: {size}")
            bot_logger.info(f"   Type: {order_type}")
            bot_logger.info(f"📋 Full order data: {order}")
            
            # Validate critical fields
            if symbol == 'Unknown' or price == 0.0:
                bot_logger.warning(f"⚠️ Missing critical data for notification. Order: {order}")
                # Still send notification with available data
            
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
            
            # Try to send a basic notification
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=f"🔔 Order Filled\n\nAn order was filled but details could not be retrieved.\nPlease check your positions.",
                    parse_mode=ParseMode.HTML
                )
            except:
                pass


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
            
            bot_logger.info(f"📊 Found {len(stored_orders)} pending orders in database")
            
            filled_orders = []
            
            # Check which orders are no longer in current orders
            stored_order_ids = {order['order_id'] for order in stored_orders}
            current_order_ids = {order.get('id') for order in current_orders}
            
            potentially_filled = stored_order_ids - current_order_ids
            
            if potentially_filled:
                bot_logger.info(f"🔍 Potentially filled orders: {potentially_filled}")
            
            for filled_id in potentially_filled:
                stored_order = next(
                    (o for o in stored_orders if o['order_id'] == filled_id), 
                    None
                )
                
                if stored_order:
                    # Log stored order details BEFORE marking as filled
                    bot_logger.info(f"📋 Stored order before marking filled:")
                    bot_logger.info(f"   Order ID: {filled_id}")
                    bot_logger.info(f"   Symbol: {stored_order.get('symbol')}")
                    bot_logger.info(f"   Side: {stored_order.get('side')}")
                    bot_logger.info(f"   Price: {stored_order.get('price')}")
                    bot_logger.info(f"   Size: {stored_order.get('size')}")
                    bot_logger.info(f"   Full data: {stored_order}")
                    
                    # Mark as filled in database
                    await db.order_states.update_one(
                        {'_id': stored_order['_id']},
                        {
                            '$set': {
                                'state': 'filled',
                                'filled_at': datetime.utcnow()
                            }
                        }
                    )
                    
                    # Add to filled orders list (BEFORE any modifications)
                    filled_orders.append(stored_order)
                    bot_logger.info(f"✅ Marked order as filled: {filled_id} - {stored_order.get('symbol')}")
            
            # Update/insert current order states with FULL data
            for order in current_orders:
                order_id = order.get('id')
                symbol = order.get('product_symbol')
                side = order.get('side')
                size = order.get('size')
                
                # Get price (try multiple fields)
                price = order.get('stop_price') or order.get('limit_price') or order.get('average_fill_price')
                
                # Convert price to float if it's a string
                try:
                    price = float(price) if price else None
                except (ValueError, TypeError):
                    price = None
                
                order_data = {
                    'user_id': user_id,
                    'api_id': api_id,
                    'order_id': order_id,
                    'state': order.get('state', 'pending'),
                    'order_type': order.get('stop_order_type', 'entry'),
                    'symbol': symbol,
                    'side': side,
                    'size': size,
                    'price': price,
                    'stop_price': order.get('stop_price'),
                    'limit_price': order.get('limit_price'),
                    'reduce_only': order.get('reduce_only', False),
                    'updated_at': datetime.utcnow()
                }
                
                await db.order_states.update_one(
                    {
                        'user_id': user_id,
                        'api_id': api_id,
                        'order_id': order_id
                    },
                    {'$set': order_data},
                    upsert=True
                )
                
                bot_logger.info(f"📝 Updated order state: {order_id} - {symbol} @ ${price}")
            
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
        
        bot_logger.info(f"🔍 Determining fill type:")
        bot_logger.info(f"   order_type: {order_type}")
        bot_logger.info(f"   reduce_only: {reduce_only}")
        
        if reduce_only:
            if 'stop_loss' in str(order_type).lower():
                return "STOP_LOSS"
            elif 'take_profit' in str(order_type).lower():
                return "TAKE_PROFIT"
            else:
                # Default to stop-loss if reduce_only but type unclear
                return "STOP_LOSS"
        else:
            return "ENTRY"
                
