from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.crud import UserCRUD, APICredentialCRUD, StrategyCRUD, TradeCRUD
from trading.delta_api import DeltaExchangeAPI
from trading.straddle_logic import StraddleStrategy
from trading.strangle_logic import StrangleStrategy
from trading.order_manager import OrderManager
from trading.position_monitor import PositionMonitor
from bot.keyboards import *
from bot.validators import *
from utils.helpers import Encryptor, format_currency, calculate_pnl
from config.settings import ADMIN_TELEGRAM_IDS
import logging

logger = logging.getLogger(__name__)

# Initialize CRUD operations
user_crud = UserCRUD()
api_crud = APICredentialCRUD()
strategy_crud = StrategyCRUD()
trade_crud = TradeCRUD()
encryptor = Encryptor()

# User state management
user_states = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    
    # Create or get user
    db_user = user_crud.get_or_create_user(user.id, user.username or '', user.first_name or '')
    
    welcome_text = f"""
👋 Welcome to **Straddle & Strangle Trading Bot**!

🎯 Trade ATM Straddles and OTM Strangles on Delta Exchange India with single-click execution.

**Features:**
✅ Multi-API Support
✅ Preset Strategy Configurations
✅ Real-time Position Monitoring
✅ Automated Stop Loss & Targets
✅ Trade Analytics & History

Use the menu below to get started 👇
    """
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
📚 **Command Reference**

**API Management:**
/addapi - Add new Delta API credentials
/listapis - View all registered APIs
/selectapi - Choose active API

**Strategy Management:**
/createstrategy - Configure new strategy preset
/liststrategy - View all strategies
/editstrategy - Modify existing strategy

**Trading:**
/trade - Execute preset strategies
/positions - View active positions
/closeposition - Close positions
/balance - Check wallet balance

**Analytics:**
/history - Trade history with P&L
/analytics - Performance statistics
/comparestrategies - Compare straddle vs strangle

**Other:**
/start - Show main menu
/help - This help message

💡 Tip: Use inline buttons for easier navigation!
    """
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def add_api_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start API credential addition process"""
    user_id = update.effective_user.id
    user_states[user_id] = {'action': 'add_api', 'step': 'nickname'}
    
    await update.message.reply_text(
        "🔑 **Add New API Credentials**\n\n"
        "Step 1/3: Enter a nickname for this API\n"
        "(e.g., 'Main Account', 'Trading Account 1')",
        parse_mode='Markdown'
    )

async def create_strategy_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start strategy creation process"""
    user = update.effective_user
    db_user = user_crud.get_user_by_telegram_id(user.id)
    
    # Check if user has active API
    active_api = api_crud.get_active_credential(str(db_user['_id']))
    if not active_api:
        await update.message.reply_text(
            "⚠️ Please add and activate an API credential first using /addapi",
            parse_mode='Markdown'
        )
        return
    
    await update.message.reply_text(
        "📋 **Create New Strategy**\n\n"
        "Select strategy type:",
        reply_markup=get_strategy_type_keyboard(),
        parse_mode='Markdown'
    )

async def list_strategies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all user strategies"""
    user = update.effective_user
    db_user = user_crud.get_user_by_telegram_id(user.id)
    
    strategies = strategy_crud.get_user_strategies(str(db_user['_id']))
    
    if not strategies:
        await update.message.reply_text(
            "📋 You don't have any strategies yet.\n\n"
            "Create your first strategy with /createstrategy",
            parse_mode='Markdown'
        )
        return
    
    await update.message.reply_text(
        f"📋 **Your Strategies** ({len(strategies)} total)\n\n"
        "Select a strategy to view details:",
        reply_markup=get_strategies_list_keyboard(strategies),
        parse_mode='Markdown'
    )

