from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from bson import ObjectId
from config.database import Database
from database import crud
from bot.keyboards import *
from bot.validators import validator
from utils.helpers import encryptor, format_currency, format_percentage, is_admin
from utils.logger import bot_logger
from trading.delta_api import DeltaExchangeAPI
from trading.straddle_logic import StraddleCalculator, StraddleExecutor
from trading.position_monitor import PositionMonitor
from bson import ObjectId
from typing import Dict
import asyncio

# Trade states
SELECTING_API = 50
SELECTING_STRATEGY = 51
CONFIRMING_TRADE = 52

# Conversation states
(
    AWAITING_API_NICKNAME, AWAITING_API_KEY, AWAITING_API_SECRET,
    AWAITING_STRATEGY_NAME, AWAITING_LOT_SIZE, AWAITING_STOP_LOSS,
    AWAITING_TARGET, AWAITING_MAX_CAPITAL, AWAITING_STRIKE_OFFSET,
    AWAITING_SL_ORDER_CHOICE, AWAITING_SL_TRIGGER, AWAITING_SL_LIMIT,  # ✅ NEW
    AWAITING_TARGET_ORDER_CHOICE  # ✅ NEW
) = range(13)  # ✅ Changed from range(9) to range(13)

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
    """Show wallet balance for ALL APIs - Called from /balance command"""
    await update.message.reply_text("🔄 Fetching balances from all APIs...")
    
    db = Database.get_database()
    user = update.effective_user
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    
    if not user_data:
        await update.message.reply_text(
            "❌ User not found. Please use /start first.",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Get all API credentials for this user
    apis = await crud.get_user_apis(db, user_data['_id'])
    
    if not apis:
        await update.message.reply_text(
            "❌ No API credentials found.\n\n"
            "Please add your Delta Exchange API credentials first.",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # ✅ Fetch balance from each API
    balance_text = "💰 <b>Account Balances</b>\n\n"
    total_balance = 0
    total_available = 0
    
    for idx, api in enumerate(apis, 1):
        try:
            # Decrypt credentials
            api_key = encryptor.decrypt(api['api_key_encrypted'])
            api_secret = encryptor.decrypt(api['api_secret_encrypted'])
            
            # Get balance
            async with DeltaExchangeAPI(api_key, api_secret) as delta_api:
                balance = await delta_api.get_wallet_balance()
            
            available = float(balance.get('available_balance', 0))
            wallet = float(balance.get('balance', 0))
            total_balance += wallet
            total_available += available
            
            balance_text += (
                f"<b>{idx}. {api.get('nickname', 'Unnamed API')}</b>\n"
                f"   💵 Total: <b>${wallet:,.2f}</b>\n"
                f"   ✅ Available: <b>${available:,.2f}</b>\n"
                f"   🔒 In Use: ${(wallet - available):,.2f}\n\n"
            )
            
        except Exception as e:
            balance_text += (
                f"<b>{idx}. {api.get('nickname', 'Unnamed API')}</b>\n"
                f"   ❌ Error: {str(e)[:50]}\n\n"
            )
    
    # Add totals
    if total_balance > 0:
        balance_text += (
            f"<b>📊 TOTAL ACROSS ALL ACCOUNTS</b>\n"
            f"💵 Total: <b>${total_balance:,.2f}</b>\n"
            f"✅ Available: <b>${total_available:,.2f}</b>\n"
            f"🔒 In Use: ${(total_balance - total_available):,.2f}"
        )
    
    await update.message.reply_text(
        balance_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu_keyboard()
    )

async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show wallet balance for ALL APIs - Called from button click"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("🔄 Fetching balances from all APIs...")
    
    db = Database.get_database()
    user = query.from_user
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    
    if not user_data:
        await query.edit_message_text(
            "❌ User not found. Please use /start first.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Get all API credentials for this user
    apis = await crud.get_user_api_credentials(db, user_data['_id'])
    
    if not apis:
        await query.edit_message_text(
            "❌ No API credentials found.\n\n"
            "Please add your Delta Exchange API credentials first.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Fetch balance from each API
    balance_text = "💰 <b>Account Balances</b>\n\n"
    total_balance = 0
    total_available = 0
    
    for idx, api in enumerate(apis, 1):
        try:
            # Decrypt credentials
            api_key = encryptor.decrypt(api['api_key_encrypted'])
            api_secret = encryptor.decrypt(api['api_secret_encrypted'])
            
            # Get balance
            async with DeltaExchangeAPI(api_key, api_secret) as delta_api:
                balance_response = await delta_api.get_wallet_balance()
            
            # ✅ FIX: Delta Exchange returns balance in 'result' array
            if 'result' in balance_response and balance_response['result']:
                # Get the first wallet (usually USDT or INR)
                wallet_data = balance_response['result'][0]
                
                available = float(wallet_data.get('available_balance', 0))
                wallet = float(wallet_data.get('balance', 0))
                currency = wallet_data.get('asset_symbol', 'USD')
                
                total_balance += wallet
                total_available += available
                
                balance_text += (
                    f"<b>{idx}. {api.get('nickname', 'Unnamed API')}</b>\n"
                    f"   💵 Total: <b>${wallet:,.2f} {currency}</b>\n"
                    f"   ✅ Available: <b>${available:,.2f}</b>\n"
                    f"   🔒 In Use: ${(wallet - available):,.2f}\n\n"
                )
            else:
                balance_text += (
                    f"<b>{idx}. {api.get('nickname', 'Unnamed API')}</b>\n"
                    f"   ❌ No balance data available\n\n"
                )
            
        except Exception as e:
            bot_logger.error(f"Error fetching balance for {api.get('nickname')}: {e}")
            balance_text += (
                f"<b>{idx}. {api.get('nickname', 'Unnamed API')}</b>\n"
                f"   ❌ Error: {str(e)[:50]}\n\n"
            )
    
    # Add totals
    if total_balance > 0:
        balance_text += (
            f"<b>📊 TOTAL ACROSS ALL ACCOUNTS</b>\n"
            f"💵 Total: <b>${total_balance:,.2f}</b>\n"
            f"✅ Available: <b>${total_available:,.2f}</b>\n"
            f"🔒 In Use: ${(total_balance - total_available):,.2f}"
        )
    
    await query.edit_message_text(
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


async def activate_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Activate API"""
    query = update.callback_query
    api_id = query.data.split('_')[-1]
    user = query.from_user
    
    db = Database.get_database()
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    await crud.set_active_api(db, user_data['_id'], api_id)
    
    await query.answer("✅ API activated!", show_alert=True)
    await view_api_details(update, context)


async def delete_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete API"""
    query = update.callback_query
    api_id = query.data.split('_')[-1]
    
    db = Database.get_database()
    await crud.delete_api_credential(db, api_id)
    
    await query.answer("✅ API deleted!", show_alert=True)
    await list_apis(update, context)


# ==================== CALLBACK QUERY HANDLERS ====================

# bot/handlers.py - UPDATE button_callback

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all button callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # ✅ SKIP strangle callbacks - let ConversationHandler handle them
    if data.startswith("strangle_"):
        return  # Let strangle_conv_handler handle it
    
    # Main menu
    if data == "main_menu":
        await query.edit_message_text(
            "🏠 <b>Main Menu</b>\n\n"
            "Select an option:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()  # ✅ USE UPDATED KEYBOARD
        )
        return
    
    # ✅ ADD THIS - Strangle Menu Handler
    elif data == "strangle_menu":
        strangle_text = (
            "🎲 <b>Strangle Strategy</b>\n\n"
            "A strangle involves buying/selling OTM call and put options.\n\n"
            "<b>Features:</b>\n"
            "• <b>Long Strangle:</b> Buy OTM Call + Put\n"
            "• <b>Short Strangle:</b> Sell OTM Call + Put\n"
            "• Percentage or ATM offset strike selection\n"
            "• Advanced stop-loss options\n\n"
            "Choose an option:"
        )
        
        keyboard = [
            [InlineKeyboardButton("📝 Create Preset", callback_data="strangle_create")],
            [InlineKeyboardButton("▶️ Execute Preset", callback_data="strangle_execute")],
            [InlineKeyboardButton("📋 Manage Presets", callback_data="strangle_manage")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            strangle_text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # Help
    elif data == "help":
        help_text = (
            "❓ <b>Help & Support</b>\n\n"
            "<b>How to use this bot:</b>\n\n"
            "1️⃣ <b>Add API Keys:</b>\n"
            "   • Click 'API Keys'\n"
            "   • Add your Delta Exchange credentials\n"
            "   • Activate the API you want to use\n\n"
            "2️⃣ <b>Create Strategy:</b>\n"
            "   • Click 'Strategies'\n"
            "   • Configure your trading parameters\n"
            "   • Save the strategy\n\n"
            "3️⃣ <b>Execute Trade:</b>\n"
            "   • Click 'Trade'\n"
            "   • Select your strategy\n"
            "   • Confirm execution\n\n"
            "<b>📊 Features:</b>\n"
            "• <b>Trade:</b> Execute preset strategies\n"
            "• <b>Orders:</b> View and manage orders\n"
            "• <b>Positions:</b> Monitor open positions\n"
            "• <b>Strangle:</b> Create strangle strategies\n"  # ✅ MENTIONED
            "• <b>History:</b> View past trades\n"
            "• <b>Balance:</b> Check account balance\n\n"
            "<b>Need help?</b> Contact support."
        )
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            help_text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # If no match, show main menu
    await query.edit_message_text(
        "Please select an option:",
        reply_markup=get_main_menu_keyboard()
    )

# ==================== STRATEGY MANAGEMENT HANDLERS ====================

async def create_strategy_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start strategy creation conversation"""
    user = update.effective_user
    db = Database.get_database()
    
    # Check if user has active API
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    apis = await crud.get_user_api_credentials(db, user_data['_id'])
    active_api = next((api for api in apis if api['is_active']), None)
    
    if not active_api:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "❌ You need to add an API first before creating strategies.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_api_management_keyboard()
        )
        return ConversationHandler.END
    
    session = get_user_session(user.id)
    session['creating_strategy'] = True
    session['strategy_data'] = {'api_id': active_api['_id']}
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "🎯 <b>Create New Strategy</b>\n\n"
        "Please provide a name for this strategy (e.g., 'BTC_Weekly_Conservative'):",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard()
    )
    
    return AWAITING_STRATEGY_NAME


async def receive_strategy_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive strategy name"""
    user = update.effective_user
    session = get_user_session(user.id)
    name = update.message.text
    
    # Validate name
    is_valid, message = validator.validate_nickname(name)
    if not is_valid:
        await update.message.reply_text(
            f"❌ {message}\n\nPlease provide a valid strategy name:",
            reply_markup=get_cancel_keyboard()
        )
        return AWAITING_STRATEGY_NAME
    
    session['strategy_data']['name'] = name
    
    await update.message.reply_text(
        f"✅ Strategy Name: <b>{name}</b>\n\n"
        "Now select the <b>underlying asset</b>:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_underlying_keyboard()
    )


async def receive_underlying(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive underlying asset selection"""
    query = update.callback_query
    user = query.from_user
    session = get_user_session(user.id)
    
    underlying = query.data.split('_')[-1]
    session['strategy_data']['underlying'] = underlying
    
    await query.answer()
    await query.edit_message_text(
        f"✅ Underlying: <b>{underlying}</b>\n\n"
        "Now select the <b>straddle direction</b>:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_direction_keyboard()
    )


async def receive_direction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive direction selection"""
    query = update.callback_query
    user = query.from_user
    session = get_user_session(user.id)
    
    direction = query.data.split('_')[-1]
    session['strategy_data']['direction'] = direction
    
    direction_text = "Long Straddle (Buy Call + Put)" if direction == "long" else "Short Straddle (Sell Call + Put)"
    
    await query.answer()
    await query.edit_message_text(
        f"✅ Direction: <b>{direction_text}</b>\n\n"
        "Now select the <b>expiry type</b>:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_expiry_keyboard()
    )


async def receive_expiry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive expiry type selection"""
    query = update.callback_query
    user = query.from_user
    session = get_user_session(user.id)
    
    expiry_type = query.data.split('_')[-1]
    session['strategy_data']['expiry_type'] = expiry_type
    
    await query.answer()
    await query.edit_message_text(
        f"✅ Expiry: <b>{expiry_type.capitalize()}</b>\n\n"
        "Please enter the <b>lot size</b> (number of contracts):",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard()
    )
    
    return AWAITING_LOT_SIZE


async def receive_lot_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive lot size"""
    user = update.effective_user
    session = get_user_session(user.id)
    
    is_valid, message, lot_size = validator.validate_lot_size(update.message.text)
    if not is_valid:
        await update.message.reply_text(
            f"❌ {message}\n\nPlease enter a valid lot size:",
            reply_markup=get_cancel_keyboard()
        )
        return AWAITING_LOT_SIZE
    
    session['strategy_data']['lot_size'] = lot_size
    
    await update.message.reply_text(
        f"✅ Lot Size: <b>{lot_size}</b>\n\n"
        "Please enter the <b>stop loss percentage</b> (e.g., 20 for 20%):",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard()
    )
    
    return AWAITING_STOP_LOSS


async def receive_stop_loss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive stop loss percentage"""
    user = update.effective_user
    session = get_user_session(user.id)
    
    is_valid, message, sl_pct = validator.validate_percentage(update.message.text)
    if not is_valid:
        await update.message.reply_text(
            f"❌ {message}\n\nPlease enter a valid stop loss percentage:",
            reply_markup=get_cancel_keyboard()
        )
        return AWAITING_STOP_LOSS
    
    session['strategy_data']['stop_loss_pct'] = sl_pct
    
    # ✅ ASK IF USER WANTS AUTO STOP-LOSS ORDERS
    await update.message.reply_text(
        f"✅ Stop Loss: <b>{sl_pct}%</b>\n\n"
        "📊 <b>Automatic Stop-Loss Orders</b>\n\n"
        "Do you want to place automatic stop-loss orders on Delta Exchange when trade is executed?\n\n"
        "✅ <b>Yes:</b> Stop-loss orders will be placed automatically\n"
        "❌ <b>No:</b> Manual monitoring only",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes, place SL orders", callback_data="sl_order_yes"),
                InlineKeyboardButton("❌ No, manual only", callback_data="sl_order_no")
            ]
        ])
    )
    
    return AWAITING_SL_ORDER_CHOICE  # ✅ NEW STATE


async def receive_sl_order_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle stop-loss order choice"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    session = get_user_session(user_id)
    
    if query.data == "sl_order_yes":
        session['strategy_data']['use_stop_loss_order'] = True
        
        await query.edit_message_text(
            "📊 <b>Stop-Loss Trigger Percentage</b>\n\n"
            "At what percentage loss should the stop-loss order trigger?\n\n"
            "Example: Enter <b>50</b> for 50% loss\n\n"
            "💡 <b>Tip:</b> This should be same or slightly less than your stop-loss %",
            parse_mode=ParseMode.HTML
        )
        
        return AWAITING_SL_TRIGGER
    
    else:
        session['strategy_data']['use_stop_loss_order'] = False
        session['strategy_data']['sl_trigger_pct'] = None
        session['strategy_data']['sl_limit_pct'] = None
        
        await query.edit_message_text(
            "🎯 <b>Target Profit (Optional)</b>\n\n"
            "Enter target profit percentage, or enter <b>0</b> to skip:",
            parse_mode=ParseMode.HTML
        )
        
        return AWAITING_TARGET


async def receive_sl_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive SL trigger percentage"""
    message = update.message
    user_id = message.from_user.id
    
    try:
        sl_trigger_pct = float(message.text)
        
        if sl_trigger_pct <= 0 or sl_trigger_pct > 100:
            await message.reply_text(
                "❌ Invalid percentage. Please enter between 0 and 100:",
                reply_markup=get_cancel_keyboard()
            )
            return AWAITING_SL_TRIGGER
        
        session = get_user_session(user_id)
        session['strategy_data']['sl_trigger_pct'] = sl_trigger_pct
        
        await message.reply_text(
            "📊 <b>Stop-Loss Limit Percentage</b>\n\n"
            "At what percentage should the limit order be placed?\n\n"
            "Example: Enter <b>55</b> for 55% loss (5% buffer from trigger)\n\n"
            "💡 <b>Tip:</b> This should be slightly higher than trigger % to ensure order fills",
            parse_mode=ParseMode.HTML,
            reply_markup=get_cancel_keyboard()
        )
        
        return AWAITING_SL_LIMIT
        
    except ValueError:
        await message.reply_text(
            "❌ Invalid number. Please enter trigger percentage:",
            reply_markup=get_cancel_keyboard()
        )
        return AWAITING_SL_TRIGGER


async def receive_sl_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive SL limit percentage"""
    message = update.message
    user_id = message.from_user.id
    
    try:
        sl_limit_pct = float(message.text)
        
        if sl_limit_pct <= 0 or sl_limit_pct > 100:
            await message.reply_text(
                "❌ Invalid percentage. Please enter between 0 and 100:",
                reply_markup=get_cancel_keyboard()
            )
            return AWAITING_SL_LIMIT
        
        session = get_user_session(user_id)
        session['strategy_data']['sl_limit_pct'] = sl_limit_pct
        
        await message.reply_text(
            "🎯 <b>Target Profit (Optional)</b>\n\n"
            "Enter target profit percentage, or enter <b>0</b> to skip:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_cancel_keyboard()
        )
        
        return AWAITING_TARGET
        
    except ValueError:
        await message.reply_text(
            "❌ Invalid number. Please enter limit percentage:",
            reply_markup=get_cancel_keyboard()
        )
        return AWAITING_SL_LIMIT


async def receive_target_order_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle target order choice"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    session = get_user_session(user_id)
    
    if query.data == "target_order_yes":
        session['strategy_data']['use_target_order'] = True
        session['strategy_data']['target_trigger_pct'] = session['strategy_data']['target_pct']
    else:
        session['strategy_data']['use_target_order'] = False
        session['strategy_data']['target_trigger_pct'] = None
    
    await query.edit_message_text(
        "💰 <b>Maximum Capital (Optional)</b>\n\n"
        "Enter maximum capital to use for this strategy, or enter <b>0</b> to skip:",
        parse_mode=ParseMode.HTML
    )
    
    return AWAITING_MAX_CAPITAL
    

async def receive_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive target profit percentage"""
    user = update.effective_user
    session = get_user_session(user.id)
    
    # ✅ Manual validation without using validator
    try:
        target_pct = float(update.message.text)
        
        if target_pct < 0 or target_pct > 500:
            await update.message.reply_text(
                "❌ Invalid percentage. Please enter between 0 and 500:",
                reply_markup=get_cancel_keyboard()
            )
            return AWAITING_TARGET
        
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid number. Please enter target percentage or 0 to skip:",
            reply_markup=get_cancel_keyboard()
        )
        return AWAITING_TARGET
    
    session['strategy_data']['target_pct'] = target_pct if target_pct > 0 else None
    
    # ✅ IF TARGET > 0, ASK ABOUT AUTO TARGET ORDERS
    if target_pct > 0:
        await update.message.reply_text(
            f"✅ Target: <b>{target_pct}%</b>\n\n"
            "📊 <b>Automatic Target Orders</b>\n\n"
            "Do you want to place automatic target (take-profit) orders?\n\n"
            "✅ <b>Yes:</b> Target orders will be placed automatically\n"
            "❌ <b>No:</b> Manual exit at target",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Yes, place target orders", callback_data="target_order_yes"),
                    InlineKeyboardButton("❌ No, manual exit", callback_data="target_order_no")
                ]
            ])
        )
        return AWAITING_TARGET_ORDER_CHOICE
    else:
        # No target (0 entered), skip to max capital
        session['strategy_data']['use_target_order'] = False
        session['strategy_data']['target_trigger_pct'] = None
        
        await update.message.reply_text(
            "💰 <b>Maximum Capital (Optional)</b>\n\n"
            "Enter maximum capital to use for this strategy, or enter <b>0</b> to skip:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_cancel_keyboard()
        )
        return AWAITING_MAX_CAPITAL


async def receive_target_order_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle target order choice"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    session = get_user_session(user_id)
    
    if query.data == "target_order_yes":
        session['strategy_data']['use_target_order'] = True
        session['strategy_data']['target_trigger_pct'] = session['strategy_data']['target_pct']
    else:
        session['strategy_data']['use_target_order'] = False
        session['strategy_data']['target_trigger_pct'] = None
    
    await query.edit_message_text(
        "💰 <b>Maximum Capital (Optional)</b>\n\n"
        "Enter maximum capital to use for this strategy, or enter <b>0</b> to skip:",
        parse_mode=ParseMode.HTML
    )
    
    return AWAITING_MAX_CAPITAL


async def receive_max_capital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive max capital"""
    user = update.effective_user
    session = get_user_session(user.id)
    
    is_valid, message, capital = validator.validate_capital(update.message.text)
    if not is_valid:
        await update.message.reply_text(
            f"❌ {message}\n\nPlease enter a valid capital amount or 0 for unlimited:",
            reply_markup=get_cancel_keyboard()
        )
        return AWAITING_MAX_CAPITAL
    
    session['strategy_data']['max_capital'] = capital
    
    # ✅ Show "Unlimited" if capital is 0
    if capital == 0:
        capital_display = "<b>Unlimited</b>"
    else:
        capital_display = f"<b>{format_currency(capital)}</b>"
    
    await update.message.reply_text(
        f"✅ Max Capital: {capital_display}\n\n"
        "Please enter the <b>strike offset</b> from ATM (0 for ATM, +100 for 100 points OTM, -100 for 100 points ITM):",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard()
    )
    
    return AWAITING_STRIKE_OFFSET


async def receive_strike_offset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive strike offset and save strategy"""
    user = update.effective_user
    session = get_user_session(user.id)
    
    is_valid, message, offset = validator.validate_strike_offset(update.message.text)
    if not is_valid:
        await update.message.reply_text(
            f"❌ {message}\n\nPlease enter a valid strike offset:",
            reply_markup=get_cancel_keyboard()
        )
        return AWAITING_STRIKE_OFFSET
    
    session['strategy_data']['strike_offset'] = offset
    session['strategy_data']['trailing_sl'] = False  # Default value
    
    # Save strategy to database
    db = Database.get_database()
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    session['strategy_data']['user_id'] = user_data['_id']
    
    strategy_id = await crud.create_strategy(db, session['strategy_data'])
    
    # Build summary
    strategy = session['strategy_data']
    direction_text = "Long Straddle" if strategy['direction'] == 'long' else "Short Straddle"
    target_text = f"{strategy['target_pct']}%" if strategy.get('target_pct') else "Not Set"
    
    summary = f"""
✅ <b>Strategy Created Successfully!</b>

<b>📊 Strategy Details:</b>
<b>Name:</b> {strategy['name']}
<b>Underlying:</b> {strategy['underlying']}
<b>Direction:</b> {direction_text}
<b>Expiry:</b> {strategy['expiry_type'].capitalize()}
<b>Lot Size:</b> {strategy['lot_size']}
<b>Stop Loss:</b> {strategy['stop_loss_pct']}%
<b>Target:</b> {target_text}
<b>Max Capital:</b> {format_currency(strategy['max_capital'])}
<b>Strike Offset:</b> {strategy['strike_offset']} ({"ATM" if offset == 0 else "OTM" if offset > 0 else "ITM"})

You can now execute this strategy with one click using /trade command!
"""
    
    await update.message.reply_text(
        summary,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu_keyboard()
    )
    
    clear_user_session(user.id)
    return ConversationHandler.END


# bot/handlers.py

async def list_strategies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all user strategies"""
    query = update.callback_query
    if query:
        await query.answer()
        user = query.from_user
    else:
        user = update.message.from_user
    
    db = Database.get_database()
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    
    if not user_data:
        message = "❌ User not found. Please use /start first."
        if query:
            await query.edit_message_text(message, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(message, parse_mode=ParseMode.HTML)
        return
    
    # Get all strategies for this user
    strategies = await crud.get_user_strategies(db, user_data['_id'])
    
    if not strategies or len(strategies) == 0:
        message = (
            "<b>📊 Your Strategies</b>\n\n"
            "No strategies found.\n\n"
            "Create your first strategy to start trading!"
        )
        keyboard = [
            [InlineKeyboardButton("➕ Create Strategy", callback_data="create_strategy")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
        ]
    else:
        message = f"<b>📊 Your Strategies ({len(strategies)})</b>\n\n"
        
        keyboard = []
        for idx, strategy in enumerate(strategies[:10], 1):  # Limit to 10
            name = strategy.get('name', 'Unnamed')
            underlying = strategy.get('underlying', 'N/A')
            direction = strategy.get('direction', 'N/A')
            expiry = strategy.get('expiry_type', 'N/A')
            
            message += f"<b>{idx}. {name}</b>\n"
            message += f"   {underlying} | {direction} | {expiry}\n\n"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"{idx}. {name}",
                    callback_data=f"view_strategy_{strategy['_id']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("➕ Create New", callback_data="create_strategy")])
        keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")])
    
    if query:
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def view_strategy_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View specific strategy details"""
    query = update.callback_query
    strategy_id = query.data.split('_')[-1]
    
    db = Database.get_database()
    strategy = await crud.get_strategy_by_id(db, strategy_id)
    
    if not strategy:
        await query.answer("Strategy not found", show_alert=True)
        return
    
    direction_text = "📈 Long Straddle" if strategy['direction'] == 'long' else "📉 Short Straddle"
    target_text = f"{strategy.get('target_pct', 0)}%" if strategy.get('target_pct') else "Not Set"
    
    details_text = f"""
<b>🎯 Strategy Details</b>

<b>Name:</b> {strategy['name']}
<b>Direction:</b> {direction_text}
<b>Underlying:</b> {strategy['underlying']}
<b>Expiry:</b> {strategy['expiry_type'].capitalize()}

<b>📊 Parameters:</b>
<b>Lot Size:</b> {strategy['lot_size']}
<b>Stop Loss:</b> {strategy['stop_loss_pct']}%
<b>Target:</b> {target_text}
<b>Max Capital:</b> {format_currency(strategy['max_capital'])}
<b>Strike Offset:</b> {strategy['strike_offset']}

<b>Created:</b> {strategy['created_at'].strftime('%Y-%m-%d %H:%M')}
"""
    
    await query.answer()
    await query.edit_message_text(
        details_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_strategy_action_keyboard(strategy_id)
    )


async def delete_strategy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a strategy"""
    query = update.callback_query
    strategy_id = query.data.split('_')[-1]
    
    db = Database.get_database()
    await crud.delete_strategy(db, strategy_id)
    
    await query.answer("✅ Strategy deleted!", show_alert=True)
    await list_strategies(update, context)


# ==================== TRADE EXECUTION HANDLERS ====================

async def trade_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show trade menu - Step 1: Select API"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    db = Database.get_database()
    
    # Get user's API credentials
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    apis = await crud.get_user_api_credentials(db, user_data['_id'])
    
    if not apis:
        await query.edit_message_text(
            "⚠️ <b>No API Credentials</b>\n\n"
            "Please add your Delta Exchange API credentials first.\n\n"
            "Go to <b>APIs</b> → <b>Add New API</b>",
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
    
    # Extract API ID from callback data: trade_api_{api_id}
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
            "Please create a trading strategy first.\n\n"
            "Go to <b>Strategies</b> → <b>Create New Strategy</b>",
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
    
    # Get API credentials - use selected API or strategy's default
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    selected_api_id = context.user_data.get('selected_api_id')

    if selected_api_id:
        # Use the API selected in trade_menu
        api_data = await crud.get_api_credential_by_id(db, ObjectId(selected_api_id))
    else:
        # Fallback to strategy's default API
        api_data = await crud.get_api_credential_by_id(db, strategy['api_id'])
    
    if not api_data:
        await query.edit_message_text(
            "❌ API credentials not found.",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END

    api_key = encryptor.decrypt(api_data['api_key_encrypted'])
    api_secret = encryptor.decrypt(api_data['api_secret_encrypted'])
    
    await query.answer()
    await query.edit_message_text(
        "🔄 <b>Calculating trade details...</b>",
        parse_mode=ParseMode.HTML
    )
    
    try:
        # Fetch market data
        async with DeltaExchangeAPI(api_key, api_secret) as api:
            calculator = StraddleCalculator(api)
            
            # Get spot price and ATM strike
            spot_price = await api.get_spot_price(strategy['underlying'])
            if not spot_price:
                await query.edit_message_text(
                    "❌ Failed to fetch spot price. Please try again.",
                    reply_markup=get_main_menu_keyboard()
                )
                return ConversationHandler.END
            
            # Get option chain first to get available strikes
            options = await calculator.get_option_chain(
                strategy['underlying'],
                strategy['expiry_type']
            )
            
            if not options:
                await query.edit_message_text(
                    "❌ No options available for selected criteria.",
                    reply_markup=get_main_menu_keyboard()
                )
                return ConversationHandler.END
            
            # Get available strikes
            available_strikes = sorted(set([float(o.get('strike_price', 0)) 
                                           for o in options if 'strike_price' in o]))
            
            # Calculate ATM strike with available strikes
            atm_strike = await calculator.get_atm_strike(
                strategy['underlying'],
                strategy.get('strike_offset', 0),
                available_strikes
            )
            
            if not atm_strike:
                await query.edit_message_text(
                    "❌ Failed to calculate ATM strike. Please try again.",
                    reply_markup=get_main_menu_keyboard()
                )
                return ConversationHandler.END
            
            # Find option contracts
            call_contract, put_contract = await calculator.find_option_contracts(
                strategy['underlying'],
                atm_strike,
                strategy['expiry_type']
            )
            
            if not call_contract or not put_contract:
                await query.edit_message_text(
                    "❌ Failed to find option contracts. Please check expiry settings.",
                    reply_markup=get_main_menu_keyboard()
                )
                return ConversationHandler.END
            
            # Get premiums
            call_premium, put_premium = await calculator.get_option_premiums(
                call_contract['symbol'],
                put_contract['symbol']
            )
            
            if not call_premium or not put_premium:
                await query.edit_message_text(
                    "❌ Failed to fetch option premiums. Please try again.",
                    reply_markup=get_main_menu_keyboard()
                )
                return ConversationHandler.END
            
            # ✅ FIX: Get contract size for display calculations
            call_contract_size = float(call_contract.get('contract_value', 0.001))
            put_contract_size = float(put_contract.get('contract_value', 0.001))
            
            bot_logger.info(f"Contract sizes - Call: {call_contract_size} BTC, Put: {put_contract_size} BTC")
            
            # Calculate premiums
            total_premium = call_premium + put_premium
            lot_size = strategy.get('lot_size', 1)
            
            # ✅ IMPORTANT: Two different calculations
            # 1. total_cost_notional: For display only (actual USD cost)
            # 2. lot_size: Keep original for order execution
            total_cost_notional = (call_premium * call_contract_size + put_premium * put_contract_size) * lot_size
            
            bot_logger.info(f"Premium per BTC: ${total_premium:.2f}")
            bot_logger.info(f"Lot size: {lot_size}")
            bot_logger.info(f"Total cost (notional): ${total_cost_notional:.2f}")
            
            # Calculate SL and Target based on NOTIONAL cost
            stop_loss_pct = strategy.get('stop_loss_pct', 0)
            target_pct = strategy.get('target_pct')
            
            # Calculate stop loss
            stop_loss_value = 0
            stop_loss_amount = 0
            
            if stop_loss_pct > 0:
                if strategy['direction'] == 'long':
                    # Long: Loss when premium decreases
                    stop_loss_amount = total_cost_notional * (stop_loss_pct / 100)
                    stop_loss_value = total_cost_notional - stop_loss_amount
                else:
                    # Short: Loss when premium increases
                    stop_loss_amount = total_cost_notional * (stop_loss_pct / 100)
                    stop_loss_value = total_cost_notional + stop_loss_amount
            
            # Calculate target
            target_value = 0
            target_amount = 0
            
            if target_pct and target_pct > 0:
                if strategy['direction'] == 'long':
                    # Long: Profit when premium increases
                    target_amount = total_cost_notional * (target_pct / 100)
                    target_value = total_cost_notional + target_amount
                else:
                    # Short: Profit when premium decreases
                    target_amount = total_cost_notional * (target_pct / 100)
                    target_value = total_cost_notional - target_amount
            
            # ✅ Get available balance in USD/USDT format
            balance_response = await api.get_wallet_balance()
            available_balance = 0.0
            
            bot_logger.info(f"Balance response: {balance_response}")
            
            if balance_response and 'result' in balance_response:
                # Delta Exchange returns list of wallet balances
                for wallet in balance_response['result']:
                    # Try multiple asset identifiers
                    asset_symbol = wallet.get('asset_symbol', '')
                    asset_id = wallet.get('asset_id', -1)
                    
                    bot_logger.info(f"Checking wallet: asset_symbol={asset_symbol}, asset_id={asset_id}, balance={wallet.get('available_balance')}")
                    
                    # Check for USDT, USD, USDC, or asset_id == 0 (default USD)
                    if asset_symbol in ['USDT', 'USD', 'USDC'] or asset_id == 0:
                        available_balance = float(wallet.get('available_balance', 0))
                        bot_logger.info(f"✅ Found balance: ${available_balance} in {asset_symbol or 'USD'}")
                        break
            
            # ✅ Calculate margin requirement based on NOTIONAL cost
            if strategy['direction'] == 'long':
                required_margin = total_cost_notional
            else:
                # For short positions, approximate margin as 2x notional
                required_margin = total_cost_notional * 2
            
            bot_logger.info(f"Margin: available=${available_balance}, required=${required_margin}")
            
            # Check if sufficient balance
            margin_sufficient = available_balance >= required_margin
        
        # ✅ CRITICAL: Store ORIGINAL lot_size for execution (not adjusted)
        session = get_user_session(user.id)
        session['trade_preview'] = {
            'strategy_id': strategy_id,
            'api_id': str(api_data['_id']),
            'call_symbol': call_contract['symbol'],
            'put_symbol': put_contract['symbol'],
            'strike': atm_strike,
            'spot_price': spot_price,
            'call_premium': call_premium,
            'put_premium': put_premium,
            'total_premium': total_premium,
            'lot_size': lot_size,  # ✅ Original lot_size for execution
            'contract_size': call_contract_size  # Store for reference
        }
        
        direction_text = "📈 BUY" if strategy['direction'] == 'long' else "📉 SELL"
        margin_status = "✅ Sufficient" if margin_sufficient else "❌ Insufficient"
        
        preview_text = f"""<b>🎯 Trade Preview - {direction_text} Straddle</b>

<b>🔑 Active API:</b> {api_data.get('nickname', 'Unnamed')}
<b>💰 Available Balance:</b> ${available_balance:,.2f}

<b>Strategy:</b> {strategy.get('name', strategy.get('strategy_name', 'Unnamed'))}
<b>Direction:</b> {direction_text} Straddle

<b>📊 Trade Details:</b>
<b>Underlying:</b> {strategy['underlying']}
<b>Spot Price:</b> ${spot_price:,.2f}
<b>ATM Strike:</b> ${atm_strike:,.2f}

<b>Call Option:</b> {call_contract['symbol']}
<b>Call Premium:</b> ${call_premium:.2f}/BTC
<b>Contract Size:</b> {call_contract_size} BTC

<b>Put Option:</b> {put_contract['symbol']}
<b>Put Premium:</b> ${put_premium:.2f}/BTC
<b>Contract Size:</b> {put_contract_size} BTC

<b>💵 Cost Analysis:</b>
<b>Premium per BTC:</b> ${total_premium:.2f}
<b>Lot Size:</b> {lot_size} lot(s)
<b>Total Cost:</b> ${total_cost_notional:.2f}

<b>🎯 Risk Management:</b>
<b>Stop Loss:</b> {f"${stop_loss_value:.2f} (-${stop_loss_amount:.2f})" if stop_loss_value > 0 else "Not Set"}
<b>Target:</b> {f"${target_value:.2f} (+${target_amount:.2f})" if target_value > 0 else "Not Set"}

<b>📊 Margin Status:</b> {margin_status}
<b>Available:</b> ${available_balance:.2f}
<b>Required:</b> ${required_margin:.2f}

⚠️ <b>Confirm to execute this trade</b>
"""
        
        await query.edit_message_text(
            preview_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_trade_confirmation_keyboard(strategy_id)
        )

        return CONFIRMING_TRADE
    
    except Exception as e:
        bot_logger.error(f"Error in trade preview: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Error preparing trade preview:\n{str(e)}",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END

async def confirm_trade_execution(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute the trade after confirmation"""
    query = update.callback_query
    user = query.from_user
    
    session = get_user_session(user.id)
    preview = session.get('trade_preview')
    
    if not preview:
        await query.answer("Trade preview expired. Please try again.", show_alert=True)
        await query.edit_message_text(
            "❌ <b>Trade preview expired.</b>\n\nPlease try again.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END
    
    # Get strategy_id from preview
    strategy_id = preview['strategy_id']
    
    await query.answer()
    await query.edit_message_text(
        "⏳ <b>Executing trade...</b>\n\nPlease wait...",
        parse_mode=ParseMode.HTML
    )
    
    db = Database.get_database()
    strategy = await crud.get_strategy_by_id(db, strategy_id)
    
    # Get API credentials - use selected API from trade flow
    selected_api_id = context.user_data.get('selected_api_id')

    if selected_api_id:
        api_data = await crud.get_api_credential_by_id(db, ObjectId(selected_api_id))
    else:
        api_data = await crud.get_api_credential_by_id(db, strategy['api_id'])

    api_key = encryptor.decrypt(api_data['api_key_encrypted'])
    api_secret = encryptor.decrypt(api_data['api_secret_encrypted'])
    
    # ✅ Execute trade with stop-loss and target orders
    async with DeltaExchangeAPI(api_key, api_secret) as api:
        executor = StraddleExecutor(api)
    
        if strategy['direction'] == 'long':
            result = await executor.execute_long_straddle(
                call_symbol=preview['call_symbol'],
                put_symbol=preview['put_symbol'],
                lot_size=strategy['lot_size'],
                use_stop_loss_order=strategy.get('use_stop_loss_order', False),
                sl_trigger_pct=strategy.get('sl_trigger_pct'),
                sl_limit_pct=strategy.get('sl_limit_pct'),
                use_target_order=strategy.get('use_target_order', False),
                target_trigger_pct=strategy.get('target_trigger_pct')
            )
        else:
            result = await executor.execute_short_straddle(
                call_symbol=preview['call_symbol'],
                put_symbol=preview['put_symbol'],
                lot_size=strategy['lot_size'],
                stop_loss_pct=strategy['stop_loss_pct'],
                use_stop_loss_order=strategy.get('use_stop_loss_order', True),
                sl_trigger_pct=strategy.get('sl_trigger_pct'),
                sl_limit_pct=strategy.get('sl_limit_pct'),
                use_target_order=strategy.get('use_target_order', False),
                target_trigger_pct=strategy.get('target_trigger_pct')
            )
    
    if not result.get('success'):
        await query.edit_message_text(
            f"❌ <b>Trade execution failed!</b>\n\n"
            f"Error: {result.get('error', 'Unknown error')}\n\n"
            "Please check your settings and try again.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END
    
    # Save trade to database
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    actual_api_id = ObjectId(selected_api_id) if selected_api_id else strategy['api_id']

    trade_data = {
        'user_id': user_data['_id'],
        'api_id': actual_api_id,
        'strategy_id': strategy_id,
        'call_symbol': preview['call_symbol'],
        'put_symbol': preview['put_symbol'],
        'strike': preview['strike'],
        'spot_price': preview['spot_price'],
        'call_entry_price': result.get('call_price', preview['call_premium']),
        'put_entry_price': result.get('put_price', preview['put_premium']),
        'lot_size': strategy['lot_size']
    }
    
    trade_id = await crud.create_trade(db, trade_data)
    
    # Save main orders
    if result.get('call_order'):
        call_order_data = {
            'trade_id': trade_id,
            'order_id_delta': result['call_order']['result']['id'],
            'symbol': preview['call_symbol'],
            'side': 'buy' if strategy['direction'] == 'long' else 'sell',
            'order_type': 'market',
            'quantity': strategy['lot_size'],
            'price': result.get('call_price', preview['call_premium']),
            'status': 'filled'
        }
        await crud.create_order(db, call_order_data)
    
    if result.get('put_order'):
        put_order_data = {
            'trade_id': trade_id,
            'order_id_delta': result['put_order']['result']['id'],
            'symbol': preview['put_symbol'],
            'side': 'buy' if strategy['direction'] == 'long' else 'sell',
            'order_type': 'market',
            'quantity': strategy['lot_size'],
            'price': result.get('put_price', preview['put_premium']),
            'status': 'filled'
        }
        await crud.create_order(db, put_order_data)
    
    # Clear session
    clear_user_session(user.id)
    
    # ✅ Build success message with SL/Target info
    total_entry = (result.get('call_price', preview['call_premium']) + 
                   result.get('put_price', preview['put_premium']))
    total_cost = total_entry * strategy['lot_size']
    
    # Order status info
    sl_info = ""
    if strategy.get('use_stop_loss_order') and result.get('sl_orders'):
        num_sl_orders = len(result['sl_orders'])
        sl_info = f"\n🛡️ <b>Stop-Loss Orders:</b> {num_sl_orders} orders placed ✅"
        if strategy.get('sl_trigger_pct'):
            sl_info += f"\n   Trigger: {strategy['sl_trigger_pct']}% loss"
    
    target_info = ""
    if strategy.get('use_target_order') and result.get('target_orders'):
        num_target_orders = len(result['target_orders'])
        target_info = f"\n🎯 <b>Target Orders:</b> {num_target_orders} orders placed ✅"
        if strategy.get('target_trigger_pct'):
            target_info += f"\n   Target: {strategy['target_trigger_pct']}% profit"
    
    success_text = f"""
✅ <b>Trade Executed Successfully!</b>

📊 <b>Strategy:</b> {strategy['name']}
📈 <b>Direction:</b> {strategy['direction'].upper()} Straddle

<b>📋 Trade Details:</b>
🔵 <b>Call:</b> {preview['call_symbol']}
   Entry: ${result.get('call_price', preview['call_premium']):.2f}

🟠 <b>Put:</b> {preview['put_symbol']}
   Entry: ${result.get('put_price', preview['put_premium']):.2f}

📦 <b>Lot Size:</b> {strategy['lot_size']}
💰 <b>Total Premium:</b> ${total_entry:.2f}
💵 <b>Total Cost:</b> ${total_cost:.2f}{sl_info}{target_info}

📊 <b>Position Status:</b> OPEN
🆔 <b>Trade ID:</b> <code>{trade_id}</code>

View your position: /positions
"""
    
    await query.edit_message_text(
        success_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu_keyboard()
    )
    
    return ConversationHandler.END

async def cancel_trade_execution(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel trade execution and return to main menu"""
    query = update.callback_query
    await query.answer("Trade cancelled ❌")
    
    # Clear any stored data
    context.user_data.clear()
    
    # Return to main menu
    text = (
        "<b>🏠 Main Menu</b>\n\n"
        "Trade execution cancelled.\n\n"
        "What would you like to do?"
    )
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu_keyboard()
    )
    
    # End conversation
    return ConversationHandler.END

# ==================== POSITION MANAGEMENT HANDLERS ====================

async def show_positions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show open positions from ALL APIs with LIVE mark prices"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("🔄 Fetching positions from all APIs...")
    
    db = Database.get_database()
    user = query.from_user
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    
    if not user_data:
        await query.edit_message_text(
            "❌ User not found.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Get all API credentials
    apis = await crud.get_user_api_credentials(db, user_data['_id'])
    
    if not apis:
        await query.edit_message_text(
            "❌ No API credentials found.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Fetch positions from each API
    positions_text = "📈 <b>Open Positions</b>\n\n"
    total_pnl = 0
    position_count = 0
    
    for idx, api in enumerate(apis, 1):
        try:
            # Decrypt credentials
            api_key = encryptor.decrypt(api['api_key_encrypted'])
            api_secret = encryptor.decrypt(api['api_secret_encrypted'])
            
            # Get positions from Delta Exchange
            async with DeltaExchangeAPI(api_key, api_secret) as delta_api:
                positions = await delta_api.get_positions()
                
                api_nickname = api.get('nickname', 'Unnamed API')
                
                bot_logger.info(f"📊 Processing {len(positions)} positions for {api_nickname}")
                
                # Filter only positions with size != 0
                active_positions = [p for p in positions if abs(float(p.get('size', 0))) > 0]
                
                if active_positions:
                    positions_text += f"<b>📍 {api_nickname}</b>\n"
                    
                    for pos in active_positions:
                        # Get symbol from product_symbol
                        symbol = pos.get('product_symbol', 'Unknown')
                        
                        # Position details
                        size = float(pos.get('size', 0))
                        entry_price = float(pos.get('entry_price', 0))
                        
                        bot_logger.info(f"📍 Processing position: {symbol}, size={size}, entry=${entry_price}")
                        
                        # ✅ CRITICAL FIX: Fetch LIVE mark price from ticker API
                        mark_price = entry_price  # Default to entry if ticker fails
                        unrealized_pnl = 0
                        
                        if symbol != 'Unknown':
                            try:
                                bot_logger.info(f"🔍 Fetching LIVE ticker for {symbol}")
                                
                                # ✅ Fetch live ticker data
                                ticker = await delta_api.get_ticker_by_symbol(symbol)
                                
                                if ticker and isinstance(ticker, dict):
                                    # Get mark_price from ticker
                                    mark_price_str = ticker.get('mark_price')
                                    
                                    if mark_price_str:
                                        mark_price = float(mark_price_str)
                                        bot_logger.info(f"✅ Live mark price: ${mark_price}")
                                        
                                        # ✅ Calculate P&L with contract size
                                        contract_value = float(ticker.get('contract_value', 0.001))
                                        
                                        bot_logger.info(f"📐 Contract value: {contract_value} BTC")
                                        
                                        # Calculate P&L per contract
                                        if size < 0:  # SHORT position
                                            # Short: Profit when price goes down
                                            pnl_per_contract = (entry_price - mark_price) * contract_value
                                        else:  # LONG position
                                            # Long: Profit when price goes up
                                            pnl_per_contract = (mark_price - entry_price) * contract_value
                                        
                                        # Total P&L = P&L per contract * number of contracts
                                        unrealized_pnl = pnl_per_contract * abs(size)
                                        
                                        bot_logger.info(f"💰 P&L: ${unrealized_pnl:.4f} (per_contract=${pnl_per_contract:.4f}, size={abs(size)})")
                                    else:
                                        bot_logger.warning(f"⚠️ No mark_price in ticker for {symbol}")
                                else:
                                    bot_logger.warning(f"⚠️ Invalid ticker response for {symbol}: {ticker}")
                                    
                            except Exception as ticker_error:
                                bot_logger.error(f"❌ Error fetching ticker for {symbol}: {ticker_error}")
                                # Keep mark_price = entry_price as fallback
                        
                        # Determine side and PnL emoji
                        pnl_emoji = "🟢" if unrealized_pnl > 0 else "🔴" if unrealized_pnl < 0 else "⚪"
                        side = "🟢 LONG" if size > 0 else "🔴 SHORT"
                        
                        total_pnl += unrealized_pnl
                        position_count += 1
                        
                        positions_text += (
                            f"\n{side} <b>{symbol}</b>\n"
                            f"   Size: {abs(size):.0f}\n"
                            f"   Entry: ${entry_price:.2f}\n"
                            f"   Mark: ${mark_price:.2f}\n"
                            f"   {pnl_emoji} P&L: <b>${unrealized_pnl:,.2f}</b>\n"
                        )
                    
                    positions_text += "\n"
            
        except Exception as e:
            bot_logger.error(f"Error fetching positions for {api.get('nickname')}: {e}", exc_info=True)
            positions_text += f"<b>{api.get('nickname', 'Unnamed API')}</b>\n❌ Error: {str(e)[:50]}\n\n"
    
    if position_count == 0:
        positions_text = "📈 <b>Open Positions</b>\n\nYou have no open positions at the moment."
    else:
        # Add summary
        total_emoji = "🟢" if total_pnl > 0 else "🔴" if total_pnl < 0 else "⚪"
        positions_text += (
            f"<b>📊 SUMMARY</b>\n"
            f"Total Positions: {position_count}\n"
            f"{total_emoji} Total Unrealized P&L: <b>${total_pnl:,.2f}</b>"
        )
    
    await query.edit_message_text(
        positions_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu_keyboard()
    )

async def view_position_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View detailed position information"""
    query = update.callback_query
    trade_id = query.data.split('_')[-1]
    
    db = Database.get_database()
    trade = await crud.get_trade_by_id(db, trade_id)
    
    if not trade:
        await query.answer("Position not found", show_alert=True)
        return
    
    # Get strategy
    strategy = await crud.get_strategy_by_id(db, trade['strategy_id'])
    
    # Get API credentials
    api_data = await crud.get_api_credential_by_id(db, trade['api_id'])
    api_key = encryptor.decrypt(api_data['api_key_encrypted'])
    api_secret = encryptor.decrypt(api_data['api_secret_encrypted'])
    
    # Fetch live data
    async with DeltaExchangeAPI(api_key, api_secret) as api:
        call_ticker = await api.get_tickers(trade['call_symbol'])
        put_ticker = await api.get_tickers(trade['put_symbol'])
        
        call_current = float(call_ticker['result'].get('close', 0)) if 'result' in call_ticker else 0
        put_current = float(put_ticker['result'].get('close', 0)) if 'result' in put_ticker else 0
        
        # Calculate P&L
        monitor = PositionMonitor(api)
        is_long = strategy['direction'] == 'long'
        current_pnl = await monitor.calculate_straddle_pnl(
            trade['call_entry_price'],
            trade['put_entry_price'],
            call_current,
            put_current,
            trade['lot_size'],
            is_long
        )
    
    entry_premium = trade['call_entry_price'] + trade['put_entry_price']
    current_premium = call_current + put_current
    premium_change = ((current_premium - entry_premium) / entry_premium) * 100
    
    pnl_emoji = "🟢" if current_pnl >= 0 else "🔴"
    direction_text = "📈 Long Straddle" if is_long else "📉 Short Straddle"
    
    # Calculate SL and Target levels
    sl_level = entry_premium * (1 - strategy['stop_loss_pct'] / 100)
    target_level = entry_premium * (1 + strategy.get('target_pct', 0) / 100) if strategy.get('target_pct') else None
    
    details_text = f"""
<b>📊 Position Details</b>

<b>Strategy:</b> {strategy['name']}
<b>Direction:</b> {direction_text}
<b>Underlying:</b> {strategy['underlying']}
<b>Strike:</b> {format_currency(trade['strike'])}

<b>📈 Call Option:</b>
<b>Symbol:</b> <code>{trade['call_symbol']}</code>
<b>Entry:</b> {format_currency(trade['call_entry_price'])}
<b>Current:</b> {format_currency(call_current)}
<b>Change:</b> {format_percentage((call_current - trade['call_entry_price']) / trade['call_entry_price'] * 100)}

<b>📉 Put Option:</b>
<b>Symbol:</b> <code>{trade['put_symbol']}</code>
<b>Entry:</b> {format_currency(trade['put_entry_price'])}
<b>Current:</b> {format_currency(put_current)}
<b>Change:</b> {format_percentage((put_current - trade['put_entry_price']) / trade['put_entry_price'] * 100)}

<b>💰 P&L Summary:</b>
<b>Entry Premium:</b> {format_currency(entry_premium)}
<b>Current Premium:</b> {format_currency(current_premium)}
<b>Premium Change:</b> {format_percentage(premium_change)}

{pnl_emoji} <b>Net P&L:</b> {format_currency(current_pnl)}

<b>🎯 Risk Levels:</b>
<b>Stop Loss:</b> {format_currency(sl_level)}
{f"<b>Target:</b> {format_currency(target_level)}" if target_level else ""}

<b>📅 Entry Time:</b> {trade['entry_time'].strftime('%Y-%m-%d %H:%M UTC')}
"""
    
    await query.answer()
    await query.edit_message_text(
        details_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_position_action_keyboard(trade_id)
    )


async def close_position_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show confirmation for closing position"""
    query = update.callback_query
    trade_id = query.data.split('_')[-1]
    
    await query.answer()
    await query.edit_message_text(
        "⚠️ <b>Close Position</b>\n\n"
        "Are you sure you want to close this position?\n\n"
        "This will execute market orders to exit both call and put options.",
        parse_mode=ParseMode.HTML,
        reply_markup=get_close_position_confirmation_keyboard(trade_id)
    )


async def close_position_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute position close"""
    query = update.callback_query
    trade_id = query.data.split('_')[-1]
    
    await query.answer()
    await query.edit_message_text(
        "⏳ <b>Closing position...</b>\n\nPlease wait...",
        parse_mode=ParseMode.HTML
    )
    
    db = Database.get_database()
    trade = await crud.get_trade_by_id(db, trade_id)
    
    if not trade:
        await query.edit_message_text(
            "❌ Position not found.",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Get strategy
    strategy = await crud.get_strategy_by_id(db, trade['strategy_id'])
    
    # Get API credentials
    api_data = await crud.get_api_credential_by_id(db, trade['api_id'])
    api_key = encryptor.decrypt(api_data['api_key_encrypted'])
    api_secret = encryptor.decrypt(api_data['api_secret_encrypted'])
    
    # Close position
    async with DeltaExchangeAPI(api_key, api_secret) as api:
        executor = StraddleExecutor(api)
        is_long = strategy['direction'] == 'long'
        
        result = await executor.close_straddle_position(
            trade['call_symbol'],
            trade['put_symbol'],
            trade['lot_size'],
            is_long
        )
    
    if not result.get('success'):
        await query.edit_message_text(
            f"❌ <b>Failed to close position!</b>\n\n"
            f"Error: {result.get('error', 'Unknown error')}\n\n"
            "Please try again or close manually from Delta Exchange.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Get exit prices
    call_exit = float(result['call_order'].get('average_fill_price', 0))
    put_exit = float(result['put_order'].get('average_fill_price', 0))
    
    # Calculate final P&L
    async with DeltaExchangeAPI(api_key, api_secret) as api:
        monitor = PositionMonitor(api)
        final_pnl = await monitor.calculate_straddle_pnl(
            trade['call_entry_price'],
            trade['put_entry_price'],
            call_exit,
            put_exit,
            trade['lot_size'],
            is_long
        )
    
    # Update trade in database
    await crud.close_trade(db, trade_id, call_exit, put_exit, final_pnl)
    
    pnl_emoji = "🟢" if final_pnl >= 0 else "🔴"
    
    close_text = f"""
✅ <b>Position Closed Successfully!</b>

<b>Call Exit:</b> {format_currency(call_exit)}
<b>Put Exit:</b> {format_currency(put_exit)}

{pnl_emoji} <b>Final P&L:</b> {format_currency(final_pnl)}

<b>Entry Premium:</b> {format_currency(trade['call_entry_price'] + trade['put_entry_price'])}
<b>Exit Premium:</b> {format_currency(call_exit + put_exit)}

<b>Holding Period:</b> {(trade['exit_time'] - trade['entry_time']).total_seconds() / 3600:.1f} hours

View trade history: /history
"""
    
    await query.edit_message_text(
        close_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu_keyboard()
    )


# ==================== HISTORY HANDLER ====================

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show compact trade history grouped by API and Date with overall API summaries"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("🔄 Loading trade history...")
    
    db = Database.get_database()
    user = query.from_user
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    
    if not user_data:
        await query.edit_message_text(
            "❌ User not found.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    try:
        from datetime import datetime
        from collections import defaultdict
        
        # Get all API credentials
        apis = await crud.get_user_api_credentials(db, user_data['_id'])
        
        if not apis:
            await query.edit_message_text(
                "❌ No API credentials found.",
                parse_mode=ParseMode.HTML,
                reply_markup=get_main_menu_keyboard()
            )
            return
        
        # ✅ Collect trades grouped by API
        trades_by_api = {}
        
        for api in apis:
            try:
                # Decrypt credentials
                api_key = encryptor.decrypt(api['api_key_encrypted'])
                api_secret = encryptor.decrypt(api['api_secret_encrypted'])
                
                api_nickname = api.get('nickname', 'Unnamed API')
                
                # Get order history from Delta Exchange
                async with DeltaExchangeAPI(api_key, api_secret) as delta_api:
                    # ✅ Fetch ALL order history (increased limit)
                    history_response = await delta_api.get_order_history(limit=100)
                    
                    if history_response and 'result' in history_response:
                        orders = history_response['result']
                        
                        # Filter for closed orders with fills
                        closed_orders = [
                            o for o in orders 
                            if o.get('state') == 'closed' and o.get('average_fill_price')
                        ]
                        
                        api_trades = []
                        
                        for order in closed_orders:
                            symbol = order.get('product_symbol', 'Unknown')
                            side = order.get('side', 'buy')
                            size = float(order.get('size', 0))
                            unfilled = float(order.get('unfilled_size', 0))
                            filled_size = size - unfilled
                            
                            avg_price = float(order.get('average_fill_price', 0))
                            commission = float(order.get('paid_commission', 0))
                            
                            # Get P&L from meta_data
                            meta_data = order.get('meta_data', {})
                            pnl = float(meta_data.get('pnl', 0))
                            
                            # Get order creation time
                            created_at = order.get('created_at', '')
                            if created_at:
                                try:
                                    order_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                except:
                                    order_time = None
                            else:
                                order_time = None
                            
                            api_trades.append({
                                'symbol': symbol,
                                'side': side,
                                'size': filled_size,
                                'price': avg_price,
                                'pnl': pnl,
                                'commission': commission,
                                'time': order_time
                            })
                        
                        if api_trades:
                            trades_by_api[api_nickname] = api_trades
                        
            except Exception as api_error:
                bot_logger.error(f"Error fetching history for {api.get('nickname')}: {api_error}")
        
        if not trades_by_api:
            await query.edit_message_text(
                "📜 <b>Trade History</b>\n\nNo closed trades found.",
                parse_mode=ParseMode.HTML,
                reply_markup=get_main_menu_keyboard()
            )
            return
        
        # ✅ Build compact history text grouped by API and Date
        history_text = "📜 <b>Trade History</b>\n\n"
        
        overall_trades = 0
        overall_pnl = 0.0
        overall_commission = 0.0
        
        # Loop through each API
        for api_nickname, api_trades in trades_by_api.items():
            history_text += f"<b>🔑 {api_nickname}</b>\n"
            
            # ✅ Calculate OVERALL API stats (ALL trades)
            api_all_trades_count = len(api_trades)
            api_all_pnl = sum(t['pnl'] for t in api_trades)
            api_all_commission = sum(t['commission'] for t in api_trades)
            api_all_net = api_all_pnl - api_all_commission
            
            # Group trades by date for this API
            trades_by_date = defaultdict(list)
            
            for trade in api_trades:
                if trade['time']:
                    date_key = trade['time'].strftime('%d %b')
                else:
                    date_key = 'Unknown'
                trades_by_date[date_key].append(trade)
            
            # Sort dates (newest first)
            sorted_dates = sorted(
                trades_by_date.keys(),
                key=lambda d: datetime.strptime(d + ' 2025', '%d %b %Y') if d != 'Unknown' else datetime.min,
                reverse=True
            )
            
            # Show last 10 days per API (for recent activity view)
            for date_key in sorted_dates[:10]:
                date_trades = trades_by_date[date_key]
                
                # Calculate daily totals
                daily_pnl = sum(t['pnl'] for t in date_trades)
                daily_commission = sum(t['commission'] for t in date_trades)
                trade_count = len(date_trades)
                
                pnl_emoji = "🟢" if daily_pnl > 0 else "🔴" if daily_pnl < 0 else "⚪"
                
                history_text += (
                    f"   📅 {date_key}: {pnl_emoji} {trade_count} trades | "
                    f"P&L ${daily_pnl:.2f} | Comm ${daily_commission:.2f}\n"
                )
            
            # ✅ Show if there are more days not displayed
            if len(sorted_dates) > 10:
                history_text += f"   ... +{len(sorted_dates) - 10} more days\n"
            
            # ✅ API OVERALL Summary (ALL trades on this API)
            api_net_emoji = "🟢" if api_all_net > 0 else "🔴" if api_all_net < 0 else "⚪"
            history_text += (
                f"   {api_net_emoji} <b>API OVERALL:</b> {api_all_trades_count} trades | "
                f"Gross ${api_all_pnl:.2f} | Comm ${api_all_commission:.2f} | "
                f"Net <b>${api_all_net:.2f}</b>\n\n"
            )
            
            overall_trades += api_all_trades_count
            overall_pnl += api_all_pnl
            overall_commission += api_all_commission
        
        # ✅ GLOBAL Overall Summary (all APIs combined)
        net_profit = overall_pnl - overall_commission
        net_emoji = "🟢" if net_profit > 0 else "🔴" if net_profit < 0 else "⚪"
        
        history_text += (
            f"<b>📊 GLOBAL SUMMARY (All APIs)</b>\n"
            f"Total Orders: {overall_trades}\n"
            f"Gross P&L: ${overall_pnl:.2f}\n"
            f"Total Commission: ${overall_commission:.2f}\n"
            f"{net_emoji} Net Profit: <b>${net_profit:.2f}</b>"
        )
        
        await query.edit_message_text(
            history_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )
    
    except Exception as e:
        bot_logger.error(f"Error in show_history: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ Error loading trade history:\n{str(e)[:100]}",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )

# ==================== CONVERSATION CANCEL HANDLER ====================

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel ongoing conversation"""
    user = update.effective_user
    clear_user_session(user.id)
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "❌ Operation cancelled.",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ Operation cancelled.",
            reply_markup=get_main_menu_keyboard()
        )
    
    return ConversationHandler.END


# ==================== ERROR HANDLER ====================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    bot_logger.error(f"Update {update} caused error {context.error}")
    
    error_message = "❌ An error occurred. Please try again or contact support."
    
    try:
        if update.effective_message:
            await update.effective_message.reply_text(
                error_message,
                reply_markup=get_main_menu_keyboard()
            )
        elif update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                error_message,
                reply_markup=get_main_menu_keyboard()
            )
    except Exception as e:
        bot_logger.error(f"Error in error handler: {e}")
    
