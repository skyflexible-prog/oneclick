# bot/strangle_strategy.py - COMPLETE CONVERSATION HANDLER

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from telegram.constants import ParseMode
from config.database import Database
from database import crud
from database.models import (
    create_strangle_preset,
    get_strangle_presets,
    get_strangle_preset_by_id,
    delete_strangle_preset
)
from utils.helpers import encryptor
from utils.logger import bot_logger
from trading.strangle_executor import StrangleExecutor
from trading.delta_api import DeltaExchangeAPI

# ==================== CONVERSATION STATES ====================
SELECTING_STRANGLE_API = 300
SELECTING_STRANGLE_DIRECTION = 301
SELECTING_STRIKE_METHOD = 302
SELECTING_STRIKE_TYPE = 303
ENTERING_STRIKE_VALUE = 304
SELECTING_SL_TRIGGER_METHOD = 305
ENTERING_SL_TRIGGER = 306
SELECTING_SL_LIMIT_METHOD = 307
ENTERING_SL_LIMIT = 308
ENTERING_PRESET_NAME = 309
REVIEWING_STRANGLE = 310
MANAGING_STRANGLE_PRESETS = 311
EXECUTING_STRANGLE = 312


# ==================== MAIN ENTRY POINT ====================
async def strangle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main strangle strategy menu"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📝 Create Preset", callback_data="strangle_create")],
        [InlineKeyboardButton("▶️ Execute Preset", callback_data="strangle_execute")],
        [InlineKeyboardButton("📋 Manage Presets", callback_data="strangle_manage")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        "<b>🎲 Strangle Strategy</b>\n\n"
        "A strangle involves buying/selling OTM call and put options.\n\n"
        "<b>Features:</b>\n"
        "• Long Strangle: Buy OTM Call + Put\n"
        "• Short Strangle: Sell OTM Call + Put\n"
        "• Percentage or ATM offset strike selection\n"
        "• Advanced stop-loss options\n\n"
        "Choose an option:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return SELECTING_STRANGLE_API


# ==================== CREATE PRESET FLOW ====================
async def start_strangle_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start creating a new strangle preset - Select API"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    db = Database.get_database()
    
    # Get user's APIs
    apis = await crud.get_user_api_credentials(db, str(user_id))
    
    if not apis:
        await query.edit_message_text(
            "❌ <b>No API Keys Found</b>\n\n"
            "Please add an API key first using the 🔑 API Keys button.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="strangle_menu")
            ]])
        )
        return ConversationHandler.END
    
    # Build API selection keyboard
    keyboard = []
    for api in apis:
        keyboard.append([
            InlineKeyboardButton(
                f"🔑 {api['nickname']}",
                callback_data=f"strangle_api_{api['_id']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="strangle_menu")])
    
    await query.edit_message_text(
        "<b>📝 Create Strangle Preset</b>\n\n"
        "Select API to use for this preset:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return SELECTING_STRANGLE_API


async def select_strangle_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """API selected - Choose direction"""
    query = update.callback_query
    await query.answer()
    
    api_id = query.data.split('_')[-1]
    context.user_data['strangle_api_id'] = api_id
    
    keyboard = [
        [InlineKeyboardButton("📈 Long Strangle", callback_data="strangle_dir_long")],
        [InlineKeyboardButton("📉 Short Strangle", callback_data="strangle_dir_short")],
        [InlineKeyboardButton("🔙 Back", callback_data="strangle_create")]
    ]
    
    await query.edit_message_text(
        "<b>📊 Select Direction</b>\n\n"
        "<b>📈 Long Strangle:</b>\n"
        "• Buy OTM Call + Buy OTM Put\n"
        "• Profit from large price moves\n"
        "• Limited risk (premium paid)\n"
        "• Unlimited profit potential\n\n"
        "<b>📉 Short Strangle:</b>\n"
        "• Sell OTM Call + Sell OTM Put\n"
        "• Profit from low volatility\n"
        "• Limited profit (premium received)\n"
        "• Unlimited risk\n\n"
        "Choose direction:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return SELECTING_STRANGLE_DIRECTION


async def select_strangle_direction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direction selected - Choose strike method"""
    query = update.callback_query
    await query.answer()
    
    direction = query.data.split('_')[-1]
    context.user_data['strangle_direction'] = direction
    
    keyboard = [
        [InlineKeyboardButton("📊 Percentage (OTM/ITM %)", callback_data="strike_method_percentage")],
        [InlineKeyboardButton("🎯 ATM Offset (±N strikes)", callback_data="strike_method_atm_offset")],
        [InlineKeyboardButton("🔙 Back", callback_data="strangle_create")]
    ]
    
    await query.edit_message_text(
        "<b>🎯 Strike Selection Method</b>\n\n"
        "<b>📊 Percentage Method:</b>\n"
        "• Select OTM or ITM\n"
        "• Enter percentage (e.g., 5% OTM)\n"
        "• Example: Spot $60,000, 5% OTM\n"
        "  - Call: $63,000\n"
        "  - Put: $57,000\n\n"
        "<b>🎯 ATM Offset Method:</b>\n"
        "• Select offset from ATM\n"
        "• Enter number of strikes\n"
        "• Example: Spot $60,000, ATM+2\n"
        "  - Call: $61,000 (+2 strikes)\n"
        "  - Put: $59,000 (-2 strikes)\n\n"
        "Choose method:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return SELECTING_STRIKE_METHOD


async def select_strike_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Strike method selected"""
    query = update.callback_query
    await query.answer()
    
    method = query.data.split('_')[-1]
    context.user_data['strike_method'] = method
    
    if method == "percentage":
        # Ask for OTM or ITM
        keyboard = [
            [InlineKeyboardButton("⬆️ OTM (Out of the Money)", callback_data="strike_type_otm")],
            [InlineKeyboardButton("⬇️ ITM (In the Money)", callback_data="strike_type_itm")],
            [InlineKeyboardButton("🔙 Back", callback_data="strangle_create")]
        ]
        
        await query.edit_message_text(
            "<b>📊 Select Strike Type</b>\n\n"
            "<b>⬆️ OTM (Out of the Money):</b>\n"
            "• Call strike above spot\n"
            "• Put strike below spot\n"
            "• Lower premium\n"
            "• Standard for strangles\n\n"
            "<b>⬇️ ITM (In the Money):</b>\n"
            "• Call strike below spot\n"
            "• Put strike above spot\n"
            "• Higher premium\n"
            "• Less common\n\n"
            "Choose type:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return SELECTING_STRIKE_TYPE
    
    else:  # atm_offset
        # Skip strike type for ATM offset
        context.user_data['strike_type'] = None
        
        await query.edit_message_text(
            "<b>🎯 Enter Strike Offset</b>\n\n"
            "Enter the number of strikes from ATM (1-10):\n\n"
            "<b>Examples:</b>\n"
            "• <code>2</code> → ATM±2 strikes\n"
            "• <code>5</code> → ATM±5 strikes\n\n"
            "Type a number:",
            parse_mode=ParseMode.HTML
        )
        
        return ENTERING_STRIKE_VALUE


async def select_strike_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Strike type selected - Ask for percentage"""
    query = update.callback_query
    await query.answer()
    
    strike_type = query.data.split('_')[-1]
    context.user_data['strike_type'] = strike_type
    
    await query.edit_message_text(
        f"<b>📊 Enter Percentage for {strike_type.upper()}</b>\n\n"
        "Enter percentage (1-50):\n\n"
        "<b>Examples:</b>\n"
        "• <code>5</code> → 5% OTM\n"
        "• <code>10</code> → 10% OTM\n"
        "• <code>2.5</code> → 2.5% OTM\n\n"
        "Type percentage:",
        parse_mode=ParseMode.HTML
    )
    
    return ENTERING_STRIKE_VALUE


async def enter_strike_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User entered strike value"""
    try:
        value = float(update.message.text.strip())
        
        method = context.user_data.get('strike_method')
        
        # Validate value
        if method == "percentage":
            if not (1 <= value <= 50):
                await update.message.reply_text(
                    "❌ Invalid percentage. Please enter a value between 1 and 50."
                )
                return ENTERING_STRIKE_VALUE
        else:  # atm_offset
            if not (1 <= value <= 10):
                await update.message.reply_text(
                    "❌ Invalid offset. Please enter a value between 1 and 10."
                )
                return ENTERING_STRIKE_VALUE
        
        context.user_data['strike_value'] = value
        
        # Ask for stop-loss trigger method
        keyboard = [
            [InlineKeyboardButton("📊 Percentage", callback_data="sl_trigger_percentage")],
            [InlineKeyboardButton("💰 Numerical", callback_data="sl_trigger_numerical")],
            [InlineKeyboardButton("📈 Multiple", callback_data="sl_trigger_multiple")]
        ]
        
        await update.message.reply_text(
            "<b>🛡️ Stop-Loss Trigger Method</b>\n\n"
            "<b>📊 Percentage:</b>\n"
            "• % loss from entry\n"
            "• Example: 50% → SL at 50% loss\n\n"
            "<b>💰 Numerical:</b>\n"
            "• Fixed dollar amount\n"
            "• Example: $100 → SL when loss = $100\n\n"
            "<b>📈 Multiple:</b>\n"
            "• Multiple of entry cost\n"
            "• Example: 2x → SL when loss = 2x entry\n\n"
            "Choose method:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return SELECTING_SL_TRIGGER_METHOD
    
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid number. Please enter a valid number."
        )
        return ENTERING_STRIKE_VALUE


# bot/strangle_strategy.py - PART 2 (CONTINUED)

async def select_sl_trigger_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """SL trigger method selected"""
    query = update.callback_query
    await query.answer()
    
    method = query.data.split('_')[-1]
    context.user_data['sl_trigger_method'] = method
    
    if method == "percentage":
        prompt = "Enter trigger percentage (e.g., 50 for 50% loss):"
        example = "• <code>50</code> → Trigger at 50% loss\n• <code>75</code> → Trigger at 75% loss"
    elif method == "numerical":
        prompt = "Enter trigger amount in dollars:"
        example = "• <code>100</code> → Trigger at $100 loss\n• <code>250</code> → Trigger at $250 loss"
    else:  # multiple
        prompt = "Enter trigger multiple (e.g., 2 for 2x entry):"
        example = "• <code>2</code> → Trigger at 2x entry cost\n• <code>1.5</code> → Trigger at 1.5x entry cost"
    
    await query.edit_message_text(
        f"<b>🛡️ Stop-Loss Trigger Value</b>\n\n"
        f"{prompt}\n\n"
        f"<b>Examples:</b>\n{example}\n\n"
        "Type value:",
        parse_mode=ParseMode.HTML
    )
    
    return ENTERING_SL_TRIGGER


async def enter_sl_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User entered SL trigger value"""
    try:
        value = float(update.message.text.strip())
        
        if value <= 0:
            await update.message.reply_text(
                "❌ Invalid value. Please enter a positive number."
            )
            return ENTERING_SL_TRIGGER
        
        context.user_data['sl_trigger_value'] = value
        
        # Ask for SL limit method
        keyboard = [
            [InlineKeyboardButton("📊 Percentage", callback_data="sl_limit_percentage")],
            [InlineKeyboardButton("💰 Numerical", callback_data="sl_limit_numerical")],
            [InlineKeyboardButton("📈 Multiple", callback_data="sl_limit_multiple")]
        ]
        
        await update.message.reply_text(
            "<b>🛡️ Stop-Loss Limit Method</b>\n\n"
            "Limit price should be slightly worse than trigger.\n\n"
            "<b>📊 Percentage:</b>\n"
            "• % loss from entry\n"
            "• Example: 55% (if trigger is 50%)\n\n"
            "<b>💰 Numerical:</b>\n"
            "• Fixed dollar amount\n"
            "• Example: $110 (if trigger is $100)\n\n"
            "<b>📈 Multiple:</b>\n"
            "• Multiple of entry cost\n"
            "• Example: 2.2x (if trigger is 2x)\n\n"
            "Choose method:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return SELECTING_SL_LIMIT_METHOD
    
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid number. Please enter a valid number."
        )
        return ENTERING_SL_TRIGGER


async def select_sl_limit_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """SL limit method selected"""
    query = update.callback_query
    await query.answer()
    
    method = query.data.split('_')[-1]
    context.user_data['sl_limit_method'] = method
    
    if method == "percentage":
        prompt = "Enter limit percentage (should be > trigger):"
        example = "• <code>55</code> → Limit at 55% loss"
    elif method == "numerical":
        prompt = "Enter limit amount in dollars (should be > trigger):"
        example = "• <code>110</code> → Limit at $110 loss"
    else:  # multiple
        prompt = "Enter limit multiple (should be > trigger):"
        example = "• <code>2.2</code> → Limit at 2.2x entry cost"
    
    await query.edit_message_text(
        f"<b>🛡️ Stop-Loss Limit Value</b>\n\n"
        f"{prompt}\n\n"
        f"<b>Examples:</b>\n{example}\n\n"
        "Type value:",
        parse_mode=ParseMode.HTML
    )
    
    return ENTERING_SL_LIMIT


async def enter_sl_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User entered SL limit value"""
    try:
        value = float(update.message.text.strip())
        
        if value <= 0:
            await update.message.reply_text(
                "❌ Invalid value. Please enter a positive number."
            )
            return ENTERING_SL_LIMIT
        
        context.user_data['sl_limit_value'] = value
        
        # Ask for preset name
        await update.message.reply_text(
            "<b>📝 Preset Name</b>\n\n"
            "Enter a name for this preset:\n\n"
            "<b>Examples:</b>\n"
            "• <code>5% OTM Long Strangle</code>\n"
            "• <code>ATM+2 Short Strangle</code>\n"
            "• <code>My Strangle Strategy</code>\n\n"
            "Type name:",
            parse_mode=ParseMode.HTML
        )
        
        return ENTERING_PRESET_NAME
    
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid number. Please enter a valid number."
        )
        return ENTERING_SL_LIMIT


async def enter_preset_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User entered preset name - Show review"""
    preset_name = update.message.text.strip()
    
    if len(preset_name) < 3:
        await update.message.reply_text(
            "❌ Name too short. Please enter at least 3 characters."
        )
        return ENTERING_PRESET_NAME
    
    context.user_data['preset_name'] = preset_name
    
    # Build review message
    direction = context.user_data['strangle_direction']
    strike_method = context.user_data['strike_method']
    strike_type = context.user_data.get('strike_type', 'N/A')
    strike_value = context.user_data['strike_value']
    sl_trigger_method = context.user_data['sl_trigger_method']
    sl_trigger_value = context.user_data['sl_trigger_value']
    sl_limit_method = context.user_data['sl_limit_method']
    sl_limit_value = context.user_data['sl_limit_value']
    
    # Format strike display
    if strike_method == "percentage":
        strike_display = f"{strike_value}% {strike_type.upper()}"
    else:
        strike_display = f"ATM±{int(strike_value)}"
    
    # Format SL display
    sl_trigger_display = f"{sl_trigger_value}"
    if sl_trigger_method == "percentage":
        sl_trigger_display += "%"
    elif sl_trigger_method == "numerical":
        sl_trigger_display = f"${sl_trigger_display}"
    else:
        sl_trigger_display += "x"
    
    sl_limit_display = f"{sl_limit_value}"
    if sl_limit_method == "percentage":
        sl_limit_display += "%"
    elif sl_limit_method == "numerical":
        sl_limit_display = f"${sl_limit_display}"
    else:
        sl_limit_display += "x"
    
    review_message = (
        f"<b>📊 Strangle Preset Review</b>\n\n"
        f"<b>Name:</b> {preset_name}\n"
        f"<b>Direction:</b> {direction.capitalize()} Strangle\n"
        f"<b>Asset:</b> BTC\n"
        f"<b>Expiry:</b> Daily\n\n"
        f"<b>Strike Selection:</b>\n"
        f"• Method: {strike_method.replace('_', ' ').title()}\n"
        f"• Value: {strike_display}\n\n"
        f"<b>Stop-Loss:</b>\n"
        f"• Trigger: {sl_trigger_display} ({sl_trigger_method})\n"
        f"• Limit: {sl_limit_display} ({sl_limit_method})\n\n"
        f"Confirm to save this preset?"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Confirm", callback_data="strangle_confirm")],
        [InlineKeyboardButton("❌ Cancel", callback_data="strangle_menu")]
    ]
    
    await update.message.reply_text(
        review_message,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return REVIEWING_STRANGLE


async def confirm_strangle_preset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save the strangle preset"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    db = Database.get_database()
    
    try:
        # Create preset
        preset_id = await create_strangle_preset(
            db=db,
            user_id=user_id,
            api_id=context.user_data['strangle_api_id'],
            preset_name=context.user_data['preset_name'],
            direction=context.user_data['strangle_direction'],
            strike_method=context.user_data['strike_method'],
            strike_type=context.user_data.get('strike_type'),
            strike_value=context.user_data['strike_value'],
            sl_trigger_method=context.user_data['sl_trigger_method'],
            sl_trigger_value=context.user_data['sl_trigger_value'],
            sl_limit_method=context.user_data['sl_limit_method'],
            sl_limit_value=context.user_data['sl_limit_value']
        )
        
        await query.edit_message_text(
            f"✅ <b>Preset Created!</b>\n\n"
            f"<b>Name:</b> {context.user_data['preset_name']}\n\n"
            f"Your strangle preset has been saved.\n"
            f"Use 'Execute Preset' to trade with this configuration.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to Strangle Menu", callback_data="strangle_menu")
            ]])
        )
        
        # Clear context
        context.user_data.clear()
        
        return ConversationHandler.END
    
    except Exception as e:
        bot_logger.error(f"Error creating strangle preset: {e}")
        await query.edit_message_text(
            f"❌ <b>Error</b>\n\nFailed to create preset: {str(e)}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="strangle_menu")
            ]])
        )
        return ConversationHandler.END
        
