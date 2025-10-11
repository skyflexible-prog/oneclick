from pymongo import MongoClient
from config.settings import MONGODB_URI, DB_NAME
import logging

logger = logging.getLogger(__name__)

class Database:
    _instance = None
    _client = None
    _db = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance

    def connect(self):
        try:
            self._client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            self._db = self._client[DB_NAME]
            self._client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")
            self._create_indexes()
            return self._db
        except Exception as e:
            logger.error(f"MongoDB connection error: {e}")
            raise

    def _create_indexes(self):
        """Create database indexes for performance"""
        self._db.users.create_index("telegram_id", unique=True)
        self._db.api_credentials.create_index([("user_id", 1), ("is_active", 1)])
        self._db.strategies.create_index("user_id")
        self._db.trades.create_index([("user_id", 1), ("status", 1)])
        logger.info("Database indexes created")

    def get_db(self):
        if self._db is None:
            return self.connect()
        return self._db

    def close(self):
        if self._client:
            self._client.close()
            logger.info("MongoDB connection closed")

db_instance = Database()