async def list_apis_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all user API credentials"""
    user = update.effective_user
    db_user = user_crud.get_user_by_telegram_id(user.id)
    
    apis = api_crud.get_user_credentials(str(db_user['_id']))
    
    if not apis:
        await update.message.reply_text(
            "🔑 You don't have any API credentials yet.\n\n"
            "Add your first API with /addapi",
            parse_mode='Markdown'
        )
        return
    
    await update.message.reply_text(
        f"🔑 **Your API Credentials** ({len(apis)} total)\n\n"
        "✅ = Active | ⭕ = Inactive\n\n"
        "Select an API to manage:",
        reply_markup=get_api_list_keyboard(apis),
        parse_mode='Markdown'
    )

async def check_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check wallet balance for active API"""
    user = update.effective_user
    db_user = user_crud.get_user_by_telegram_id(user.id)
    
    active_api = api_crud.get_active_credential(str(db_user['_id']))
    if not active_api:
        await update.message.reply_text(
            "⚠️ No active API found. Please select an API first.",
            parse_mode='Markdown'
        )
        return
    
    # Decrypt credentials
    api_key = encryptor.decrypt(active_api['api_key_encrypted'])
    api_secret = encryptor.decrypt(active_api['api_secret_encrypted'])
    
    # Get balance
    delta_api = DeltaExchangeAPI(api_key, api_secret)
    balance_data = delta_api.get_wallet_balance()
    
    if not balance_data:
        await update.message.reply_text(
            "❌ Failed to fetch balance. Please check your API credentials.",
            parse_mode='Markdown'
        )
        return
    
    available = float(balance_data[0].get('available_balance', 0))
    total = float(balance_data[0].get('balance', 0))
    
    balance_text = f"""
💰 **Wallet Balance**

API: {active_api['nickname']}
Available: {format_currency(available)}
Total: {format_currency(total)}
    """
    
    await update.message.reply_text(balance_text, parse_mode='Markdown')

async def show_positions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show active positions"""
    user = update.effective_user
    db_user = user_crud.get_user_by_telegram_id(user.id)
    
    active_api = api_crud.get_active_credential(str(db_user['_id']))
    if not active_api:
        await update.message.reply_text(
            "⚠️ No active API found.",
            parse_mode='Markdown'
        )
        return
    
    # Decrypt and get positions
    api_key = encryptor.decrypt(active_api['api_key_encrypted'])
    api_secret = encryptor.decrypt(active_api['api_secret_encrypted'])
    
    delta_api = DeltaExchangeAPI(api_key, api_secret)
    monitor = PositionMonitor(delta_api)
    positions = monitor.get_active_positions_details()
    
    if not positions:
        await update.message.reply_text(
            "📊 No active positions found.",
            parse_mode='Markdown'
        )
        return
    
    positions_text = "💼 **Active Positions**\n\n"
    total_pnl = 0
    
    for pos in positions:
        pnl = pos['unrealized_pnl']
        total_pnl += pnl
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        
        positions_text += f"{pnl_emoji} {pos['symbol']}\n"
        positions_text += f"   Entry: {format_currency(pos['entry_price'])}\n"
        positions_text += f"   Current: {format_currency(pos['current_price'])}\n"
        positions_text += f"   P&L: {format_currency(pnl)} ({pos['pnl_percentage']:.2f}%)\n\n"
    
    positions_text += f"**Total P&L: {format_currency(total_pnl)}**"
    
    # Store positions in context for callbacks
    context.user_data['positions'] = positions
    
    await update.message.reply_text(
        positions_text,
        reply_markup=get_positions_keyboard(positions),
        parse_mode='Markdown'
    )

async def trade_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show trade history"""
    user = update.effective_user
    db_user = user_crud.get_user_by_telegram_id(user.id)
    
    trades = trade_crud.get_trade_history(str(db_user['_id']), limit=10)
    
    if not trades:
        await update.message.reply_text(
            "📈 No trade history found.",
            parse_mode='Markdown'
        )
        return
    
    history_text = "📈 **Trade History** (Last 10)\n\n"
    total_pnl = 0
    
    for trade in trades:
        entry_time = trade['entry_time'].strftime('%Y-%m-%d %H:%M')
        strategy_type = trade['strategy_type'].upper()
        pnl = trade.get('pnl', 0)
        total_pnl += pnl
        status = trade['status'].upper()
        
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        
        history_text += f"{pnl_emoji} {strategy_type} - {status}\n"
        history_text += f"   Entry: {entry_time}\n"
        history_text += f"   P&L: {format_currency(pnl)}\n\n"
    
    history_text += f"**Total P&L: {format_currency(total_pnl)}**"
    
    await update.message.reply_text(history_text, parse_mode='Markdown')

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input based on user state"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    action = state.get('action')
    
    if action == 'add_api':
        await handle_add_api_input(update, context, state, text)
    elif action == 'create_strategy':
        await handle_create_strategy_input(update, context, state, text)

