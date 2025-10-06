from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


class Database:
    """MongoDB database connection manager"""
    
    client: AsyncIOMotorClient = None
    
    @classmethod
    async def connect_db(cls):
        """Establish async connection to MongoDB"""
        try:
            cls.client = AsyncIOMotorClient(settings.mongodb_uri)
            # Test connection
            await cls.client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    @classmethod
    async def close_db(cls):
        """Close MongoDB connection"""
        if cls.client:
            cls.client.close()
            logger.info("MongoDB connection closed")
    
    @classmethod
    def get_database(cls):
        """Get database instance"""
        return cls.client.straddle_trading_bot


def get_sync_database():
    """Get synchronous MongoDB connection (for testing/scripts)"""
    client = MongoClient(settings.mongodb_uri)
    return client.straddle_trading_bot


# Database collections
async def get_users_collection():
    db = Database.get_database()
    return db.users


async def get_api_credentials_collection():
    db = Database.get_database()
    return db.api_credentials


async def get_strategies_collection():
    db = Database.get_database()
    return db.strategies


async def get_trades_collection():
    db = Database.get_database()
    return db.trades


async def get_orders_collection():
    db = Database.get_database()
    return db.orders


async def create_indexes():
    """Create database indexes for optimal performance"""
    db = Database.get_database()
    
    # Users collection indexes
    await db.users.create_index("telegram_id", unique=True)
    
    # API credentials collection indexes
    await db.api_credentials.create_index([("user_id", 1), ("is_active", 1)])
    
    # Strategies collection indexes
    await db.strategies.create_index([("user_id", 1), ("name", 1)])
    
    # Trades collection indexes
    await db.trades.create_index([("user_id", 1), ("status", 1)])
    await db.trades.create_index("entry_time")
    
    # Orders collection indexes
    await db.orders.create_index("trade_id")
    await db.orders.create_index("order_id_delta")
    
    logger.info("Database indexes created successfully")
  
