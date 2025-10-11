from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu keyboard"""
    keyboard = [
        [InlineKeyboardButton("📊 Trade", callback_data="menu_trade")],
        [InlineKeyboardButton("⚙️ Manage APIs", callback_data="menu_apis"),
         InlineKeyboardButton("📋 Strategies", callback_data="menu_strategies")],
        [InlineKeyboardButton("💼 Positions", callback_data="menu_positions"),
         InlineKeyboardButton("💰 Balance", callback_data="menu_balance")],
        [InlineKeyboardButton("📈 History", callback_data="menu_history"),
         InlineKeyboardButton("❓ Help", callback_data="menu_help")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_strategy_type_keyboard() -> InlineKeyboardMarkup:
    """Strategy type selection keyboard"""
    keyboard = [
        [InlineKeyboardButton("🎯 ATM Straddle", callback_data="type_straddle")],
        [InlineKeyboardButton("🎪 OTM Strangle", callback_data="type_strangle")],
        [InlineKeyboardButton("🔄 Compare Both", callback_data="type_compare")],
        [InlineKeyboardButton("« Back", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_direction_keyboard() -> InlineKeyboardMarkup:
    """Direction selection keyboard"""
    keyboard = [
        [InlineKeyboardButton("📈 Long (Buy)", callback_data="dir_long")],
        [InlineKeyboardButton("📉 Short (Sell)", callback_data="dir_short")],
        [InlineKeyboardButton("« Back", callback_data="back_strategy_type")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_expiry_keyboard() -> InlineKeyboardMarkup:
    """Expiry selection keyboard"""
    keyboard = [
        [InlineKeyboardButton("📅 Daily", callback_data="exp_daily")],
        [InlineKeyboardButton("📆 Weekly", callback_data="exp_weekly")],
        [InlineKeyboardButton("📊 Monthly", callback_data="exp_monthly")],
        [InlineKeyboardButton("« Back", callback_data="back_direction")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_strike_offset_keyboard(strategy_type: str) -> InlineKeyboardMarkup:
    """Strike offset selection keyboard"""
    if strategy_type == 'strangle':
        keyboard = [
            [InlineKeyboardButton("Near OTM (±1-2)", callback_data="offset_near")],
            [InlineKeyboardButton("Mid OTM (±3-4)", callback_data="offset_mid")],
            [InlineKeyboardButton("Far OTM (±5-6)", callback_data="offset_far")],
            [InlineKeyboardButton("Custom Offset", callback_data="offset_custom")],
            [InlineKeyboardButton("« Back", callback_data="back_expiry")]
        ]
    else:  # straddle
        keyboard = [
            [InlineKeyboardButton("Exact ATM (0)", callback_data="offset_atm")],
            [InlineKeyboardButton("Custom Offset", callback_data="offset_custom")],
            [InlineKeyboardButton("« Back", callback_data="back_expiry")]
        ]
    return InlineKeyboardMarkup(keyboard)

def get_confirmation_keyboard(action: str) -> InlineKeyboardMarkup:
    """Confirmation keyboard"""
    keyboard = [
        [InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_{action}"),
         InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{action}")],
        [InlineKeyboardButton("⚙️ Modify", callback_data=f"modify_{action}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_strategies_list_keyboard(strategies: List[Dict]) -> InlineKeyboardMarkup:
    """Display list of user strategies"""
    keyboard = []
    for strategy in strategies:
        strategy_id = str(strategy['_id'])
        name = strategy['name']
        strategy_type = strategy['strategy_type'].upper()
        direction = strategy['direction'].upper()
        
        button_text = f"{name} | {strategy_type} | {direction}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"strategy_{strategy_id}")])
    
    keyboard.append([InlineKeyboardButton("➕ Create New", callback_data="create_strategy")])
    keyboard.append([InlineKeyboardButton("« Back", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def get_strategy_action_keyboard(strategy_id: str) -> InlineKeyboardMarkup:
    """Actions for a specific strategy"""
    keyboard = [
        [InlineKeyboardButton("🚀 Execute Trade", callback_data=f"execute_{strategy_id}")],
        [InlineKeyboardButton("✏️ Edit", callback_data=f"edit_{strategy_id}"),
         InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_{strategy_id}")],
        [InlineKeyboardButton("« Back", callback_data="menu_strategies")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_api_list_keyboard(apis: List[Dict]) -> InlineKeyboardMarkup:
    """Display list of user API credentials"""
    keyboard = []
    for api in apis:
        api_id = str(api['_id'])
        nickname = api['nickname']
        is_active = "✅" if api.get('is_active') else "⭕"
        
        button_text = f"{is_active} {nickname}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"api_{api_id}")])
    
    keyboard.append([InlineKeyboardButton("➕ Add New API", callback_data="add_api")])
    keyboard.append([InlineKeyboardButton("« Back", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)

def get_api_action_keyboard(api_id: str, is_active: bool) -> InlineKeyboardMarkup:
    """Actions for a specific API"""
    keyboard = []
    
    if not is_active:
        keyboard.append([InlineKeyboardButton("✅ Set as Active", callback_data=f"activate_{api_id}")])
    
    keyboard.append([InlineKeyboardButton("💰 Check Balance", callback_data=f"balance_{api_id}")])
    keyboard.append([InlineKeyboardButton("🗑️ Delete", callback_data=f"deleteapi_{api_id}")])
    keyboard.append([InlineKeyboardButton("« Back", callback_data="menu_apis")])
    
    return InlineKeyboardMarkup(keyboard)

def get_positions_keyboard(positions: List[Dict]) -> InlineKeyboardMarkup:
    """Display active positions"""
    keyboard = []
    
    for i, pos in enumerate(positions):
        symbol = pos.get('symbol', 'Unknown')
        pnl = pos.get('unrealized_pnl', 0)
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        
        button_text = f"{pnl_emoji} {symbol} | P&L: ₹{pnl:.2f}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"position_{i}")])
    
    if positions:
        keyboard.append([InlineKeyboardButton("🚫 Close All Positions", callback_data="close_all_positions")])
    
    keyboard.append([InlineKeyboardButton("🔄 Refresh", callback_data="menu_positions")])
    keyboard.append([InlineKeyboardButton("« Back", callback_data="back_main")])
    
    return InlineKeyboardMarkup(keyboard)

def get_position_action_keyboard(position_index: int) -> InlineKeyboardMarkup:
    """Actions for a specific position"""
    keyboard = [
        [InlineKeyboardButton("🚫 Close Position", callback_data=f"close_position_{position_index}")],
        [InlineKeyboardButton("« Back", callback_data="menu_positions")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_yes_no_keyboard(action: str) -> InlineKeyboardMarkup:
    """Simple yes/no keyboard"""
    keyboard = [
        [InlineKeyboardButton("Yes", callback_data=f"yes_{action}"),
         InlineKeyboardButton("No", callback_data=f"no_{action}")]
    ]
    return InlineKeyboardMarkup(keyboard)
