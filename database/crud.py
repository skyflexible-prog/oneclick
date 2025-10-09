from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from typing import List, Optional, Dict
from datetime import datetime
from database.models import (
    UserModel, APICredentialModel, StrategyModel, 
    TradeModel, OrderModel
)


# ==================== USER OPERATIONS ====================

async def create_user(db: AsyncIOMotorDatabase, telegram_id: int, username: str = None) -> str:
    """Create new user"""
    user_data = {
        "telegram_id": telegram_id,
        "username": username,
        "is_active": True,
        "created_at": datetime.utcnow()
    }
    result = await db.users.insert_one(user_data)
    return str(result.inserted_id)


async def get_user_by_telegram_id(db: AsyncIOMotorDatabase, telegram_id: int) -> Optional[Dict]:
    """Get user by Telegram ID"""
    user = await db.users.find_one({"telegram_id": telegram_id})
    if user:
        user["_id"] = str(user["_id"])
    return user


async def get_user_by_id(db: AsyncIOMotorDatabase, user_id: str) -> Optional[Dict]:
    """Get user by database ID"""
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if user:
        user["_id"] = str(user["_id"])
    return user


# ==================== API CREDENTIALS OPERATIONS ====================

async def create_api_credential(
    db: AsyncIOMotorDatabase,
    user_id: str,
    nickname: str,
    api_key_encrypted: str,
    api_secret_encrypted: str
) -> str:
    """Create new API credential"""
    credential_data = {
        "user_id": ObjectId(user_id),
        "nickname": nickname,
        "api_key_encrypted": api_key_encrypted,
        "api_secret_encrypted": api_secret_encrypted,
        "is_active": True,
        "created_at": datetime.utcnow()
    }
    result = await db.api_credentials.insert_one(credential_data)
    return str(result.inserted_id)


async def get_user_api_credentials(db: AsyncIOMotorDatabase, user_id: str) -> List[Dict]:
    """Get all API credentials for a user"""
    credentials = []
    cursor = db.api_credentials.find({"user_id": ObjectId(user_id)})
    async for credential in cursor:
        credential["_id"] = str(credential["_id"])
        credential["user_id"] = str(credential["user_id"])
        credentials.append(credential)
    return credentials


async def get_api_credential_by_id(db: AsyncIOMotorDatabase, api_id: str) -> Optional[Dict]:
    """Get API credential by ID"""
    credential = await db.api_credentials.find_one({"_id": ObjectId(api_id)})
    if credential:
        credential["_id"] = str(credential["_id"])
        credential["user_id"] = str(credential["user_id"])
    return credential


async def set_active_api(db: AsyncIOMotorDatabase, user_id: str, api_id: str):
    """Set specific API as active and deactivate others"""
    # Deactivate all APIs for user
    await db.api_credentials.update_many(
        {"user_id": ObjectId(user_id)},
        {"$set": {"is_active": False}}
    )
    # Activate selected API
    await db.api_credentials.update_one(
        {"_id": ObjectId(api_id)},
        {"$set": {"is_active": True}}
    )


async def delete_api_credential(db: AsyncIOMotorDatabase, api_id: str):
    """Delete API credential"""
    await db.api_credentials.delete_one({"_id": ObjectId(api_id)})


# ==================== STRATEGY OPERATIONS ====================

async def create_strategy(db: AsyncIOMotorDatabase, strategy_data: Dict) -> str:
    """Create new trading strategy"""
    strategy_data["user_id"] = ObjectId(strategy_data["user_id"])
    strategy_data["api_id"] = ObjectId(strategy_data["api_id"])
    strategy_data["created_at"] = datetime.utcnow()
    strategy_data["updated_at"] = datetime.utcnow()
    
    result = await db.strategies.insert_one(strategy_data)
    return str(result.inserted_id)


async def get_user_strategies(db: AsyncIOMotorDatabase, user_id: str) -> List[Dict]:
    """Get all strategies for a user"""
    strategies = []
    cursor = db.strategies.find({"user_id": ObjectId(user_id)})
    async for strategy in cursor:
        strategy["_id"] = str(strategy["_id"])
        strategy["user_id"] = str(strategy["user_id"])
        strategy["api_id"] = str(strategy["api_id"])
        strategies.append(strategy)
    return strategies


