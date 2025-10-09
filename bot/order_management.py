# bot/order_management.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from database import crud
from config.database import Database
from utils.helpers import encryptor
from utils.logger import bot_logger
from trading.delta_api import DeltaExchangeAPI
from typing import Dict, List


# ==================== ORDER MANAGEMENT STATES ====================
SELECTING_ORDER_API = 100
VIEWING_ORDERS = 101
EDITING_ORDER = 102
AWAITING_TRIGGER_PRICE = 103
AWAITING_LIMIT_PRICE = 104


async def show_order_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show order management main menu"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    db = Database.get_database()
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    
    if not user_data:
        await query.edit_message_text(
            "❌ User not found. Please use /start first.",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Get all API credentials
    apis = await crud.get_user_api_credentials(db, user_data['_id'])
    
    if not apis:
        await query.edit_message_text(
            "❌ <b>No API Credentials Found</b>\n\n"
            "Please add your Delta Exchange API credentials first.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")
            ]])
        )
        return
    
    # Create API selection keyboard
    keyboard = []
    for api in apis:
        status = "✅" if api.get('is_active') else "⚪"
        keyboard.append([
            InlineKeyboardButton(
                f"{status} {api['nickname']}", 
                callback_data=f"orders_api_{api['_id']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")])
    
    await query.edit_message_text(
        "<b>📋 Order Management</b>\n\n"
        "Select an API to view open orders:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return SELECTING_ORDER_API


async def show_orders_for_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all open orders for selected API"""
    query = update.callback_query
    await query.answer()
    
    api_id = query.data.split('_')[-1]
    user = query.from_user
    
    db = Database.get_database()
    api_data = await crud.get_api_credential_by_id(db, api_id)
    
    if not api_data:
        await query.edit_message_text(
            "❌ API not found.",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Decrypt credentials
    api_key = encryptor.decrypt(api_data['api_key_encrypted'])
    api_secret = encryptor.decrypt(api_data['api_secret_encrypted'])
    
    # Fetch open orders
    await query.edit_message_text("🔄 Fetching open orders...")
    
    try:
        async with DeltaExchangeAPI(api_key, api_secret) as delta_api:
            orders = await delta_api.get_open_orders()
        
        if not orders or len(orders) == 0:
            await query.edit_message_text(
                f"<b>📋 Open Orders - {api_data['nickname']}</b>\n\n"
                "No open orders found.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="orders_menu")
                ]])
            )
            return
        
        # Store orders in context
        context.user_data['current_orders'] = orders
        context.user_data['current_api_id'] = api_id
        
        # Create order list message
        message = f"<b>📋 Open Orders - {api_data['nickname']}</b>\n\n"
        message += f"Found {len(orders)} open order(s):\n\n"
        
        keyboard = []
        for idx, order in enumerate(orders[:10], 1):  # Limit to 10 orders
            symbol = order.get('product_symbol', 'N/A')
            side = order.get('side', 'N/A').upper()
            order_type = order.get('order_type', 'N/A')
            size = order.get('size', 0)
            unfilled_size = order.get('unfilled_size', 0)
            limit_price = order.get('limit_price', 'N/A')
            stop_price = order.get('stop_price', 'N/A')
            
            # Order summary
            order_text = f"{idx}. {symbol} - {side}"
            if stop_price != 'N/A':
                order_text += f" @ ${stop_price}"
            elif limit_price != 'N/A':
                order_text += f" @ ${limit_price}"
            
            message += f"<b>{idx}. {symbol}</b>\n"
            message += f"   Side: {side} | Size: {size}\n"
            if stop_price != 'N/A':
                message += f"   Stop: ${stop_price}"
            if limit_price != 'N/A':
                message += f" | Limit: ${limit_price}"
            message += f"\n   Type: {order_type}\n\n"
            
            keyboard.append([
                InlineKeyboardButton(
                    order_text,
                    callback_data=f"view_order_{idx-1}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="orders_menu")])
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return VIEWING_ORDERS
        
    except Exception as e:
        bot_logger.error(f"Error fetching orders: {e}")
        await query.edit_message_text(
            f"❌ <b>Error fetching orders</b>\n\n{str(e)}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="orders_menu")
            ]])
        )
        return


async def view_order_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View detailed order information and actions"""
    query = update.callback_query
    await query.answer()
    
    order_idx = int(query.data.split('_')[-1])
    orders = context.user_data.get('current_orders', [])
    
    if order_idx >= len(orders):
        await query.answer("Order not found", show_alert=True)
        return
    
    order = orders[order_idx]
    context.user_data['selected_order'] = order
    context.user_data['selected_order_idx'] = order_idx  # ✅ Store index
    
    # Format order details
    message = "<b>📋 Order Details</b>\n\n"
    message += f"<b>Symbol:</b> {order.get('product_symbol', 'N/A')}\n"
    message += f"<b>Side:</b> {order.get('side', 'N/A').upper()}\n"
    message += f"<b>Type:</b> {order.get('order_type', 'N/A')}\n"
    message += f"<b>Size:</b> {order.get('size', 0)}\n"
    message += f"<b>Unfilled:</b> {order.get('unfilled_size', 0)}\n"
    
    if order.get('limit_price'):
        message += f"<b>Limit Price:</b> ${order['limit_price']}\n"
    if order.get('stop_price'):
        message += f"<b>Stop Price:</b> ${order['stop_price']}\n"
    
    message += f"<b>Status:</b> {order.get('state', 'N/A')}\n"
    message += f"<b>Order ID:</b> <code>{order.get('id', 'N/A')}</code>\n"
    
    # Action buttons
    keyboard = [
        [
            InlineKeyboardButton("✏️ Edit Order", callback_data=f"edit_order_{order_idx}"),
            InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel_order_{order_idx}")
        ],
        [InlineKeyboardButton("🔙 Back to Orders", callback_data=f"orders_api_{context.user_data['current_api_id']}")]
    ]
    
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_edit_order_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show order edit options"""
    query = update.callback_query
    await query.answer()
    
    order_idx = int(query.data.split('_')[-1])
    order = context.user_data.get('selected_order')
    
    if not order:
        await query.answer("Order not found", show_alert=True)
        return
    
    message = "<b>✏️ Edit Order</b>\n\n"
    message += f"<b>Symbol:</b> {order.get('product_symbol')}\n"
    message += f"<b>Current Stop:</b> ${order.get('stop_price', 'N/A')}\n"
    message += f"<b>Current Limit:</b> ${order.get('limit_price', 'N/A')}\n\n"
    message += "What would you like to edit?"
    
    keyboard = [
        [InlineKeyboardButton("🎯 Change Trigger Price", callback_data=f"edit_trigger_{order_idx}")],
        [InlineKeyboardButton("📊 Change Limit Price", callback_data=f"edit_limit_{order_idx}")],
        [InlineKeyboardButton("💰 SL to Cost", callback_data=f"sl_to_cost_{order_idx}")],
        [InlineKeyboardButton("🔙 Back", callback_data=f"view_order_{order_idx}")]
    ]
    
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def edit_trigger_price_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start editing trigger price"""
    query = update.callback_query
    await query.answer()
    
    order = context.user_data.get('selected_order')
    
    message = "<b>🎯 Edit Trigger (Stop) Price</b>\n\n"
    message += f"<b>Current Trigger:</b> ${order.get('stop_price', 'N/A')}\n\n"
    message += "Enter new trigger price:\n"
    message += "• Enter number (e.g., 61000)\n"
    message += "• Or percentage (e.g., +5% or -3%)\n\n"
    message += "Use /cancel to abort"
    
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.HTML
    )
    
    return AWAITING_TRIGGER_PRICE


