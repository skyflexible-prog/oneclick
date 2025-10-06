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
    
    return ConversationHandler.END  # Will be handled by callback


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
    
    await update.message.reply_text(
        f"✅ Stop Loss: <b>{sl_pct}%</b>\n\n"
        "Please enter the <b>target percentage</b> (optional, send 0 to skip):",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard()
    )
    
    return AWAITING_TARGET


async def receive_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive target percentage"""
    user = update.effective_user
    session = get_user_session(user.id)
    
    is_valid, message, target_pct = validator.validate_percentage(update.message.text, allow_zero=True)
    if not is_valid:
        await update.message.reply_text(
            f"❌ {message}\n\nPlease enter a valid target percentage (or 0 to skip):",
            reply_markup=get_cancel_keyboard()
        )
        return AWAITING_TARGET
    
    session['strategy_data']['target_pct'] = target_pct if target_pct > 0 else None
    
    await update.message.reply_text(
        f"✅ Target: <b>{target_pct}%</b>\n\n"
        "Please enter the <b>maximum capital allocation</b> in INR:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_cancel_keyboard()
    )
    
    return AWAITING_MAX_CAPITAL


async def receive_max_capital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive max capital"""
    user = update.effective_user
    session = get_user_session(user.id)
    
    is_valid, message, capital = validator.validate_capital(update.message.text)
    if not is_valid:
        await update.message.reply_text(
            f"❌ {message}\n\nPlease enter a valid capital amount:",
            reply_markup=get_cancel_keyboard()
        )
        return AWAITING_MAX_CAPITAL
    
    session['strategy_data']['max_capital'] = capital
    
    await update.message.reply_text(
        f"✅ Max Capital: <b>{format_currency(capital)}</b>\n\n"
        "Please enter the <b>strike offset</b> from ATM (0 for ATM, +1 for OTM, -1 for ITM):",
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


async def list_strategies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all user strategies"""
    user = update.effective_user
    db = Database.get_database()
    
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    strategies = await crud.get_user_strategies(db, user_data['_id'])
    
    if not strategies:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "🎯 <b>Trading Strategies</b>\n\n"
            "You haven't created any strategies yet.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_strategy_management_keyboard()
        )
        return
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "🎯 <b>Your Trading Strategies</b>\n\n"
        "Select a strategy to view details:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_strategy_list_keyboard(strategies)
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
    """Show trade execution menu"""
    user = update.effective_user
    db = Database.get_database()
    
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    strategies = await crud.get_user_strategies(db, user_data['_id'])
    
    if not strategies:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "📊 <b>Execute Trade</b>\n\n"
            "You need to create a strategy first before trading.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_strategy_management_keyboard()
        )
        return
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "📊 <b>Execute Trade</b>\n\n"
        "Select a strategy to execute:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_trade_execution_keyboard(strategies)
    )


async def execute_trade_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show trade preview and confirmation"""
    query = update.callback_query
    strategy_id = query.data.split('_')[-1]
    user = query.from_user
    
    db = Database.get_database()
    strategy = await crud.get_strategy_by_id(db, strategy_id)
    
    if not strategy:
        await query.answer("Strategy not found", show_alert=True)
        return
    
    # Get API credentials
    api_data = await crud.get_api_credential_by_id(db, strategy['api_id'])
    api_key = encryptor.decrypt(api_data['api_key_encrypted'])
    api_secret = encryptor.decrypt(api_data['api_secret_encrypted'])
    
    await query.answer()
    await query.edit_message_text(
        "🔄 <b>Calculating trade details...</b>",
        parse_mode=ParseMode.HTML
    )
    
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
            return
        
        atm_strike = await calculator.get_atm_strike(strategy['underlying'], strategy['strike_offset'])
        if not atm_strike:
            await query.edit_message_text(
                "❌ Failed to calculate ATM strike. Please try again.",
                reply_markup=get_main_menu_keyboard()
            )
            return
        
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
            return
        
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
            return
        
        total_premium = call_premium + put_premium
        total_cost = total_premium * strategy['lot_size']
        
        # Calculate SL and Target
        targets = await calculator.calculate_straddle_targets(
            total_premium,
            strategy['stop_loss_pct'],
            strategy.get('target_pct')
        )
        
        # Check margin
        margin_check = await api.check_margin_requirements(call_contract['symbol'], strategy['lot_size'])
    
    # Store trade preview data in session
    session = get_user_session(user.id)
    session['trade_preview'] = {
        'strategy_id': strategy_id,
        'call_symbol': call_contract['symbol'],
        'put_symbol': put_contract['symbol'],
        'strike': atm_strike,
        'spot_price': spot_price,
        'call_premium': call_premium,
        'put_premium': put_premium,
        'total_premium': total_premium,
        'total_cost': total_cost,
        'targets': targets
    }
    
    direction_text = "📈 BUY" if strategy['direction'] == 'long' else "📉 SELL"
    margin_status = "✅ Sufficient" if margin_check.get('sufficient') else "❌ Insufficient"
    
    preview_text = f"""
<b>📊 Trade Preview</b>

<b>Strategy:</b> {strategy['name']}
<b>Direction:</b> {direction_text} Straddle

<b>🎯 Trade Details:</b>
<b>Underlying:</b> {strategy['underlying']}
<b>Spot Price:</b> {format_currency(spot_price)}
<b>ATM Strike:</b> {format_currency(atm_strike)}

<b>Call Option:</b> {call_contract['symbol']}
<b>Call Premium:</b> {format_currency(call_premium)}

<b>Put Option:</b> {put_contract['symbol']}
<b>Put Premium:</b> {format_currency(put_premium)}

<b>💰 Cost Analysis:</b>
<b>Total Premium:</b> {format_currency(total_premium)}
<b>Lot Size:</b> {strategy['lot_size']}
<b>Total Cost:</b> {format_currency(total_cost)}

<b>🎯 Risk Management:</b>
<b>Stop Loss:</b> {format_currency(targets['stop_loss'])} (-{format_currency(targets['stop_loss_amount'])})
<b>Target:</b> {format_currency(targets.get('target', 0)) if targets.get('target') else 'Not Set'}

<b>💳 Margin Status:</b> {margin_status}
<b>Available:</b> {format_currency(margin_check.get('available', 0))}
<b>Required:</b> {format_currency(margin_check.get('required', 0))}

⚠️ <b>Confirm to execute this trade</b>
"""
    
    await query.edit_message_text(
        preview_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_trade_confirmation_keyboard(strategy_id)
    )


async def confirm_trade_execution(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute the trade after confirmation"""
    query = update.callback_query
    strategy_id = query.data.split('_')[-1]
    user = query.from_user
    
    session = get_user_session(user.id)
    preview = session.get('trade_preview')
    
    if not preview or preview['strategy_id'] != strategy_id:
        await query.answer("Trade preview expired. Please try again.", show_alert=True)
        return
    
    await query.answer()
    await query.edit_message_text(
        "⏳ <b>Executing trade...</b>\n\nPlease wait...",
        parse_mode=ParseMode.HTML
    )
    
    db = Database.get_database()
    strategy = await crud.get_strategy_by_id(db, strategy_id)
    
    # Get API credentials
    api_data = await crud.get_api_credential_by_id(db, strategy['api_id'])
    api_key = encryptor.decrypt(api_data['api_key_encrypted'])
    api_secret = encryptor.decrypt(api_data['api_secret_encrypted'])
    
    # Execute trade
    async with DeltaExchangeAPI(api_key, api_secret) as api:
        executor = StraddleExecutor(api)
        
        if strategy['direction'] == 'long':
            result = await executor.execute_long_straddle(
                preview['call_symbol'],
                preview['put_symbol'],
                strategy['lot_size']
            )
        else:
            result = await executor.execute_short_straddle(
                preview['call_symbol'],
                preview['put_symbol'],
                strategy['lot_size']
            )
    
    if not result.get('success'):
        await query.edit_message_text(
            f"❌ <b>Trade execution failed!</b>\n\n"
            f"Error: {result.get('error', 'Unknown error')}\n\n"
            "Please check your settings and try again.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    # Save trade to database
    user_data = await crud.get_user_by_telegram_id(db, user.id)
    
    trade_data = {
        'user_id': user_data['_id'],
        'api_id': strategy['api_id'],
        'strategy_id': strategy_id,
        'call_symbol': preview['call_symbol'],
        'put_symbol': preview['put_symbol'],
        'strike': preview['strike'],
        'spot_price': preview['spot_price'],
        'call_entry_price': preview['call_premium'],
        'put_entry_price': preview['put_premium'],
        'lot_size': strategy['lot_size']
    }
    
    trade_id = await crud.create_trade(db, trade_data)
    
    # Save orders
    call_order_data = {
        'trade_id': trade_id,
        'order_id_delta': result['call_order']['id'],
        'symbol': preview['call_symbol'],
        'side': 'buy' if strategy['direction'] == 'long' else 'sell',
        'order_type': 'market',
        'quantity': strategy['lot_size'],
        'price': preview['call_premium'],
        'status': 'filled'
    }
    await crud.create_order(db, call_order_data)
    
    put_order_data = {
        'trade_id': trade_id,
        'order_id_delta': result['put_order']['id'],
        'symbol': preview['put_symbol'],
        'side': 'buy' if strategy['direction'] == 'long' else 'sell',
        'order_type': 'market',
        'quantity': strategy['lot_size'],
        'price': preview['put_premium'],
        'status': 'filled'
    }
    await crud.create_order(db, put_order_data)
    
    success_text = f"""
✅ <b>Trade Executed Successfully!</b>

<b>Trade ID:</b> <code>{trade_id}</code>

<b>Call Order:</b> {result['call_order']['id']}
<b>Put Order:</b> {result['put_order']['id']}

<b>Entry Premium:</b> {format_currency(preview['total_premium'])}
<b>Total Cost:</b> {format_currency(preview['total_cost'])}

<b>Stop Loss:</b> {format_currency(preview['targets']['stop_loss'])}
{f"<b>Target:</b> {format_currency(preview['targets'].get('target', 0))}" if preview['targets'].get('target') else ""}

Your position is now being monitored. You'll receive alerts when SL/Target is hit.

View positions: /positions
"""
    
    await query.edit_message_text(
        success_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu_keyboard()
    )
    
    # Start position monitoring
    # This will be implemented in the main.py file
    clear_user_session(user.id)


# Continue in next part...
