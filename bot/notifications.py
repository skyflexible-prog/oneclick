# bot/notifications.py

from telegram import Bot
from telegram.constants import ParseMode
from config.settings import settings
from utils.logger import bot_logger
from datetime import datetime
from typing import Dict, Optional


class NotificationService:
    """Handle all trading notifications"""
    
    def __init__(self):
        self.bot = Bot(token=settings.telegram_bot_token)
    
    async def send_order_fill_notification(
        self, 
        user_telegram_id: int,
        order_data: Dict,
        position_data: Optional[Dict] = None
    ):
        """Send notification when an order is filled"""
        
        try:
            # Extract order details
            symbol = order_data.get('product_symbol', 'N/A')
            side = order_data.get('side', 'N/A').upper()
            fill_price = float(order_data.get('average_fill_price', 0))
            size = order_data.get('size', 0)
            order_type = order_data.get('order_type', 'N/A')
            stop_order_type = order_data.get('stop_order_type', '')
            filled_size = order_data.get('size', 0) - order_data.get('unfilled_size', 0)
            
            # Determine order category
            if 'stop_loss' in stop_order_type:
                order_category = "🛑 STOP-LOSS"
                emoji = "🔴"
            elif 'take_profit' in stop_order_type:
                order_category = "🎯 TAKE-PROFIT"
                emoji = "🟢"
            else:
                order_category = "📍 ENTRY"
                emoji = "🔵"
            
            # Calculate P&L if position data available
            pnl_text = ""
            if position_data and 'entry_price' in position_data:
                entry_price = float(position_data['entry_price'])
                position_size = int(position_data.get('size', 0))
                
                if position_size < 0:  # Short position
                    pnl = (entry_price - fill_price) * abs(position_size)
                else:  # Long position
                    pnl = (fill_price - entry_price) * position_size
                
                pnl_pct = (pnl / (entry_price * abs(position_size))) * 100 if entry_price > 0 else 0
                
                pnl_emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
                pnl_text = f"\n\n<b>P&L:</b> {pnl_emoji} ${pnl:+.2f} ({pnl_pct:+.2f}%)"
                if entry_price:
                    pnl_text += f"\n<b>Entry Price:</b> ${entry_price:.2f}"
            
            # Build notification message
            message = f"{emoji} <b>{order_category} FILLED!</b>\n\n"
            message += f"<b>Symbol:</b> {symbol}\n"
            message += f"<b>Side:</b> {side}\n"
            message += f"<b>Fill Price:</b> ${fill_price:.2f}\n"
            message += f"<b>Size:</b> {filled_size}\n"
            message += f"<b>Total Value:</b> ${fill_price * filled_size:.2f}"
            message += pnl_text
            message += f"\n\n<b>Time:</b> {datetime.utcnow().strftime('%H:%M:%S UTC')}"
            
            # Send notification
            await self.bot.send_message(
                chat_id=user_telegram_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
            
            bot_logger.info(f"Order fill notification sent to user {user_telegram_id}: {symbol}")
            
        except Exception as e:
            bot_logger.error(f"Error sending order fill notification: {e}")
    
    async def send_position_opened_notification(
        self, 
        user_telegram_id: int,
        trade_data: Dict
    ):
        """Send notification when a position is opened"""
        
        try:
            symbol = trade_data.get('symbol', 'N/A')
            side = trade_data.get('side', 'N/A').upper()
            entry_price = trade_data.get('entry_price', 0)
            size = trade_data.get('size', 0)
            strategy = trade_data.get('strategy_name', 'Manual')
            
            message = f"✅ <b>POSITION OPENED!</b>\n\n"
            message += f"<b>Symbol:</b> {symbol}\n"
            message += f"<b>Side:</b> {side}\n"
            message += f"<b>Entry Price:</b> ${entry_price:.2f}\n"
            message += f"<b>Size:</b> {size}\n"
            message += f"<b>Total Value:</b> ${entry_price * size:.2f}\n"
            message += f"<b>Strategy:</b> {strategy}\n"
            message += f"\n<b>Time:</b> {datetime.utcnow().strftime('%H:%M:%S UTC')}"
            
            await self.bot.send_message(
                chat_id=user_telegram_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
            
            bot_logger.info(f"Position opened notification sent to user {user_telegram_id}")
            
        except Exception as e:
            bot_logger.error(f"Error sending position opened notification: {e}")
    
    async def send_position_closed_notification(
        self, 
        user_telegram_id: int,
        trade_data: Dict,
        close_price: float,
        pnl: float,
        pnl_pct: float
    ):
        """Send notification when a position is closed"""
        
        try:
            symbol = trade_data.get('symbol', 'N/A')
            side = trade_data.get('side', 'N/A').upper()
            entry_price = trade_data.get('entry_price', 0)
            size = trade_data.get('size', 0)
            
            pnl_emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
            result = "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "BREAKEVEN"
            
            message = f"{pnl_emoji} <b>POSITION CLOSED - {result}!</b>\n\n"
            message += f"<b>Symbol:</b> {symbol}\n"
            message += f"<b>Side:</b> {side}\n"
            message += f"<b>Entry:</b> ${entry_price:.2f}\n"
            message += f"<b>Exit:</b> ${close_price:.2f}\n"
            message += f"<b>Size:</b> {size}\n\n"
            message += f"<b>P&L:</b> {pnl_emoji} ${pnl:+.2f}\n"
            message += f"<b>Return:</b> {pnl_pct:+.2f}%\n"
            message += f"\n<b>Time:</b> {datetime.utcnow().strftime('%H:%M:%S UTC')}"
            
            await self.bot.send_message(
                chat_id=user_telegram_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
            
            bot_logger.info(f"Position closed notification sent to user {user_telegram_id}")
            
        except Exception as e:
            bot_logger.error(f"Error sending position closed notification: {e}")


# Singleton instance
notification_service = NotificationService()
              