async def edit_limit_price_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start editing limit price"""
    query = update.callback_query
    await query.answer()
    
    order = context.user_data.get('selected_order')
    
    message = "<b>📊 Edit Limit Price</b>\n\n"
    message += f"<b>Current Limit:</b> ${order.get('limit_price', 'N/A')}\n\n"
    message += "Enter new limit price:\n"
    message += "• Enter number (e.g., 60500)\n"
    message += "• Or percentage (e.g., +2% or -1%)\n\n"
    message += "Use /cancel to abort"
    
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.HTML
    )
    
    return AWAITING_LIMIT_PRICE


async def receive_trigger_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and update trigger price"""
    user_input = update.message.text.strip()
    order = context.user_data.get('selected_order')
    api_id = context.user_data.get('current_api_id')
    
    db = Database.get_database()
    api_data = await crud.get_api_credential_by_id(db, api_id)
    
    # Parse input
    try:
        current_stop = float(order.get('stop_price', 0))
        
        if '%' in user_input:
            # Percentage change
            percentage = float(user_input.replace('%', '').replace('+', ''))
            new_stop = current_stop * (1 + percentage / 100)
        else:
            # Absolute price
            new_stop = float(user_input)
        
        new_stop = round(new_stop, 2)
        
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid price format. Please enter a number or percentage.",
            parse_mode=ParseMode.HTML
        )
        return AWAITING_TRIGGER_PRICE
    
    # Update order via API
    await update.message.reply_text("🔄 Updating order...")
    
    try:
        api_key = encryptor.decrypt(api_data['api_key_encrypted'])
        api_secret = encryptor.decrypt(api_data['api_secret_encrypted'])
        
        async with DeltaExchangeAPI(api_key, api_secret) as delta_api:
            # Delta Exchange edit order
            result = await delta_api.edit_order(
                product_id=order['product_id'],
                order_id=order['id'],
                stop_price=str(new_stop)
            )
        
        await update.message.reply_text(
            f"✅ <b>Order Updated!</b>\n\n"
            f"Old Trigger: ${current_stop}\n"
            f"New Trigger: ${new_stop}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to Orders", callback_data="orders_menu")
            ]])
        )
        
        return
        
    except Exception as e:
        bot_logger.error(f"Error updating order: {e}")
        await update.message.reply_text(
            f"❌ <b>Error updating order</b>\n\n{str(e)}",
            parse_mode=ParseMode.HTML
        )
        return