async def get_strategy_by_id(db: AsyncIOMotorDatabase, strategy_id: str) -> Optional[Dict]:
    """Get strategy by ID"""
    strategy = await db.strategies.find_one({"_id": ObjectId(strategy_id)})
    if strategy:
        strategy["_id"] = str(strategy["_id"])
        strategy["user_id"] = str(strategy["user_id"])
        strategy["api_id"] = str(strategy["api_id"])
    return strategy


async def update_strategy(db: AsyncIOMotorDatabase, strategy_id: str, update_data: Dict):
    """Update strategy"""
    update_data["updated_at"] = datetime.utcnow()
    await db.strategies.update_one(
        {"_id": ObjectId(strategy_id)},
        {"$set": update_data}
    )


async def delete_strategy(db: AsyncIOMotorDatabase, strategy_id: str):
    """Delete strategy"""
    await db.strategies.delete_one({"_id": ObjectId(strategy_id)})


# ==================== TRADE OPERATIONS ====================

async def create_trade(db: AsyncIOMotorDatabase, trade_data: Dict) -> str:
    """Create new trade"""
    trade_data["user_id"] = ObjectId(trade_data["user_id"])
    trade_data["api_id"] = ObjectId(trade_data["api_id"])
    trade_data["strategy_id"] = ObjectId(trade_data["strategy_id"])
    trade_data["entry_time"] = datetime.utcnow()
    trade_data["status"] = "open"
    trade_data["pnl"] = 0.0
    
    result = await db.trades.insert_one(trade_data)
    return str(result.inserted_id)


async def get_user_trades(db: AsyncIOMotorDatabase, user_id: str, status: str = None) -> List[Dict]:
    """Get all trades for a user"""
    query = {"user_id": ObjectId(user_id)}
    if status:
        query["status"] = status
    
    trades = []
    cursor = db.trades.find(query).sort("entry_time", -1)
    async for trade in cursor:
        trade["_id"] = str(trade["_id"])
        trade["user_id"] = str(trade["user_id"])
        trade["api_id"] = str(trade["api_id"])
        trade["strategy_id"] = str(trade["strategy_id"])
        trades.append(trade)
    return trades


async def get_trade_by_id(db: AsyncIOMotorDatabase, trade_id: str) -> Optional[Dict]:
    """Get trade by ID"""
    trade = await db.trades.find_one({"_id": ObjectId(trade_id)})
    if trade:
        trade["_id"] = str(trade["_id"])
        trade["user_id"] = str(trade["user_id"])
        trade["api_id"] = str(trade["api_id"])
        trade["strategy_id"] = str(trade["strategy_id"])
    return trade


async def update_trade(db: AsyncIOMotorDatabase, trade_id: str, update_data: Dict):
    """Update trade"""
    await db.trades.update_one(
        {"_id": ObjectId(trade_id)},
        {"$set": update_data}
    )


async def close_trade(
    db: AsyncIOMotorDatabase,
    trade_id: str,
    call_exit_price: float,
    put_exit_price: float,
    pnl: float
):
    """Close trade"""
    update_data = {
        "exit_time": datetime.utcnow(),
        "call_exit_price": call_exit_price,
        "put_exit_price": put_exit_price,
        "pnl": pnl,
        "status": "closed"
    }
    await db.trades.update_one(
        {"_id": ObjectId(trade_id)},
        {"$set": update_data}
    )


# ==================== ORDER OPERATIONS ====================

async def create_order(db: AsyncIOMotorDatabase, order_data: Dict) -> str:
    """Create new order"""
    order_data["trade_id"] = ObjectId(order_data["trade_id"])
    order_data["timestamp"] = datetime.utcnow()
    
    result = await db.orders.insert_one(order_data)
    return str(result.inserted_id)


async def get_trade_orders(db: AsyncIOMotorDatabase, trade_id: str) -> List[Dict]:
    """Get all orders for a trade"""
    orders = []
    cursor = db.orders.find({"trade_id": ObjectId(trade_id)})
    async for order in cursor:
        order["_id"] = str(order["_id"])
        order["trade_id"] = str(order["trade_id"])
        orders.append(order)
    return orders


async def update_order_status(db: AsyncIOMotorDatabase, order_id: str, status: str, price: float = None):
    """Update order status"""
    update_data = {"status": status}
    if price:
        update_data["price"] = price
    
    await db.orders.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": update_data}
                      )