async def handle_add_api_input(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                              state: dict, text: str):
    """Handle API addition input"""
    user_id = update.effective_user.id
    step = state.get('step')
    
    if step == 'nickname':
        is_valid, msg = validate_strategy_name(text)
        if not is_valid:
            await update.message.reply_text(f"❌ {msg}\n\nPlease try again:")
            return
        
        state['nickname'] = text
        state['step'] = 'api_key'
        await update.message.reply_text(
            "Step 2/3: Enter your Delta Exchange API Key\n\n"
            "⚠️ This message will be deleted for security."
        )
    
    elif step == 'api_key':
        state['api_key'] = text
        state['step'] = 'api_secret'
        
        # Delete the message containing API key
        try:
            await update.message.delete()
        except:
            pass
        
        await context.bot.send_message(
            chat_id=user_id,
            text="Step 3/3: Enter your Delta Exchange API Secret\n\n"
                 "⚠️ This message will be deleted for security."
        )
    
    elif step == 'api_secret':
        state['api_secret'] = text
        
        # Delete the message containing API secret
        try:
            await update.message.delete()
        except:
            pass
        
        # Validate credentials
        is_valid, msg = validate_api_credentials(state['api_key'], state['api_secret'])
        if not is_valid:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ {msg}\n\nPlease start over with /addapi"
            )
            del user_states[user_id]
            return
        
        # Encrypt and save
        user = user_crud.get_user_by_telegram_id(user_id)
        api_key_encrypted = encryptor.encrypt(state['api_key'])
        api_secret_encrypted = encryptor.encrypt(state['api_secret'])
        
        api_id = api_crud.create_credential(
            str(user['_id']),
            state['nickname'],
            api_key_encrypted,
            api_secret_encrypted
        )
        
        if api_id:
            # Set as active if it's the first API
            apis = api_crud.get_user_credentials(str(user['_id']))
            if len(apis) == 1:
                api_crud.set_active_credential(str(user['_id']), api_id)
            
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ API '{state['nickname']}' added successfully!\n\n"
                     f"Use /listapis to manage your APIs.",
                parse_mode='Markdown'
            )
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Failed to save API credentials. Please try again."
            )
        
        del user_states[user_id]

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Route to appropriate handler
    if data.startswith('menu_'):
        await handle_menu_callback(query, context, data)
    elif data.startswith('type_'):
        await handle_strategy_type_callback(query, context, data)
    elif data.startswith('dir_'):
        await handle_direction_callback(query, context, data)
    elif data.startswith('exp_'):
        await handle_expiry_callback(query, context, data)
    elif data.startswith('offset_'):
        await handle_offset_callback(query, context, data)
    elif data.startswith('strategy_'):
        await handle_strategy_callback(query, context, data)
    elif data.startswith('execute_'):
        await handle_execute_callback(query, context, data)
    elif data.startswith('confirm_'):
        await handle_confirm_callback(query, context, data)
    elif data.startswith('api_'):
        await handle_api_callback(query, context, data)
    elif data.startswith('position_'):
        await handle_position_callback(query, context, data)
    elif data.startswith('close_'):
        await handle_close_position_callback(query, context, data)
    elif data.startswith('back_'):
        await handle_back_callback(query, context, data)

async def handle_menu_callback(query, context, data):
    """Handle main menu callbacks"""
    action = data.replace('menu_', '')
    
    if action == 'trade':
        await query.edit_message_text(
            "🎯 **Select Strategy Type**",
            reply_markup=get_strategy_type_keyboard(),
            parse_mode='Markdown'
        )
    elif action == 'strategies':
        user = query.from_user
        db_user = user_crud.get_user_by_telegram_id(user.id)
        strategies = strategy_crud.get_user_strategies(str(db_user['_id']))
        
        if not strategies:
            await query.edit_message_text(
                "📋 You don't have any strategies yet.\n\n"
                "Create your first strategy with /createstrategy",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                f"📋 **Your Strategies** ({len(strategies)} total)\n\n"
                "Select a strategy:",
                reply_markup=get_strategies_list_keyboard(strategies),
                parse_mode='Markdown'
            )
    elif action == 'apis':
        user = query.from_user
        db_user = user_crud.get_user_by_telegram_id(user.id)
        apis = api_crud.get_user_credentials(str(db_user['_id']))
        
        if not apis:
            await query.edit_message_text(
                "🔑 You don't have any API credentials yet.\n\n"
                "Add your first API with /addapi",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                f"🔑 **Your API Credentials** ({len(apis)} total)\n\n"
                "✅ = Active | ⭕ = Inactive",
                reply_markup=get_api_list_keyboard(apis),
                parse_mode='Markdown'
            )
    elif action == 'positions':
        # Similar to show_positions_command but for callback
        pass
    elif action == 'balance':
        # Similar to check_balance_command but for callback
        pass
    elif action == 'help':
        help_text = """
📚 **Quick Help**

Use /help for detailed command reference.

**Quick Actions:**
• Trade: Execute preset strategies
• Strategies: Manage strategy presets
• APIs: Manage API credentials
• Positions: View & close positions
• Balance: Check wallet balance
        """
        await query.edit_message_text(
            help_text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )

# Additional handler functions would continue here...
# Due to length constraints, I'll provide the main.py structure