async def receive_limit_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and update limit price"""
    user_input = update.message.text.strip()
    order = context.user_data.get('selected_order')
    api_id = context.user_data.get('current_api_id')
    
    db = Database.get_database()
    api_data = await crud.get_api_credential_by_id(db, api_id)
    
    # Parse input
    try:
        current_limit = float(order.get('limit_price', 0))
        
        if '%' in user_input:
            # Percentage change
            percentage = float(user_input.replace('%', '').replace('+', ''))
            new_limit = current_limit * (1 + percentage / 100)
        else:
            # Absolute price
            new_limit = float(user_input)
        
        new_limit = round(new_limit, 2)
        
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid price format. Please enter a number or percentage.",
            parse_mode=ParseMode.HTML
        )
        return AWAITING_LIMIT_PRICE
    
    # Update order via API
    await update.message.reply_text("🔄 Updating order...")
    
    try:
        api_key = encryptor.decrypt(api_data['api_key_encrypted'])
        api_secret = encryptor.decrypt(api_data['api_secret_encrypted'])
        
        async with DeltaExchangeAPI(api_key, api_secret) as delta_api:
            result = await delta_api.edit_order(
                product_id=order['product_id'],
                order_id=order['id'],
                limit_price=str(new_limit)
            )
        
        await update.message.reply_text(
            f"✅ <b>Order Updated!</b>\n\n"
            f"Old Limit: ${current_limit}\n"
            f"New Limit: ${new_limit}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to Orders", callback_data="orders_menu")
            ]])
        )
        
        return
        
    except Exception as e:
        bot_logger.error(f"Error updating order: {e}")
        await update.message.reply_text(
            f"❌ <b>Error updating order</b>\n\n{str(e)}",
            parse_mode=ParseMode.HTML
        )
        return


# bot/order_management.py

async def sl_to_cost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Move stop-loss to cost (entry price with 1% buffer)"""
    query = update.callback_query
    await query.answer()
    
    order = context.user_data.get('selected_order')
    api_id = context.user_data.get('current_api_id')
    
    db = Database.get_database()
    api_data = await crud.get_api_credential_by_id(db, api_id)
    
    await query.edit_message_text("🔄 Moving SL to cost...")
    
    try:
        api_key = encryptor.decrypt(api_data['api_key_encrypted'])
        api_secret = encryptor.decrypt(api_data['api_secret_encrypted'])
        
        async with DeltaExchangeAPI(api_key, api_secret) as delta_api:
            # ✅ FIX: Get positions returns a LIST, not a single object
            positions_response = await delta_api.get_position(order['product_id'])
            
            # Handle different response formats
            if isinstance(positions_response, list):
                # Response is already a list
                positions = positions_response
            elif isinstance(positions_response, dict) and 'result' in positions_response:
                # Response is wrapped in result
                positions = positions_response['result']
            else:
                positions = [positions_response]
            
            # Find the position for this product
            position = None
            for pos in positions:
                if pos.get('product_id') == order['product_id']:
                    position = pos
                    break
            
            if not position:
                await query.edit_message_text(
                    "❌ <b>No position found</b>\n\n"
                    "Unable to find an open position for this order.",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Back", callback_data=f"view_order_{context.user_data.get('selected_order_idx', 0)}")
                    ]])
                )
                return
            
            entry_price = float(position.get('entry_price', 0))
            
            if entry_price == 0:
                await query.edit_message_text(
                    "❌ <b>Unable to find entry price</b>\n\n"
                    "This position may not have an entry price set.",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Back", callback_data=f"view_order_{context.user_data.get('selected_order_idx', 0)}")
                    ]])
                )
                return
            
            # Calculate SL to cost
            side = order.get('side', 'buy')
            if side == 'buy':
                # For long position, SL is below entry
                new_stop = entry_price * 0.99  # 1% below entry
                new_limit = entry_price * 0.98  # 2% below entry
            else:
                # For short position, SL is above entry
                new_stop = entry_price * 1.01  # 1% above entry
                new_limit = entry_price * 1.02  # 2% above entry
            
            new_stop = round(new_stop, 2)
            new_limit = round(new_limit, 2)
            
            # Update order
            result = await delta_api.edit_order(
                product_id=order['product_id'],
                order_id=order['id'],
                stop_price=str(new_stop),
                limit_price=str(new_limit)
            )
        
        await query.edit_message_text(
            f"✅ <b>SL Moved to Cost!</b>\n\n"
            f"<b>Entry Price:</b> ${entry_price}\n"
            f"<b>New Stop:</b> ${new_stop}\n"
            f"<b>New Limit:</b> ${new_limit}\n\n"
            f"Your stop-loss is now at breakeven (±1%).",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to Orders", callback_data="orders_menu")
            ]])
        )
        
    except Exception as e:
        bot_logger.error(f"Error moving SL to cost: {e}")
        await query.edit_message_text(
            f"❌ <b>Error moving SL to cost</b>\n\n"
            f"<code>{str(e)}</code>\n\n"
            "Please check if you have an open position for this order.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="orders_menu")
            ]])
        )


