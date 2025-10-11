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
