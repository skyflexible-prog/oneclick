# database/crud.py

from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from typing import List, Optional, Dict
from datetime import datetime
from database.models import (
    UserModel, APICredentialModel, StrategyModel, 
    TradeModel, OrderModel
)
from config.database import Database
from utils.logger import bot_logger


# ==================== INDEX CREATION ====================

async def create_indexes():
    """Create database indexes for performance optimization"""
    try:
        db = Database.get_database()
        
        # Users indexes
        await db.users.create_index([("telegram_id", 1)], unique=True)
        await db.users.create_index([("created_at", -1)])
        
        # API credentials indexes
        await db.api_credentials.create_index([("user_id", 1)])
        await db.api_credentials.create_index([("is_active", 1)])
        await db.api_credentials.create_index([
            ("user_id", 1),
            ("is_active", 1)
        ])
        
        # Strategies indexes
        await db.strategies.create_index([("user_id", 1)])
        await db.strategies.create_index([("strategy_name", 1)])
        await db.strategies.create_index([
            ("user_id", 1),
            ("created_at", -1)
        ])
        
        # Trades indexes
        await db.trades.create_index([("user_id", 1)])
        await db.trades.create_index([("status", 1)])
        await db.trades.create_index([("created_at", -1)])
        await db.trades.create_index([
            ("user_id", 1),
            ("status", 1)
        ])
        
        # Orders indexes
        await db.orders.create_index([("trade_id", 1)])
        await db.orders.create_index([("timestamp", -1)])
        
        bot_logger.info("✅ Database indexes created successfully")
    except Exception as e:
        bot_logger.error(f"Error creating database indexes: {e}")


# database/crud.py

async def create_order_state_indexes():
    """Create indexes for order state tracking (OPTIMIZED)"""
    try:
        db = Database.get_database()
        
        # Compound index for order lookup
        await db.order_states.create_index([
            ("user_id", 1),
            ("api_id", 1),
            ("order_id", 1)
        ], unique=True)
        
        # Index for state queries
        await db.order_states.create_index([
            ("state", 1),
            ("updated_at", -1)
        ])
        
        # ✅ TTL INDEX: Auto-delete filled orders after 7 DAYS
        await db.order_states.create_index(
            [("filled_at", 1)],
            expireAfterSeconds=604800  # 7 days (was 30 days)
        )
        
        # ✅ ADDITIONAL: Delete old pending orders after 30 days
        await db.order_states.create_index(
            [("updated_at", 1)],
            expireAfterSeconds=2592000  # 30 days
        )
        
        bot_logger.info("✅ Order state indexes created (optimized)")
    except Exception as e:
        bot_logger.error(f"Error creating order state indexes: {e}")


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


async def update_trade_status(db: AsyncIOMotorDatabase, trade_id: ObjectId, status: str):
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
 