async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel selected order"""
    query = update.callback_query
    await query.answer()
    
    order_idx = int(query.data.split('_')[-1])
    orders = context.user_data.get('current_orders', [])
    order = orders[order_idx]
    api_id = context.user_data.get('current_api_id')
    
    db = Database.get_database()
    api_data = await crud.get_api_credential_by_id(db, api_id)
    
    await query.edit_message_text("🔄 Cancelling order...")
    
    try:
        api_key = encryptor.decrypt(api_data['api_key_encrypted'])
        api_secret = encryptor.decrypt(api_data['api_secret_encrypted'])
        
        async with DeltaExchangeAPI(api_key, api_secret) as delta_api:
            result = await delta_api.cancel_order(
                product_id=order['product_id'],
                order_id=order['id']
            )
        
        await query.edit_message_text(
            f"✅ <b>Order Cancelled!</b>\n\n"
            f"Symbol: {order.get('product_symbol')}\n"
            f"Side: {order.get('side').upper()}\n"
            f"Size: {order.get('size')}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to Orders", callback_data=f"orders_api_{api_id}")
            ]])
        )
        
    except Exception as e:
        bot_logger.error(f"Error cancelling order: {e}")
        await query.edit_message_text(
            f"❌ <b>Error cancelling order</b>\n\n{str(e)}",
            parse_mode=ParseMode.HTML
  )
      
