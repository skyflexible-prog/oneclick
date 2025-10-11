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

# Add these functions to bot/handlers.py

async def handle_strategy_type_callback(query, context, data):
    """Handle strategy type selection"""
    user_id = query.from_user.id
    strategy_type = data.replace('type_', '')
    
    if strategy_type == 'compare':
        # Show comparison between straddle and strangle
        user = query.from_user
        db_user = user_crud.get_user_by_telegram_id(user.id)
        active_api = api_crud.get_active_credential(str(db_user['_id']))
        
        if not active_api:
            await query.edit_message_text(
                "⚠️ Please add and activate an API credential first.",
                parse_mode='Markdown'
            )
            return
        
        # Get API and create comparison
        api_key = encryptor.decrypt(active_api['api_key_encrypted'])
        api_secret = encryptor.decrypt(active_api['api_secret_encrypted'])
        delta_api = DeltaExchangeAPI(api_key, api_secret)
        
        spot_price = delta_api.get_spot_price('BTCUSD')
        if not spot_price:
            await query.edit_message_text("❌ Failed to fetch spot price")
            return
        
        strangle = StrangleStrategy(delta_api)
        comparison = strangle.compare_with_straddle(spot_price, 2, 2, 'BTC')
        
        if comparison:
            comp_text = f"""
📊 **Straddle vs Strangle Comparison**

Spot Price: {format_currency(spot_price)}

**ATM Straddle:**
Strike: {comparison['straddle']['strike']}
Total Premium: {format_currency(comparison['straddle']['total_premium'])}

**OTM Strangle (±2):**
Call Strike: {comparison['strangle']['call_strike']}
Put Strike: {comparison['strangle']['put_strike']}
Total Premium: {format_currency(comparison['strangle']['total_premium'])}

💰 **Cost Savings: {comparison['cost_savings_pct']:.2f}%**
Difference: {format_currency(comparison['cost_difference'])}
            """
            await query.edit_message_text(
                comp_text,
                reply_markup=get_strategy_type_keyboard(),
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text("❌ Failed to fetch comparison data")
        return
    
    # Store strategy type in user state
    if user_id not in user_states:
        user_states[user_id] = {}
    
    user_states[user_id]['action'] = 'create_strategy'
    user_states[user_id]['strategy_type'] = strategy_type
    user_states[user_id]['step'] = 'direction'
    
    await query.edit_message_text(
        f"📋 Creating **{strategy_type.upper()}** Strategy\n\n"
        "Select direction:",
        reply_markup=get_direction_keyboard(),
        parse_mode='Markdown'
    )

async def handle_direction_callback(query, context, data):
    """Handle direction selection"""
    user_id = query.from_user.id
    direction = data.replace('dir_', '')
    
    if user_id not in user_states:
        await query.edit_message_text("❌ Session expired. Please start over.")
        return
    
    user_states[user_id]['direction'] = direction
    user_states[user_id]['step'] = 'expiry'
    
    await query.edit_message_text(
        f"Direction: **{direction.upper()}**\n\n"
        "Select expiry type:",
        reply_markup=get_expiry_keyboard(),
        parse_mode='Markdown'
    )

async def handle_expiry_callback(query, context, data):
    """Handle expiry selection"""
    user_id = query.from_user.id
    expiry = data.replace('exp_', '')
    
    if user_id not in user_states:
        await query.edit_message_text("❌ Session expired. Please start over.")
        return
    
    user_states[user_id]['expiry_type'] = expiry
    user_states[user_id]['step'] = 'strike_offset'
    
    strategy_type = user_states[user_id].get('strategy_type', 'straddle')
    
    await query.edit_message_text(
        f"Expiry: **{expiry.upper()}**\n\n"
        "Select strike offset:",
        reply_markup=get_strike_offset_keyboard(strategy_type),
        parse_mode='Markdown'
    )

async def handle_offset_callback(query, context, data):
    """Handle strike offset selection"""
    user_id = query.from_user.id
    offset_type = data.replace('offset_', '')
    
    if user_id not in user_states:
        await query.edit_message_text("❌ Session expired. Please start over.")
        return
    
    strategy_type = user_states[user_id].get('strategy_type', 'straddle')
    
    if offset_type == 'custom':
        user_states[user_id]['step'] = 'custom_offset'
        await query.edit_message_text(
            "Enter custom strike offset (e.g., 3 for ±3 strikes from ATM):"
        )
        return
    
    # Set predefined offsets
    if offset_type == 'atm':
        call_offset = 0
        put_offset = 0
    elif offset_type == 'near':
        call_offset = 2
        put_offset = 2
    elif offset_type == 'mid':
        call_offset = 4
        put_offset = 4
    elif offset_type == 'far':
        call_offset = 6
        put_offset = 6
    
    user_states[user_id]['call_strike_offset'] = call_offset
    user_states[user_id]['put_strike_offset'] = put_offset
    user_states[user_id]['step'] = 'lot_size'
    
    await query.edit_message_text(
        f"Strike Offset: **±{call_offset}**\n\n"
        "Enter lot size (number of contracts):"
    )

async def handle_execute_callback(query, context, data):
    """Handle strategy execution"""
    strategy_id = data.replace('execute_', '')
    user = query.from_user
    db_user = user_crud.get_user_by_telegram_id(user.id)
    
    # Get strategy details
    strategy = strategy_crud.get_strategy_by_id(strategy_id)
    if not strategy:
        await query.edit_message_text("❌ Strategy not found")
        return
    
    # Get active API
    active_api = api_crud.get_active_credential(str(db_user['_id']))
    if not active_api:
        await query.edit_message_text("⚠️ No active API found")
        return
    
    # Decrypt credentials
    api_key = encryptor.decrypt(active_api['api_key_encrypted'])
    api_secret = encryptor.decrypt(active_api['api_secret_encrypted'])
    delta_api = DeltaExchangeAPI(api_key, api_secret)
    
    # Get spot price
    spot_price = delta_api.get_spot_price('BTCUSD')
    if not spot_price:
        await query.edit_message_text("❌ Failed to fetch spot price")
        return
    
    strategy_type = strategy['strategy_type']
    direction = strategy['direction']
    lot_size = strategy['lot_size']
    
    # Execute based on strategy type
    if strategy_type == 'straddle':
        straddle = StraddleStrategy(delta_api)
        options = straddle.find_atm_options(spot_price, 'BTC', strategy['expiry_type'])
        
        if not options:
            await query.edit_message_text("❌ Failed to find ATM options")
            return
        
        call_option, put_option = options
        details = straddle.calculate_straddle_details(call_option, put_option, lot_size, direction)
        
    else:  # strangle
        strangle = StrangleStrategy(delta_api)
        atm_strike = strangle.find_atm_strike(spot_price)
        call_strike, put_strike = strangle.calculate_otm_strikes(
            atm_strike, 
            strategy['call_strike_offset'],
            strategy['put_strike_offset']
        )
        
        options = strangle.find_otm_options(call_strike, put_strike, 'BTC', strategy['expiry_type'])
        
        if not options:
            await query.edit_message_text("❌ Failed to find OTM options")
            return
        
        call_option, put_option = options
        details = strangle.calculate_strangle_details(
            call_option, put_option, atm_strike, lot_size, direction
        )
    
    if not details:
        await query.edit_message_text("❌ Failed to calculate trade details")
        return
    
    # Show confirmation
    confirm_text = f"""
🎯 **Trade Confirmation**

Strategy: {strategy['name']}
Type: {strategy_type.upper()}
Direction: {direction.upper()}

Spot Price: {format_currency(spot_price)}

**Call Leg:**
Symbol: {details['call_symbol']}
Strike: {details.get('call_strike', details['strike'])}
Premium: {format_currency(details['call_premium'])}

**Put Leg:**
Symbol: {details['put_symbol']}
Strike: {details.get('put_strike', details['strike'])}
Premium: {format_currency(details['put_premium'])}

**Total:**
Premium: {format_currency(details['total_premium'])}
Cost: {format_currency(details['total_cost'])}
Lot Size: {lot_size}

Breakeven Range: {format_currency(details['lower_breakeven'])} - {format_currency(details['upper_breakeven'])}

Proceed with execution?
    """
    
    # Store details in context for confirmation
    context.user_data['pending_trade'] = details
    context.user_data['strategy_id'] = strategy_id
    context.user_data['strategy_type'] = strategy_type
    
    await query.edit_message_text(
        confirm_text,
        reply_markup=get_confirmation_keyboard('trade'),
        parse_mode='Markdown'
    )

async def handle_confirm_callback(query, context, data):
    """Handle trade confirmation"""
    action = data.replace('confirm_', '')
    
    if action == 'trade':
        user = query.from_user
        db_user = user_crud.get_user_by_telegram_id(user.id)
        
        # Get pending trade details
        details = context.user_data.get('pending_trade')
        strategy_id = context.user_data.get('strategy_id')
        strategy_type = context.user_data.get('strategy_type')
        
        if not details:
            await query.edit_message_text("❌ Trade details not found")
            return
        
        # Get API
        active_api = api_crud.get_active_credential(str(db_user['_id']))
        api_key = encryptor.decrypt(active_api['api_key_encrypted'])
        api_secret = encryptor.decrypt(active_api['api_secret_encrypted'])
        delta_api = DeltaExchangeAPI(api_key, api_secret)
        
        # Validate margin
        if strategy_type == 'straddle':
            straddle = StraddleStrategy(delta_api)
            if not straddle.validate_margin(details['total_cost']):
                await query.edit_message_text("❌ Insufficient margin for this trade")
                return
            
            # Execute trade
            await query.edit_message_text("⏳ Executing trade...")
            call_order, put_order = straddle.execute_straddle(
                details['call_product_id'],
                details['put_product_id'],
                details['lot_size'],
                details['direction']
            )
        else:
            strangle = StrangleStrategy(delta_api)
            if not strangle.validate_margin(details['total_cost']):
                await query.edit_message_text("❌ Insufficient margin for this trade")
                return
            
            # Execute trade
            await query.edit_message_text("⏳ Executing trade...")
            call_order, put_order = strangle.execute_strangle(
                details['call_product_id'],
                details['put_product_id'],
                details['lot_size'],
                details['direction']
            )
        
        if not call_order or not put_order:
            await query.edit_message_text("❌ Trade execution failed")
            return
        
        # Save trade to database
        from trading.order_manager import OrderManager
        order_mgr = OrderManager(delta_api)
        
        call_fill_price = order_mgr.get_fill_price(call_order)
        put_fill_price = order_mgr.get_fill_price(put_order)
        
        trade_id = trade_crud.create_trade(
            user_id=str(db_user['_id']),
            api_id=str(active_api['_id']),
            strategy_id=strategy_id,
            strategy_type=strategy_type,
            call_symbol=details['call_symbol'],
            put_symbol=details['put_symbol'],
            strike=details.get('strike', details.get('atm_strike')),
            atm_strike=details.get('atm_strike'),
            call_strike=details.get('call_strike'),
            put_strike=details.get('put_strike'),
            spot_at_entry=details.get('spot_at_entry'),
            call_entry_price=call_fill_price,
            put_entry_price=put_fill_price,
            lot_size=details['lot_size'],
            stop_loss_pct=20.0,  # From strategy
            upper_breakeven=details['upper_breakeven'],
            lower_breakeven=details['lower_breakeven']
        )
        
        success_text = f"""
✅ **Trade Executed Successfully!**

Trade ID: {trade_id}

Call Order: {call_order.get('id')}
Fill Price: {format_currency(call_fill_price)}

Put Order: {put_order.get('id')}
Fill Price: {format_currency(put_fill_price)}

Monitor your position with /positions
        """
        
        await query.edit_message_text(success_text, parse_mode='Markdown')
        
        # Clear pending trade
        context.user_data.pop('pending_trade', None)
        context.user_data.pop('strategy_id', None)

async def handle_close_position_callback(query, context, data):
    """Handle position closure"""
    if data == 'close_all_positions':
        # Close all positions confirmation
        await query.edit_message_text(
            "⚠️ Are you sure you want to close ALL positions?",
            reply_markup=get_yes_no_keyboard('close_all'),
            parse_mode='Markdown'
        )
    else:
        position_index = int(data.replace('close_position_', ''))
        positions = context.user_data.get('positions', [])
        
        if position_index >= len(positions):
            await query.edit_message_text("❌ Position not found")
            return
        
        position = positions[position_index]
        
        confirm_text = f"""
⚠️ **Close Position**

Symbol: {position['symbol']}
Current P&L: {format_currency(position['unrealized_pnl'])}

Proceed with closing?
        """
        
        context.user_data['closing_position'] = position
        
        await query.edit_message_text(
            confirm_text,
            reply_markup=get_yes_no_keyboard(f'close_pos_{position_index}'),
            parse_mode='Markdown'
        )

async def handle_back_callback(query, context, data):
    """Handle back navigation"""
    target = data.replace('back_', '')
    
    if target == 'main':
        await query.edit_message_text(
            "🏠 **Main Menu**",
            reply_markup=get_main_menu_keyboard(),
            parse_mode='Markdown'
        )
    # Add more back navigation handlers as needed
    
