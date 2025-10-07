from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Dict


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu keyboard"""
    keyboard = [
        [InlineKeyboardButton("📊 Trade", callback_data="trade")],
        [InlineKeyboardButton("📈 Positions", callback_data="positions")],
        [
            InlineKeyboardButton("⚙️ APIs", callback_data="list_apis"),
            InlineKeyboardButton("🎯 Strategies", callback_data="list_strategies")
        ],
        [
            InlineKeyboardButton("💰 Balance", callback_data="balance"),
            InlineKeyboardButton("📜 History", callback_data="history")
        ],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_api_management_keyboard() -> InlineKeyboardMarkup:
    """API management keyboard"""
    keyboard = [
        [InlineKeyboardButton("➕ Add API", callback_data="add_api")],
        [InlineKeyboardButton("📋 List APIs", callback_data="list_apis")],
        [InlineKeyboardButton("✏️ Select Active API", callback_data="select_api")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_api_list_keyboard(apis: List[Dict]) -> InlineKeyboardMarkup:
    """Keyboard showing list of APIs"""
    keyboard = []
    
    for api in apis:
        status = "✅" if api.get('is_active') else "⚪"
        button_text = f"{status} {api.get('nickname', 'Unnamed')}"
        keyboard.append([
            InlineKeyboardButton(button_text, callback_data=f"view_api_{api['_id']}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="api_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_api_action_keyboard(api_id: str) -> InlineKeyboardMarkup:
    """Actions for specific API"""
    keyboard = [
        [InlineKeyboardButton("✅ Set Active", callback_data=f"activate_api_{api_id}")],
        [InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_api_{api_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data="list_apis")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_strategy_management_keyboard() -> InlineKeyboardMarkup:
    """Strategy management keyboard"""
    keyboard = [
        [InlineKeyboardButton("➕ Create Strategy", callback_data="create_strategy")],
        [InlineKeyboardButton("📋 List Strategies", callback_data="list_strategies")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_strategy_list_keyboard(strategies: List[Dict]) -> InlineKeyboardMarkup:
    """Keyboard showing list of strategies"""
    keyboard = []
    
    # Add existing strategies
    for strategy in strategies:
        direction_emoji = "📈" if strategy.get('direction') == 'long' else "📉"
        button_text = f"{direction_emoji} {strategy.get('name', 'Unnamed')}"
        keyboard.append([
            InlineKeyboardButton(button_text, callback_data=f"view_strategy_{strategy['_id']}")
        ])
    
    # Add "Create New Strategy" button
    keyboard.append([
        InlineKeyboardButton("➕ Create New Strategy", callback_data="create_strategy")
    ])
    
    # Add Back button
    keyboard.append([
        InlineKeyboardButton("🔙 Back", callback_data="main_menu")
    ])
    
    return InlineKeyboardMarkup(keyboard)


def get_strategy_action_keyboard(strategy_id: str) -> InlineKeyboardMarkup:
    """Actions for specific strategy"""
    keyboard = [
        [InlineKeyboardButton("✏️ Edit", callback_data=f"edit_strategy_{strategy_id}")],
        [InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_strategy_{strategy_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data="list_strategies")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_trade_execution_keyboard(strategies: List[Dict]) -> InlineKeyboardMarkup:
    """Keyboard for trade execution with strategy buttons"""
    keyboard = []
    
    for strategy in strategies:
        direction_emoji = "📈" if strategy.get('direction') == 'long' else "📉"
        underlying = strategy.get('underlying', 'BTC')
        button_text = f"{direction_emoji} {strategy.get('name')} ({underlying})"
        keyboard.append([
            InlineKeyboardButton(button_text, callback_data=f"execute_{strategy['_id']}")
        ])
    
    if not strategies:
        keyboard.append([InlineKeyboardButton("➕ Create Strategy First", callback_data="create_strategy")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_trade_confirmation_keyboard(strategy_id: str) -> InlineKeyboardMarkup:
    """Confirmation keyboard for trade execution"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_trade_{strategy_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data="trade")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_position_list_keyboard(positions: List[Dict]) -> InlineKeyboardMarkup:
    """Keyboard showing open positions"""
    keyboard = []
    
    for idx, position in enumerate(positions):
        pnl_emoji = "🟢" if position.get('pnl', 0) >= 0 else "🔴"
        button_text = f"{pnl_emoji} {position.get('underlying', 'BTC')} - ₹{position.get('pnl', 0):.2f}"
        keyboard.append([
            InlineKeyboardButton(button_text, callback_data=f"view_position_{position['_id']}")
        ])
    
    if not positions:
        keyboard.append([InlineKeyboardButton("No open positions", callback_data="main_menu")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_position_action_keyboard(trade_id: str) -> InlineKeyboardMarkup:
    """Actions for specific position"""
    keyboard = [
        [InlineKeyboardButton("❌ Close Position", callback_data=f"close_position_{trade_id}")],
        [InlineKeyboardButton("🔄 Refresh", callback_data=f"view_position_{trade_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data="positions")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_close_position_confirmation_keyboard(trade_id: str) -> InlineKeyboardMarkup:
    """Confirmation for closing position"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, Close", callback_data=f"confirm_close_{trade_id}"),
            InlineKeyboardButton("❌ No, Keep Open", callback_data=f"view_position_{trade_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_direction_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting strategy direction"""
    keyboard = [
        [InlineKeyboardButton("📈 Long Straddle", callback_data="direction_long")],
        [InlineKeyboardButton("📉 Short Straddle", callback_data="direction_short")],
        [InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_underlying_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting underlying asset"""
    keyboard = [
        [InlineKeyboardButton("₿ BTC", callback_data="underlying_BTC")],
        [InlineKeyboardButton("Ξ ETH", callback_data="underlying_ETH")],
        [InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_expiry_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting expiry type"""
    keyboard = [
        [InlineKeyboardButton("📅 Daily", callback_data="expiry_daily")],
        [InlineKeyboardButton("📆 Weekly", callback_data="expiry_weekly")],
        [InlineKeyboardButton("🗓️ Monthly", callback_data="expiry_monthly")],
        [InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Simple cancel keyboard"""
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]]
    return InlineKeyboardMarkup(keyboard)
  