async def update_trade_status(db, trade_id: ObjectId, status: str):
    """Update trade status"""
    try:
        result = await db.trades.update_one(
            {'_id': ObjectId(trade_id)},
            {'$set': {'status': status}}
        )
        return result.modified_count > 0
    except Exception as e:
        bot_logger.error(f"Error updating trade status: {e}")
        return False
        

# database/crud.py (APPEND TO END)

# ==================== PAPER TRADING OPERATIONS ====================

async def get_user_trading_mode(db: AsyncIOMotorDatabase, telegram_id: int) -> str:
    """Get user's current trading mode"""
    user = await db.users.find_one({"telegram_id": telegram_id})
    if not user:
        return "live"
    return user.get("trading_mode", "live")


async def set_user_trading_mode(db: AsyncIOMotorDatabase, telegram_id: int, mode: str):
    """Set user's trading mode (live or paper)"""
    await db.users.update_one(
        {"telegram_id": telegram_id},
        {"$set": {"trading_mode": mode}}
    )


async def initialize_paper_trading(db: AsyncIOMotorDatabase, telegram_id: int, initial_balance: float = 10000.0):
    """Initialize paper trading for a user"""
    await db.users.update_one(
        {"telegram_id": telegram_id},
        {
            "$set": {
                "trading_mode": "paper",
                "paper_balance": initial_balance,
                "paper_trades": [],
                "paper_stats": {
                    "total_trades": 0,
                    "winning_trades": 0,
                    "total_pnl": 0.0,
                    "started_at": datetime.utcnow()
                }
            }
        }
    )


async def get_paper_balance(db: AsyncIOMotorDatabase, telegram_id: int) -> float:
    """Get user's paper trading balance"""
    user = await db.users.find_one({"telegram_id": telegram_id})
    if not user:
        return 10000.0
    return user.get("paper_balance", 10000.0)


async def update_paper_balance(db: AsyncIOMotorDatabase, telegram_id: int, new_balance: float):
    """Update paper trading balance"""
    await db.users.update_one(
        {"telegram_id": telegram_id},
        {"$set": {"paper_balance": new_balance}}
    )


async def add_paper_trade(db: AsyncIOMotorDatabase, telegram_id: int, trade: Dict):
    """Add a paper trade to user's history"""
    await db.users.update_one(
        {"telegram_id": telegram_id},
        {
            "$push": {"paper_trades": trade},
            "$inc": {"paper_stats.total_trades": 1}
        }
    )


async def get_paper_trades(db: AsyncIOMotorDatabase, telegram_id: int, status: str = None) -> List[Dict]:
    """Get user's paper trades"""
    user = await db.users.find_one({"telegram_id": telegram_id})
    if not user:
        return []
    
    trades = user.get("paper_trades", [])
    
    # Filter by status if provided
    if status:
        trades = [t for t in trades if t.get("status") == status]
    
    return trades


async def get_open_paper_trades(db: AsyncIOMotorDatabase, telegram_id: int) -> List[Dict]:
    """Get all open paper trades for user"""
    return await get_paper_trades(db, telegram_id, status="open")


async def update_paper_trade(db: AsyncIOMotorDatabase, telegram_id: int, trade_id: str, updates: Dict):
    """Update a specific paper trade"""
    # Get all trades
    user = await db.users.find_one({"telegram_id": telegram_id})
    if not user:
        return False
    
    trades = user.get("paper_trades", [])
    
    # Find and update the trade
    trade_updated = False
    for trade in trades:
        if trade.get("id") == trade_id:
            trade.update(updates)
            trade_updated = True
            break
    
    if trade_updated:
        # Update the entire trades array
        await db.users.update_one(
            {"telegram_id": telegram_id},
            {"$set": {"paper_trades": trades}}
        )
    
    return trade_updated


async def close_paper_trade(
    db: AsyncIOMotorDatabase,
    telegram_id: int,
    trade_id: str,
    exit_price: float,
    pnl: float
):
    """Close a paper trade"""
    # Get user
    user = await db.users.find_one({"telegram_id": telegram_id})
    if not user:
        return False
    
    trades = user.get("paper_trades", [])
    current_balance = user.get("paper_balance", 0.0)
    
    # Find and close the trade
    trade_closed = False
    winning_trade = False
    
    for trade in trades:
        if trade.get("id") == trade_id and trade.get("status") == "open":
            trade["status"] = "closed"
            trade["exit_price"] = exit_price
            trade["exit_timestamp"] = datetime.utcnow()
            trade["pnl"] = pnl
            trade_closed = True
            winning_trade = pnl > 0
            break
    
    if trade_closed:
        # Update balance and stats
        new_balance = current_balance + pnl
        
        update_ops = {
            "$set": {
                "paper_trades": trades,
                "paper_balance": new_balance
            },
            "$inc": {
                "paper_stats.total_pnl": pnl
            }
        }
        
        # Increment winning trades if profitable
        if winning_trade:
            update_ops["$inc"]["paper_stats.winning_trades"] = 1
        
        await db.users.update_one(
            {"telegram_id": telegram_id},
            update_ops
        )
    
    return trade_closed


