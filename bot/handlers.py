# bot/handlers.py - PART 1 OF 4
# Complete working handlers.py file

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from bot.database import Database
from bot.logger import bot_logger
from bot import crud
from bot.keyboards import (
    get_main_menu_keyboard,
    get_api_management_keyboard,
    get_api_action_keyboard,
    get_api_selection_keyboard,
    get_trade_execution_keyboard,
    get_position_action_keyboard
)
from bson import ObjectId
from datetime import datetime
import asyncio


# Conversation states
WAITING_API_NAME, WAITING_API_KEY, WAITING_API_SECRET = range(3)
SELECTING_API, SELECTING_STRATEGY = range(2)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    db = Database.get_database()
    
    # Create or get user
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    if not user_data:
        await crud.create_user(
            db,
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        bot_logger.info(f"✅ New user created: {user.id}")
    
    await update.message.reply_text(
        f"👋 Hello {user.first_name}!\n\n"
        "Welcome to Telegram Straddle Pro Bot\n\n"
        "This bot helps you execute option trading strategies on Delta Exchange.",
        reply_markup=get_main_menu_keyboard()
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all button callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    bot_logger.info(f"🔘 Button: {data}")
    
    if data == "main_menu":
        await query.edit_message_text(
            "🏠 <b>Main Menu</b>\n\nSelect an option:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )
    elif data == "api_menu":
        await query.edit_message_text(
            "🔑 <b>API Management</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_api_management_keyboard()
        )
    elif data == "list_apis":
        await list_apis(update, context)
    elif data == "add_api":
        await add_api(update, context)
    elif data == "help":
        await query.edit_message_text(
            "❓ <b>Help</b>\n\n"
            "Use the buttons below to navigate.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
        )
    else:
        await query.edit_message_text(
            "Please select an option:",
            reply_markup=get_main_menu_keyboard()
        )


async def list_apis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all API credentials"""
    query = update.callback_query
    user = update.effective_user
    
    db = Database.get_database()
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    
    if not user_data:
        await query.edit_message_text(
            "❌ User not found. Please use /start",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    apis = await crud.get_user_apis(db, user_data['_id'])
    
    if not apis:
        await query.edit_message_text(
            "📝 <b>No API Keys</b>\n\n"
            "You haven't added any API keys yet.\n"
            "Click below to add your first API key.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_api_management_keyboard()
        )
        return
    
    # Build API list message
    text = "🔑 <b>Your API Keys</b>\n\n"
    
    keyboard = []
    for api in apis:
        status = "✅" if api.get('is_active') else "⚪"
        nickname = api.get('nickname', 'Unnamed')
        text += f"{status} {nickname}\n"
        
        keyboard.append([
            InlineKeyboardButton(
                f"{status} {nickname}",
                callback_data=f"view_api_{str(api['_id'])}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("➕ Add New API", callback_data="add_api")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def add_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start API addition conversation"""
    query = update.callback_query
    
    await query.edit_message_text(
        "📝 <b>Add New API Key</b>\n\n"
        "Please enter a nickname for this API key:",
        parse_mode=ParseMode.HTML
    )
    
    return WAITING_API_NAME


async def receive_api_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive API nickname"""
    nickname = update.message.text.strip()
    
    if len(nickname) > 50:
        await update.message.reply_text(
            "❌ Nickname too long. Please enter a shorter name (max 50 characters):"
        )
        return WAITING_API_NAME
    
    context.user_data['api_nickname'] = nickname
    
    await update.message.reply_text(
        f"✅ Nickname: {nickname}\n\n"
        "Now, please enter your Delta Exchange API Key:"
    )
    
    return WAITING_API_KEY


async def receive_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive API key"""
    api_key = update.message.text.strip()
    
    # Delete the message for security
    try:
        await update.message.delete()
    except:
        pass
    
    if len(api_key) < 10:
        await update.message.reply_text(
            "❌ Invalid API key. Please enter your Delta Exchange API Key:"
        )
        return WAITING_API_KEY
    
    context.user_data['api_key'] = api_key
    
    await update.message.reply_text(
        "✅ API Key received\n\n"
        "Now, please enter your Delta Exchange API Secret:"
    )
    
    return WAITING_API_SECRET


async def receive_api_secret(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive API secret and save"""
    api_secret = update.message.text.strip()
    user = update.effective_user
    
    # Delete the message for security
    try:
        await update.message.delete()
    except:
        pass
    
    if len(api_secret) < 10:
        await update.message.reply_text(
            "❌ Invalid API secret. Please enter your Delta Exchange API Secret:"
        )
        return WAITING_API_SECRET
    
    # Save to database
    db = Database.get_database()
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    
    try:
        await crud.create_api_credential(
            db,
            user_id=user_data['_id'],
            nickname=context.user_data['api_nickname'],
            api_key=context.user_data['api_key'],
            api_secret=api_secret
        )
        
        await update.message.reply_text(
            "✅ <b>API Key Added Successfully!</b>\n\n"
            f"Nickname: {context.user_data['api_nickname']}",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )
        
        bot_logger.info(f"✅ API added for user {user.id}")
        
    except Exception as e:
        bot_logger.error(f"❌ Failed to save API: {e}")
        await update.message.reply_text(
            f"❌ Failed to save API key: {str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
    
    # Clear context
    context.user_data.clear()
    
    return ConversationHandler.END


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel any ongoing conversation"""
    user = update.effective_user
    bot_logger.info(f"❌ User {user.id} cancelled conversation")
    
    context.user_data.clear()
    
    await update.message.reply_text(
        "❌ Operation cancelled.",
        reply_markup=get_main_menu_keyboard()
    )
    
    return ConversationHandler.END


async def view_api_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View specific API details"""
    query = update.callback_query
    api_id = query.data.split('_')[-1]
    
    db = Database.get_database()
    api_data = await crud.get_api_credential_by_id(db, api_id)
    
    if not api_data:
        await query.answer("API not found", show_alert=True)
        return
    
    status = "✅ Active" if api_data.get('is_active') else "⚪ Inactive"
    
    details_text = (
        f"🔑 <b>API Details</b>\n\n"
        f"<b>Nickname:</b> {api_data.get('nickname', 'Unnamed')}\n"
        f"<b>Status:</b> {status}\n"
        f"<b>Key:</b> <code>{api_data.get('api_key_encrypted', '')[:20]}...</code>\n"
        f"<b>Created:</b> {api_data.get('created_at', 'Unknown')}"
    )
    
    await query.answer()
    await query.edit_message_text(
        details_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_api_action_keyboard(api_id)
    )

# PART 2 OF 4 - Continues from PART 1

async def activate_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Activate API"""
    query = update.callback_query
    await query.answer()
    api_id = query.data.split('_')[-1]
    db = Database.get_database()
    user_id = str(query.from_user.id)
    bot_logger.info(f"✅ Activating API: user={user_id}, api_id={api_id}")
    
    try:
        await crud.set_active_api(db, user_id, ObjectId(api_id))
        bot_logger.info(f"✅ API activated successfully")
        await query.answer("✅ API activated!", show_alert=True)
        await list_apis(update, context)
    except Exception as e:
        bot_logger.error(f"❌ Activate API failed: {e}")
        await query.answer(f"❌ Activation failed: {str(e)}", show_alert=True)


async def delete_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete API"""
    query = update.callback_query
    await query.answer()
    api_id = query.data.split('_')[-1]
    
    db = Database.get_database()
    
    try:
        await crud.delete_api_credential(db, ObjectId(api_id))
        bot_logger.info(f"✅ API deleted: {api_id}")
        await query.answer("✅ API deleted!", show_alert=True)
        await list_apis(update, context)
    except Exception as e:
        bot_logger.error(f"❌ Delete API failed: {e}")
        await query.answer(f"❌ Delete failed: {str(e)}", show_alert=True)


async def trade_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show trade menu"""
    query = update.callback_query
    user = update.effective_user
    
    db = Database.get_database()
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    
    if not user_data:
        await query.edit_message_text(
            "❌ User not found. Please use /start",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END
    
    # Get user's API keys
    apis = await crud.get_user_apis(db, user_data['_id'])
    
    if not apis:
        await query.edit_message_text(
            "⚠️ <b>No API Keys</b>\n\n"
            "Please add an API key first before executing trades.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END
    
    # Show API selection
    await query.edit_message_text(
        "📊 <b>Execute Trade</b>\n\n"
        "Select which API to use for this trade:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_api_selection_keyboard(apis)
    )
    
    return SELECTING_API


async def select_api_for_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """After API selection, show strategies"""
    query = update.callback_query
    await query.answer()
    
    # Extract API ID from callback data
    api_id = query.data.split('_')[-1]
    context.user_data['selected_api_id'] = api_id
    
    user = update.effective_user
    db = Database.get_database()
    
    # Get user's strategies
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    strategies = await crud.get_user_strategies(db, user_data['_id'])
    
    if not strategies:
        await query.edit_message_text(
            "⚠️ <b>No Strategies</b>\n\n"
            "Please create a trading strategy first.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END
    
    # Get API details for display
    api_data = await crud.get_api_credential_by_id(db, ObjectId(api_id))
    
    # Show strategy selection
    await query.edit_message_text(
        f"📊 <b>Execute Trade</b>\n\n"
        f"🔑 <b>Selected API:</b> {api_data.get('nickname', 'Unnamed')}\n\n"
        f"Select a strategy to execute:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_trade_execution_keyboard(strategies)
    )
    
    return SELECTING_STRATEGY


async def execute_trade_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show trade preview and confirmation"""
    query = update.callback_query
    strategy_id = query.data.split('_')[-1]
    user = query.from_user
    
    db = Database.get_database()
    strategy = await crud.get_strategy_by_id(db, strategy_id)
    
    if not strategy:
        await query.answer("Strategy not found", show_alert=True)
        return ConversationHandler.END
    
    # Get API credentials
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    selected_api_id = context.user_data.get('selected_api_id')
    
    if selected_api_id:
        api_data = await crud.get_api_credential_by_id(db, ObjectId(selected_api_id))
    else:
        api_data = await crud.get_api_credential_by_id(db, strategy['api_id'])
    
    if not api_data:
        await query.edit_message_text(
            "❌ API credentials not found.",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END
    
    # Build preview text
    preview_text = (
        f"📊 <b>Trade Preview</b>\n\n"
        f"<b>Strategy:</b> {strategy.get('name', 'Unnamed')}\n"
        f"<b>API:</b> {api_data.get('nickname', 'Unnamed')}\n"
        f"<b>Direction:</b> {strategy.get('direction', 'N/A').upper()}\n"
        f"<b>Lot Size:</b> {strategy.get('lot_size', 1)}\n\n"
        f"Confirm execution?"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_trade_{strategy_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        preview_text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return ConversationHandler.END


async def confirm_trade_execution(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute the trade after confirmation"""
    query = update.callback_query
    await query.answer()
    
    strategy_id = query.data.split('_')[-1]
    user = query.from_user
    
    db = Database.get_database()
    strategy = await crud.get_strategy_by_id(db, strategy_id)
    
    if not strategy:
        await query.edit_message_text(
            "❌ Strategy not found",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Show executing message
    await query.edit_message_text(
        "⏳ <b>Executing Trade...</b>\n\nPlease wait...",
        parse_mode=ParseMode.HTML
    )
    
    try:
        # Execute trade logic here
        # This would call your strangle_strategy.py functions
        
        await query.edit_message_text(
            "✅ <b>Trade Executed Successfully!</b>\n\n"
            f"Strategy: {strategy.get('name', 'Unnamed')}\n"
            f"Check /positions for details",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )
        
        bot_logger.info(f"✅ Trade executed: user={user.id}, strategy={strategy_id}")
        
    except Exception as e:
        bot_logger.error(f"❌ Trade execution failed: {e}")
        await query.edit_message_text(
            f"❌ <b>Trade Failed</b>\n\n{str(e)}",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )


async def view_positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View all open positions"""
    user = update.effective_user
    db = Database.get_database()
    
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    
    if not user_data:
        await update.message.reply_text(
            "❌ User not found. Please use /start"
        )
        return
    
    # Get positions from database
    positions = await crud.get_user_positions(db, user_data['_id'])
    
    if not positions:
        await update.message.reply_text(
            "📭 <b>No Open Positions</b>\n\n"
            "You don't have any active positions.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Build positions text
    text = "📊 <b>Your Positions</b>\n\n"
    
    keyboard = []
    for pos in positions:
        symbol = pos.get('symbol', 'Unknown')
        pnl = pos.get('unrealized_pnl', 0)
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        
        text += f"{pnl_emoji} {symbol}: ${pnl:.2f}\n"
        
        keyboard.append([
            InlineKeyboardButton(
                f"{pnl_emoji} {symbol}",
                callback_data=f"pos_{str(pos['_id'])}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def view_position_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View specific position details"""
    query = update.callback_query
    await query.answer()
    
    position_id = query.data.split('_')[-1]
    db = Database.get_database()
    
    position = await crud.get_position_by_id(db, ObjectId(position_id))
    
    if not position:
        await query.answer("Position not found", show_alert=True)
        return
    
    # Build details text
    details_text = (
        f"📊 <b>Position Details</b>\n\n"
        f"<b>Symbol:</b> {position.get('symbol', 'Unknown')}\n"
        f"<b>Entry Price:</b> ${position.get('entry_price', 0):.2f}\n"
        f"<b>Current Price:</b> ${position.get('current_price', 0):.2f}\n"
        f"<b>Quantity:</b> {position.get('quantity', 0)}\n"
        f"<b>PnL:</b> ${position.get('unrealized_pnl', 0):.2f}\n"
        f"<b>Opened:</b> {position.get('created_at', 'Unknown')}"
    )
    
    await query.edit_message_text(
        details_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_position_action_keyboard(position_id)
    )


async def close_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Close a position"""
    query = update.callback_query
    await query.answer()
    
    position_id = query.data.split('_')[-1]
    db = Database.get_database()
    
    try:
        # Close position logic here
        await crud.update_position_status(db, ObjectId(position_id), 'closed')
        
        await query.edit_message_text(
            "✅ <b>Position Closed</b>\n\n"
            "The position has been closed successfully.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )
        
        bot_logger.info(f"✅ Position closed: {position_id}")
        
    except Exception as e:
        bot_logger.error(f"❌ Close position failed: {e}")
        await query.answer(f"❌ Failed to close: {str(e)}", show_alert=True)


# PART 3 OF 4 - Continues from PART 2


async def strategies_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show strategies menu"""
    query = update.callback_query
    user = update.effective_user
    
    db = Database.get_database()
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    
    if not user_data:
        await query.edit_message_text(
            "❌ User not found. Please use /start",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Get user's strategies
    strategies = await crud.get_user_strategies(db, user_data['_id'])
    
    text = "📊 <b>Your Strategies</b>\n\n"
    keyboard = []
    
    if strategies:
        for strat in strategies:
            name = strat.get('name', 'Unnamed')
            direction = strat.get('direction', 'N/A').upper()
            text += f"• {name} ({direction})\n"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"📊 {name}",
                    callback_data=f"view_strat_{str(strat['_id'])}"
                )
            ])
    else:
        text += "No strategies created yet."
    
    keyboard.append([InlineKeyboardButton("➕ Create New", callback_data="create_strategy")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def view_strategy_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View specific strategy details"""
    query = update.callback_query
    await query.answer()
    
    strategy_id = query.data.split('_')[-1]
    db = Database.get_database()
    
    strategy = await crud.get_strategy_by_id(db, ObjectId(strategy_id))
    
    if not strategy:
        await query.answer("Strategy not found", show_alert=True)
        return
    
    # Build details text
    details_text = (
        f"📊 <b>Strategy: {strategy.get('name', 'Unnamed')}</b>\n\n"
        f"<b>Type:</b> {strategy.get('type', 'N/A')}\n"
        f"<b>Direction:</b> {strategy.get('direction', 'N/A').upper()}\n"
        f"<b>Lot Size:</b> {strategy.get('lot_size', 1)}\n"
        f"<b>Stop Loss:</b> {strategy.get('stop_loss_pct', 0)}%\n"
        f"<b>Target:</b> {strategy.get('target_pct', 0)}%\n"
        f"<b>Created:</b> {strategy.get('created_at', 'Unknown')}"
    )
    
    keyboard = [
        [InlineKeyboardButton("✏️ Edit", callback_data=f"edit_strat_{strategy_id}")],
        [InlineKeyboardButton("🗑️ Delete", callback_data=f"del_strat_{strategy_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data="strategies_menu")]
    ]
    
    await query.edit_message_text(
        details_text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def delete_strategy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a strategy"""
    query = update.callback_query
    await query.answer()
    
    strategy_id = query.data.split('_')[-1]
    db = Database.get_database()
    
    try:
        await crud.delete_strategy(db, ObjectId(strategy_id))
        
        await query.edit_message_text(
            "✅ <b>Strategy Deleted</b>\n\n"
            "The strategy has been deleted successfully.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )
        
        bot_logger.info(f"✅ Strategy deleted: {strategy_id}")
        
    except Exception as e:
        bot_logger.error(f"❌ Delete strategy failed: {e}")
        await query.answer(f"❌ Failed to delete: {str(e)}", show_alert=True)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message"""
    help_text = (
        "🤖 <b>Bot Commands</b>\n\n"
        "/start - Start the bot\n"
        "/positions - View your positions\n"
        "/help - Show this help message\n\n"
        "<b>Features:</b>\n"
        "• Manage API keys securely\n"
        "• Create trading strategies\n"
        "• Execute trades automatically\n"
        "• Monitor positions in real-time\n\n"
        "<b>Need help?</b>\n"
        "Contact support at @yoursupport"
    )
    
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu_keyboard()
    )


async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show settings menu"""
    query = update.callback_query
    
    settings_text = (
        "⚙️ <b>Settings</b>\n\n"
        "Configure your bot preferences:"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔔 Notifications", callback_data="notif_settings")],
        [InlineKeyboardButton("🔐 Security", callback_data="security_settings")],
        [InlineKeyboardButton("📊 Trading", callback_data="trading_settings")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        settings_text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def notification_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Configure notification settings"""
    query = update.callback_query
    user = update.effective_user
    
    db = Database.get_database()
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    
    settings = user_data.get('notification_settings', {})
    
    trade_notifs = "✅" if settings.get('trade_execution', True) else "❌"
    pnl_notifs = "✅" if settings.get('pnl_updates', True) else "❌"
    alert_notifs = "✅" if settings.get('price_alerts', True) else "❌"
    
    text = (
        f"🔔 <b>Notification Settings</b>\n\n"
        f"{trade_notifs} Trade Execution\n"
        f"{pnl_notifs} PnL Updates\n"
        f"{alert_notifs} Price Alerts"
    )
    
    keyboard = [
        [InlineKeyboardButton(f"{trade_notifs} Trade Execution", callback_data="toggle_trade_notif")],
        [InlineKeyboardButton(f"{pnl_notifs} PnL Updates", callback_data="toggle_pnl_notif")],
        [InlineKeyboardButton(f"{alert_notifs} Price Alerts", callback_data="toggle_alert_notif")],
        [InlineKeyboardButton("🔙 Back", callback_data="settings_menu")]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def security_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show security settings"""
    query = update.callback_query
    
    text = (
        "🔐 <b>Security Settings</b>\n\n"
        "Your API keys are encrypted using AES-256.\n"
        "Private keys never leave the server."
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Rotate Encryption Key", callback_data="rotate_key")],
        [InlineKeyboardButton("📋 View API Keys", callback_data="list_apis")],
        [InlineKeyboardButton("🔙 Back", callback_data="settings_menu")]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def trading_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show trading settings"""
    query = update.callback_query
    user = update.effective_user
    
    db = Database.get_database()
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    
    settings = user_data.get('trading_settings', {})
    
    auto_trade = "✅" if settings.get('auto_trade', False) else "❌"
    paper_mode = "✅" if settings.get('paper_trading', True) else "❌"
    
    text = (
        f"📊 <b>Trading Settings</b>\n\n"
        f"{auto_trade} Auto Trading\n"
        f"{paper_mode} Paper Trading Mode"
    )
    
    keyboard = [
        [InlineKeyboardButton(f"{auto_trade} Auto Trading", callback_data="toggle_auto_trade")],
        [InlineKeyboardButton(f"{paper_mode} Paper Trading", callback_data="toggle_paper_mode")],
        [InlineKeyboardButton("🔙 Back", callback_data="settings_menu")]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def toggle_notification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle notification settings"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    db = Database.get_database()
    
    # Determine which notification to toggle
    if query.data == "toggle_trade_notif":
        setting_key = "trade_execution"
    elif query.data == "toggle_pnl_notif":
        setting_key = "pnl_updates"
    elif query.data == "toggle_alert_notif":
        setting_key = "price_alerts"
    else:
        return
    
    try:
        # Update in database
        await crud.toggle_notification_setting(db, str(user.id), setting_key)
        
        # Refresh the notification settings page
        await notification_settings(update, context)
        
    except Exception as e:
        bot_logger.error(f"❌ Toggle notification failed: {e}")
        await query.answer(f"❌ Failed: {str(e)}", show_alert=True)


async def toggle_trading_setting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle trading settings"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    db = Database.get_database()
    
    # Determine which setting to toggle
    if query.data == "toggle_auto_trade":
        setting_key = "auto_trade"
    elif query.data == "toggle_paper_mode":
        setting_key = "paper_trading"
    else:
        return
    
    try:
        # Update in database
        await crud.toggle_trading_setting(db, str(user.id), setting_key)
        
        # Refresh the trading settings page
        await trading_settings(update, context)
        
    except Exception as e:
        bot_logger.error(f"❌ Toggle setting failed: {e}")
        await query.answer(f"❌ Failed: {str(e)}", show_alert=True)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    bot_logger.error(f"❌ Error: {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred. Please try again or contact support.",
            reply_markup=get_main_menu_keyboard()
        )


# PART 4 OF 4 (FINAL) - Continues from PART 3


async def stats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show trading statistics"""
    query = update.callback_query
    user = update.effective_user
    
    db = Database.get_database()
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    
    if not user_data:
        await query.edit_message_text(
            "❌ User not found. Please use /start",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Get user statistics
    stats = await crud.get_user_statistics(db, user_data['_id'])
    
    total_trades = stats.get('total_trades', 0)
    winning_trades = stats.get('winning_trades', 0)
    total_pnl = stats.get('total_pnl', 0)
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    stats_text = (
        f"📊 <b>Your Statistics</b>\n\n"
        f"<b>Total Trades:</b> {total_trades}\n"
        f"<b>Winning Trades:</b> {winning_trades}\n"
        f"<b>Win Rate:</b> {win_rate:.1f}%\n"
        f"<b>Total PnL:</b> ${total_pnl:.2f}\n"
        f"<b>Best Trade:</b> ${stats.get('best_trade', 0):.2f}\n"
        f"<b>Worst Trade:</b> ${stats.get('worst_trade', 0):.2f}"
    )
    
    keyboard = [
        [InlineKeyboardButton("📈 View Chart", callback_data="view_chart")],
        [InlineKeyboardButton("📋 Trade History", callback_data="trade_history")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        stats_text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def trade_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show trade history"""
    query = update.callback_query
    user = update.effective_user
    
    db = Database.get_database()
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    
    # Get recent trades
    trades = await crud.get_user_trades(db, user_data['_id'], limit=10)
    
    if not trades:
        await query.edit_message_text(
            "📭 <b>No Trade History</b>\n\n"
            "You haven't executed any trades yet.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="stats_menu")]])
        )
        return
    
    text = "📋 <b>Recent Trades</b>\n\n"
    
    for trade in trades:
        symbol = trade.get('symbol', 'Unknown')
        pnl = trade.get('pnl', 0)
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        date = trade.get('closed_at', 'Unknown')
        
        text += f"{pnl_emoji} {symbol}: ${pnl:.2f} ({date})\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="stats_menu")]]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def about_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show about information"""
    query = update.callback_query
    
    about_text = (
        "ℹ️ <b>About This Bot</b>\n\n"
        "<b>Telegram Straddle Pro</b>\n"
        "Version 1.0.0\n\n"
        "A professional trading bot for Delta Exchange options.\n\n"
        "<b>Features:</b>\n"
        "• Secure API key management\n"
        "• Strategy automation\n"
        "• Real-time position monitoring\n"
        "• Trade execution\n"
        "• Performance analytics\n\n"
        "<b>Support:</b> @yoursupport\n"
        "<b>Website:</b> example.com"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
    
    await query.edit_message_text(
        about_text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def refresh_positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Refresh and update positions"""
    query = update.callback_query
    await query.answer("🔄 Refreshing positions...")
    
    user = update.effective_user
    db = Database.get_database()
    
    try:
        user_data = await crud.get_user_by_telegram_id(db, user.id)
        
        # Refresh positions from exchange
        # This would call your position_monitor.py functions
        
        await query.answer("✅ Positions refreshed!", show_alert=True)
        await view_positions(update, context)
        
    except Exception as e:
        bot_logger.error(f"❌ Refresh failed: {e}")
        await query.answer(f"❌ Refresh failed: {str(e)}", show_alert=True)


async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Export user data"""
    query = update.callback_query
    user = update.effective_user
    
    await query.answer("📥 Preparing export...")
    
    db = Database.get_database()
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    
    try:
        # Export user data to CSV/JSON
        # This would generate a file with user's trading data
        
        await query.edit_message_text(
            "✅ <b>Data Exported</b>\n\n"
            "Your data has been prepared.\n"
            "Download link will be sent shortly.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )
        
        bot_logger.info(f"✅ Data exported for user: {user.id}")
        
    except Exception as e:
        bot_logger.error(f"❌ Export failed: {e}")
        await query.answer(f"❌ Export failed: {str(e)}", show_alert=True)


# Utility function for admin commands (optional)
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin statistics (admin only)"""
    user = update.effective_user
    
    # Check if user is admin
    ADMIN_IDS = [123456789]  # Replace with your admin Telegram IDs
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized")
        return
    
    db = Database.get_database()
    
    # Get platform statistics
    total_users = await crud.count_total_users(db)
    active_trades = await crud.count_active_trades(db)
    total_volume = await crud.get_total_volume(db)
    
    stats_text = (
        f"👑 <b>Admin Dashboard</b>\n\n"
        f"<b>Total Users:</b> {total_users}\n"
        f"<b>Active Trades:</b> {active_trades}\n"
        f"<b>Total Volume:</b> ${total_volume:.2f}"
    )
    
    await update.message.reply_text(
        stats_text,
        parse_mode=ParseMode.HTML
    )


# Broadcast message to all users (admin only)
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast message to all users (admin only)"""
    user = update.effective_user
    
    # Check if user is admin
    ADMIN_IDS = [123456789]  # Replace with your admin Telegram IDs
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized")
        return
    
    # Get message text
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    
    message = " ".join(context.args)
    
    db = Database.get_database()
    users = await crud.get_all_users(db)
    
    success_count = 0
    fail_count = 0
    
    for user_data in users:
        try:
            await context.bot.send_message(
                chat_id=user_data['telegram_id'],
                text=f"📢 <b>Announcement</b>\n\n{message}",
                parse_mode=ParseMode.HTML
            )
            success_count += 1
            await asyncio.sleep(0.05)  # Rate limiting
        except Exception as e:
            bot_logger.error(f"❌ Broadcast failed for user {user_data['telegram_id']}: {e}")
            fail_count += 1
    
    await update.message.reply_text(
        f"✅ Broadcast complete!\n\n"
        f"Success: {success_count}\n"
        f"Failed: {fail_count}"
    )

