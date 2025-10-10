# bot/notifications.py

from telegram import Bot
from telegram.constants import ParseMode
from config.database import Database
from database import crud
from utils.logger import bot_logger
from datetime import datetime
from typing import Dict, List, Optional
import asyncio


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
        """
        Send notification when an order is filled
        
        Args:
            user_id: Telegram user ID
            order: Order data from exchange
            fill_type: "ENTRY", "STOP_LOSS", or "TAKE_PROFIT"
        """
        try:
            symbol = order.get('product_symbol', 'N/A')
            side = order.get('side', 'N/A').upper()
            fill_price = float(order.get('average_fill_price', 0))
            size = order.get('size', 0)
            order_type = order.get('order_type', 'N/A')
            
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
                message += f"<b>Fill Price:</b> ${fill_price:.2f}\n"
                message += f"<b>Size:</b> {size}\n"
                message += f"<b>Type:</b> {order_type}\n"
                message += f"<b>Time:</b> {datetime.utcnow().strftime('%H:%M:%S UTC')}"
                
            elif fill_type == "STOP_LOSS":
                # Get entry price and calculate P&L
                entry_price = float(order.get('entry_price', fill_price))
                if side == "BUY":
                    pnl = (fill_price - entry_price) * size
                    pnl_pct = ((fill_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
                else:
                    pnl = (entry_price - fill_price) * size
                    pnl_pct = ((entry_price - fill_price) / entry_price * 100) if entry_price > 0 else 0
                
                pnl_emoji = "🟢" if pnl >= 0 else "🔴"
                
                message = f"{emoji} <b>Stop-Loss Triggered</b>\n\n"
                message += f"<b>Symbol:</b> {symbol}\n"
                message += f"<b>Side:</b> {side}\n"
                message += f"<b>Fill Price:</b> ${fill_price:.2f}\n"
                message += f"<b>Entry Price:</b> ${entry_price:.2f}\n"
                message += f"<b>Size:</b> {size}\n\n"
                message += f"<b>P&L:</b> {pnl_emoji} ${pnl:+.2f} ({pnl_pct:+.2f}%)\n"
                message += f"<b>Time:</b> {datetime.utcnow().strftime('%H:%M:%S UTC')}"
                
            elif fill_type == "TAKE_PROFIT":
                # Get entry price and calculate P&L
                entry_price = float(order.get('entry_price', fill_price))
                if side == "BUY":
                    pnl = (fill_price - entry_price) * size
                    pnl_pct = ((fill_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
                else:
                    pnl = (entry_price - fill_price) * size
                    pnl_pct = ((entry_price - fill_price) / entry_price * 100) if entry_price > 0 else 0
                
                message = f"{emoji} <b>Take-Profit Hit!</b>\n\n"
                message += f"<b>Symbol:</b> {symbol}\n"
                message += f"<b>Side:</b> {side}\n"
                message += f"<b>Fill Price:</b> ${fill_price:.2f}\n"
                message += f"<b>Entry Price:</b> ${entry_price:.2f}\n"
                message += f"<b>Size:</b> {size}\n\n"
                message += f"<b>P&L:</b> 🟢 ${pnl:+.2f} ({pnl_pct:+.2f}%)\n"
                message += f"<b>Time:</b> {datetime.utcnow().strftime('%H:%M:%S UTC')}"
            
            # Send notification
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
            
            bot_logger.info(f"Order fill notification sent to user {user_id}: {fill_type}")
            
        except Exception as e:
            bot_logger.error(f"Error sending order fill notification: {e}")
    
    async def send_trade_execution_notification(
        self,
        user_id: int,
        trade_data: Dict
    ):
        """Send notification when a trade is executed"""
        try:
            symbol = trade_data.get('symbol', 'N/A')
            side = trade_data.get('side', 'N/A').upper()
            entry_price = trade_data.get('entry_price', 0)
            size = trade_data.get('size', 0)
            strategy = trade_data.get('strategy_name', 'Manual')
            api_name = trade_data.get('api_name', 'N/A')
            
            message = f"✅ <b>Trade Executed!</b>\n\n"
            message += f"<b>Symbol:</b> {symbol}\n"
            message += f"<b>Side:</b> {side}\n"
            message += f"<b>Entry Price:</b> ${entry_price:.2f}\n"
            message += f"<b>Size:</b> {size}\n"
            message += f"<b>Total Value:</b> ${entry_price * size:.2f}\n\n"
            message += f"<b>Strategy:</b> {strategy}\n"
            message += f"<b>API:</b> {api_name}\n"
            message += f"<b>Time:</b> {datetime.utcnow().strftime('%H:%M:%S UTC')}"
            
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
            
            bot_logger.info(f"Trade execution notification sent to user {user_id}")
            
        except Exception as e:
            bot_logger.error(f"Error sending trade execution notification: {e}")
    
    async def send_position_closed_notification(
        self,
        user_id: int,
        position_data: Dict
    ):
        """Send notification when a position is closed"""
        try:
            symbol = position_data.get('symbol', 'N/A')
            side = position_data.get('side', 'N/A').upper()
            entry_price = position_data.get('entry_price', 0)
            exit_price = position_data.get('exit_price', 0)
            size = position_data.get('size', 0)
            pnl = position_data.get('realized_pnl', 0)
            pnl_pct = position_data.get('pnl_percentage', 0)
            
            pnl_emoji = "🟢" if pnl >= 0 else "🔴"
            
            message = f"🔒 <b>Position Closed</b>\n\n"
            message += f"<b>Symbol:</b> {symbol}\n"
            message += f"<b>Side:</b> {side}\n"
            message += f"<b>Entry:</b> ${entry_price:.2f}\n"
            message += f"<b>Exit:</b> ${exit_price:.2f}\n"
            message += f"<b>Size:</b> {size}\n\n"
            message += f"<b>Realized P&L:</b> {pnl_emoji} ${pnl:+.2f} ({pnl_pct:+.2f}%)\n"
            message += f"<b>Time:</b> {datetime.utcnow().strftime('%H:%M:%S UTC')}"
            
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
            
            bot_logger.info(f"Position closed notification sent to user {user_id}")
            
        except Exception as e:
            bot_logger.error(f"Error sending position closed notification: {e}")


class OrderFillTracker:
    """Track order states and detect fills"""
    
    @staticmethod
    async def check_order_fills(user_id: int, api_id: str, current_orders: List[Dict]):
        """
        Check for order fills by comparing current orders with stored state
        
        Args:
            user_id: Telegram user ID
            api_id: API credential ID
            current_orders: Current open orders from exchange
        
        Returns:
            List of filled orders
        """
        try:
            db = Database.get_database()
            
            # Get stored order states
            stored_orders = await db.order_states.find({
                'user_id': user_id,
                'api_id': api_id,
                'state': 'pending'
            }).to_list(None)
            
            filled_orders = []
            
            # Check which orders are no longer in current orders (filled or cancelled)
            stored_order_ids = {order['order_id'] for order in stored_orders}
            current_order_ids = {order.get('id') for order in current_orders}
            
            potentially_filled = stored_order_ids - current_order_ids
            
            for filled_id in potentially_filled:
                # Find the stored order
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
            
            # Update current order states
            for order in current_orders:
                await db.order_states.update_one(
                    {
                        'user_id': user_id,
                        'api_id': api_id,
                        'order_id': order.get('id')
                    },
                    {
                        '$set': {
                            'user_id': user_id,
                            'api_id': api_id,
                            'order_id': order.get('id'),
                            'state': order.get('state', 'pending'),
                            'order_data': order,
                            'updated_at': datetime.utcnow()
                        }
                    },
                    upsert=True
                )
            
            return filled_orders
            
        except Exception as e:
            bot_logger.error(f"Error checking order fills: {e}")
            return []
    
    @staticmethod
    def determine_fill_type(order: Dict) -> str:
        """Determine if order is entry, stop-loss, or take-profit"""
        order_type = order.get('order_data', {}).get('stop_order_type', '')
        
        if 'stop_loss' in order_type.lower():
            return "STOP_LOSS"
        elif 'take_profit' in order_type.lower():
            return "TAKE_PROFIT"
        else:
            return "ENTRY"
        