async def get_paper_stats(db: AsyncIOMotorDatabase, telegram_id: int) -> Dict:
    """Get paper trading statistics"""
    user = await db.users.find_one({"telegram_id": telegram_id})
    if not user:
        return {
            "balance": 10000.0,
            "initial_balance": 10000.0,
            "total_pnl": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "started_at": None
        }
    
    stats = user.get("paper_stats", {})
    balance = user.get("paper_balance", 10000.0)
    initial_balance = 10000.0  # Default starting balance
    
    total_trades = stats.get("total_trades", 0)
    winning_trades = stats.get("winning_trades", 0)
    total_pnl = stats.get("total_pnl", 0.0)
    losing_trades = total_trades - winning_trades
    
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
    
    return {
        "balance": balance,
        "initial_balance": initial_balance,
        "total_pnl": total_pnl,
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": win_rate,
        "started_at": stats.get("started_at")
    }


async def reset_paper_account(db: AsyncIOMotorDatabase, telegram_id: int, initial_balance: float = 10000.0):
    """Reset paper trading account to initial state"""
    await db.users.update_one(
        {"telegram_id": telegram_id},
        {
            "$set": {
                "paper_balance": initial_balance,
                "paper_trades": [],
                "paper_stats": {
                    "total_trades": 0,
                    "winning_trades": 0,
                    "total_pnl": 0.0,
                    "started_at": datetime.utcnow()
                }
            }
        }
    )


async def check_paper_trade_exists(db: AsyncIOMotorDatabase, telegram_id: int, trade_id: str) -> bool:
    """Check if a paper trade exists"""
    user = await db.users.find_one({"telegram_id": telegram_id})
    if not user:
        return False
    
    trades = user.get("paper_trades", [])
    return any(t.get("id") == trade_id for t in trades)


async def get_paper_trade_by_id(db: AsyncIOMotorDatabase, telegram_id: int, trade_id: str) -> Optional[Dict]:
    """Get a specific paper trade by ID"""
    user = await db.users.find_one({"telegram_id": telegram_id})
    if not user:
        return None
    
    trades = user.get("paper_trades", [])
    return next((t for t in trades if t.get("id") == trade_id), None)


# ==================== HYBRID OPERATIONS (Live + Paper) ====================

async def get_all_positions(db: AsyncIOMotorDatabase, telegram_id: int) -> Dict:
    """Get both live and paper positions"""
    user = await db.users.find_one({"telegram_id": telegram_id})
    if not user:
        return {"live": [], "paper": []}
    
    user_id_str = str(user["_id"])
    
    # Get live trades
    live_trades = await get_user_trades(db, user_id_str, status="open")
    
    # Get paper trades
    paper_trades = await get_open_paper_trades(db, telegram_id)
    
    return {
        "live": live_trades,
        "paper": paper_trades
    }


async def get_combined_stats(db: AsyncIOMotorDatabase, telegram_id: int) -> Dict:
    """Get combined statistics for both live and paper trading"""
    user = await db.users.find_one({"telegram_id": telegram_id})
    if not user:
        return {
            "live": {"total_trades": 0, "total_pnl": 0.0},
            "paper": {"total_trades": 0, "total_pnl": 0.0}
        }
    
    user_id_str = str(user["_id"])
    
    # Get live stats
    live_trades = await get_user_trades(db, user_id_str)
    live_total_pnl = sum(t.get("pnl", 0.0) for t in live_trades)
    
    # Get paper stats
    paper_stats = await get_paper_stats(db, telegram_id)
    
    return {
        "live": {
            "total_trades": len(live_trades),
            "total_pnl": live_total_pnl
        },
        "paper": {
            "total_trades": paper_stats["total_trades"],
            "total_pnl": paper_stats["total_pnl"]
        }
    }
            
