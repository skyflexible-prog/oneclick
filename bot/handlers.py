from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from config.database import Database
from database import crud
from bot.keyboards import *
from bot.validators import validator
from utils.helpers import encryptor, format_currency, format_percentage, is_admin
from utils.logger import bot_logger
from trading.delta_api import DeltaExchangeAPI
from trading.straddle_logic import StraddleCalculator, StraddleExecutor
from trading.position_monitor import PositionMonitor
from typing import Dict
import asyncio

# Conversation states
(
    AWAITING_API_NICKNAME, AWAITING_API_KEY, AWAITING_API_SECRET,
    AWAITING_STRATEGY_NAME, AWAITING_LOT_SIZE, AWAITING_STOP_LOSS,
    AWAITING_TARGET, AWAITING_MAX_CAPITAL, AWAITING_STRIKE_OFFSET
) = range(9)

# User session storage
user_sessions: Dict[int, Dict] = {}


def get_user_session(user_id: int) -> Dict:
    """Get or create user session"""
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    return user_sessions[user_id]


def clear_user_session(user_id: int):
    """Clear user session data"""
    if user_id in user_sessions:
        user_sessions[user_id] = {}


# ==================== COMMAND HANDLERS ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    bot_logger.info(f"User {user.id} started the bot")
    
    db = Database.get_database()
    
    # Check if user exists
    existing_user = await crud.get_user_by_telegram_id(db, user.id)
    
    if not existing_user:
        # Create new user
        await crud.create_user(db, user.id, user.username)
        bot_logger.info(f"New user created: {user.id}")
    
    welcome_message = f"""
🎉 <b>Welcome to ATM Straddle Trading Bot!</b>

Hello {user.first_name}! 👋

This bot helps you execute <b>ATM Straddle</b> options trades on <b>Delta Exchange India</b> with single-click execution.

<b>🚀 Quick Start:</b>
1. Add your Delta Exchange API credentials
2. Create a trading strategy
3. Execute trades with one click!

<b>📊 Features:</b>
• Multi-API management
• Preset strategy configurations
• Real-time position monitoring
• Automated stop-loss and targets
• BTC & ETH options support

Use the buttons below to get started:
"""
    
    await update.message.reply_text(
        welcome_message,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
<b>📚 Bot Commands & Features</b>

<b>🔑 API Management:</b>
• /addapi - Add Delta Exchange API credentials
• /listapis - View all registered APIs
• /selectapi - Choose active API for trading

<b>🎯 Strategy Management:</b>
• /createstrategy - Configure new trading strategy
• /editstrategy - Modify existing strategy
• /liststrategy - View all saved strategies

<b>📈 Trading:</b>
• /trade - Execute trades with preset strategies
• /positions - View active positions with live P&L
• /closeposition - Close specific positions

<b>💰 Account:</b>
• /balance - Check wallet balance
• /history - View trade history

<b>❓ Support:</b>
• /help - Show this help message

<b>🔔 Features:</b>
• <b>ATM Straddle:</b> Buy/Sell both Call & Put at same strike
• <b>Single-Click Execution:</b> Trade in one tap
• <b>Auto Stop-Loss & Targets:</b> Set and forget
• <b>Multi-API Support:</b> Manage multiple accounts

<b>⚠️ Important:</b>
• Ensure API keys have trading permissions
• Start with small lot sizes
• Always set stop-loss levels
• Monitor margin requirements

Need help? Contact support or check documentation.
"""
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            help_text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")
            ]])
        )
    else:
        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /balance command"""
    user = update.effective_user
    db = Database.get_database()
    
    # Get user and active API
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    if not user_data:
        await update.message.reply_text("Please use /start first to register.")
        return
    
    apis = await crud.get_user_api_credentials(db, user_data['_id'])
    active_api = next((api for api in apis if api['is_active']), None)
    
    if not active_api:
        await update.message.reply_text(
            "❌ No active API found. Please add and select an API first.",
            reply_markup=get_api_management_keyboard()
        )
        return
    
    # Decrypt API credentials
    api_key = encryptor.decrypt(active_api['api_key_encrypted'])
    api_secret = encryptor.decrypt(active_api['api_secret_encrypted'])
    
    # Fetch balance from Delta Exchange
    async with DeltaExchangeAPI(api_key, api_secret) as api:
        balance_data = await api.get_wallet_balance()
    
    if 'error' in balance_data:
        await update.message.reply_text(
            f"❌ Error fetching balance: {balance_data.get('error')}",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Parse balance data
    balance_text = f"<b>💰 Wallet Balance - {active_api['nickname']}</b>\n\n"
    
    if 'result' in balance_data:
        for wallet in balance_data['result']:
            asset = wallet.get('asset_symbol', 'Unknown')
            balance = float(wallet.get('balance', 0))
            available = float(wallet.get('available_balance', 0))
            
            if asset == 'INR':
                balance_text += f"<b>Asset:</b> {asset}\n"
                balance_text += f"<b>Total Balance:</b> {format_currency(balance)}\n"
                balance_text += f"<b>Available:</b> {format_currency(available)}\n"
                balance_text += f"<b>In Use:</b> {format_currency(balance - available)}\n"
    else:
        balance_text += "No balance data available."
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            balance_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            balance_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )


# ==================== API MANAGEMENT HANDLERS ====================

async def add_api_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start API addition conversation"""
    user = update.effective_user
    session = get_user_session(user.id)
    session['adding_api'] = True
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "🔑 <b>Add Delta Exchange API</b>\n\n"
        "Please provide a nickname for this API (e.g., 'Main Trading Account'):",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard()
    )
    
    return AWAITING_API_NICKNAME


async def receive_api_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive API nickname"""
    user = update.effective_user
    session = get_user_session(user.id)
    nickname = update.message.text
    
    # Validate nickname
    is_valid, message = validator.validate_nickname(nickname)
    if not is_valid:
        await update.message.reply_text(
            f"❌ {message}\n\nPlease provide a valid nickname:",
            reply_markup=get_cancel_keyboard()
        )
        return AWAITING_API_NICKNAME
    
    session['api_nickname'] = nickname
    
    await update.message.reply_text(
        f"✅ Nickname: <b>{nickname}</b>\n\n"
        "Now, please send your <b>Delta Exchange API Key</b>:\n\n"
        "⚠️ <i>Make sure you're in a private chat. Never share API keys publicly!</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard()
    )
    
    return AWAITING_API_KEY


async def receive_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive API key"""
    user = update.effective_user
    session = get_user_session(user.id)
    api_key = update.message.text.strip()
    
    # Delete message for security
    await update.message.delete()
    
    # Validate API key
    is_valid, message = validator.validate_api_key(api_key)
    if not is_valid:
        await context.bot.send_message(
            chat_id=user.id,
            text=f"❌ {message}\n\nPlease send a valid API key:",
            reply_markup=get_cancel_keyboard()
        )
        return AWAITING_API_KEY
    
    session['api_key'] = api_key
    
    await context.bot.send_message(
        chat_id=user.id,
        text="✅ API Key received!\n\n"
             "Now, please send your <b>Delta Exchange API Secret</b>:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard()
    )
    
    return AWAITING_API_SECRET


async def receive_api_secret(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive API secret and save credentials"""
    user = update.effective_user
    session = get_user_session(user.id)
    api_secret = update.message.text.strip()
    
    # Delete message for security
    await update.message.delete()
    
    # Validate API secret
    is_valid, message = validator.validate_api_secret(api_secret)
    if not is_valid:
        await context.bot.send_message(
            chat_id=user.id,
            text=f"❌ {message}\n\nPlease send a valid API secret:",
            reply_markup=get_cancel_keyboard()
        )
        return AWAITING_API_SECRET
    
    # Test API credentials
    await context.bot.send_message(
        chat_id=user.id,
        text="🔄 Testing API credentials..."
    )
    
    async with DeltaExchangeAPI(session['api_key'], api_secret) as api:
        test_result = await api.get_wallet_balance()
    
    if 'error' in test_result:
        await context.bot.send_message(
            chat_id=user.id,
            text=f"❌ API test failed: {test_result.get('error')}\n\n"
                 "Please check your credentials and try again.",
            reply_markup=get_api_management_keyboard()
        )
        clear_user_session(user.id)
        return ConversationHandler.END
    
    # Encrypt and save credentials
    db = Database.get_database()
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    
    encrypted_key = encryptor.encrypt(session['api_key'])
    encrypted_secret = encryptor.encrypt(api_secret)
    
    api_id = await crud.create_api_credential(
        db,
        user_data['_id'],
        session['api_nickname'],
        encrypted_key,
        encrypted_secret
    )
    
    # Set as active if first API
    apis = await crud.get_user_api_credentials(db, user_data['_id'])
    if len(apis) == 1:
        await crud.set_active_api(db, user_data['_id'], api_id)
    
    await context.bot.send_message(
        chat_id=user.id,
        text=f"✅ <b>API credentials saved successfully!</b>\n\n"
             f"<b>Nickname:</b> {session['api_nickname']}\n"
             f"<b>Status:</b> Active\n\n"
             "You can now create trading strategies.",
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu_keyboard()
    )
    
    clear_user_session(user.id)
    return ConversationHandler.END


async def list_apis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all user APIs"""
    user = update.effective_user
    db = Database.get_database()
    
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    if not user_data:
        await update.callback_query.answer("Please use /start first")
        return
    
    apis = await crud.get_user_api_credentials(db, user_data['_id'])
    
    if not apis:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "📋 <b>API Credentials</b>\n\n"
            "You haven't added any API credentials yet.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_api_management_keyboard()
        )
        return
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "📋 <b>Your API Credentials</b>\n\n"
        "Select an API to view details:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_api_list_keyboard(apis)
    )


async def view_api_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View specific API details"""
    query = update.callback_query
    api_id = query.data.split('_')[-1]
    
    db = Database.get_database()
    api_data = await crud.get_api_credential_by_id(db, api_id)
    
    if not api_data:
        await query.answer("API not found", show_alert=True)
        return
    
    status = "✅ Active" if api_data['is_active'] else "⚪ Inactive"
    
    details_text = f"""
<b>🔑 API Details</b>

<b>Nickname:</b> {api_data['nickname']}
<b>Status:</b> {status}
<b>Added:</b> {api_data['created_at'].strftime('%Y-%m-%d %H:%M')}

<b>API Key:</b> <code>{api_data['api_key_encrypted'][:20]}...</code>
"""
    
    await query.answer()
    await query.edit_message_text(
        details_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_api_action_keyboard(api_id)
    )


# ==================== CALLBACK QUERY HANDLERS ====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all button callbacks"""
    query = update.callback_query
    data = query.data
    
    # Main menu
    if data == "main_menu":
        await query.answer()
        await query.edit_message_text(
            "🏠 <b>Main Menu</b>\n\nSelect an option:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )
    
    # Help
    elif data == "help":
        await help_command(update, context)
    
    # Balance
    elif data == "balance":
        await balance_command(update, context)
    
    # API Management
    elif data == "api_menu":
        await query.answer()
        await query.edit_message_text(
            "⚙️ <b>API Management</b>\n\nManage your Delta Exchange API credentials:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_api_management_keyboard()
        )
    
    elif data == "list_apis":
        await list_apis(update, context)
    
    elif data.startswith("view_api_"):
        await view_api_details(update, context)
    
    elif data.startswith("activate_api_"):
        api_id = data.split('_')[-1]
        user = update.effective_user
        db = Database.get_database()
        user_data = await crud.get_user_by_telegram_id(db, user.id)
        await crud.set_active_api(db, user_data['_id'], api_id)
        await query.answer("✅ API activated!", show_alert=True)
        await view_api_details(update, context)
    
    # More handlers will be added in next part...
  
