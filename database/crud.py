from typing import Optional, List, Dict, Any
from bson import ObjectId
from config.database import db_instance
import logging

logger = logging.getLogger(__name__)

class UserCRUD:
    def __init__(self):
        self.collection = db_instance.get_db().users

    def create_user(self, telegram_id: int, username: str, first_name: str) -> Optional[str]:
        try:
            from database.models import UserModel
            user_data = UserModel.create(telegram_id, username, first_name)
            result = self.collection.insert_one(user_data)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        return self.collection.find_one({'telegram_id': telegram_id})

    def get_or_create_user(self, telegram_id: int, username: str, first_name: str) -> Dict:
        user = self.get_user_by_telegram_id(telegram_id)
        if not user:
            user_id = self.create_user(telegram_id, username, first_name)
            user = self.collection.find_one({'_id': ObjectId(user_id)})
        return user

class APICredentialCRUD:
    def __init__(self):
        self.collection = db_instance.get_db().api_credentials

    def create_credential(self, user_id: str, nickname: str, 
                         api_key_encrypted: bytes, api_secret_encrypted: bytes) -> Optional[str]:
        try:
            from database.models import APICredentialModel
            cred_data = APICredentialModel.create(user_id, nickname, api_key_encrypted, api_secret_encrypted)
            result = self.collection.insert_one(cred_data)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error creating API credential: {e}")
            return None

    def get_user_credentials(self, user_id: str) -> List[Dict]:
        return list(self.collection.find({'user_id': user_id}))

    def get_active_credential(self, user_id: str) -> Optional[Dict]:
        return self.collection.find_one({'user_id': user_id, 'is_active': True})

    def set_active_credential(self, user_id: str, api_id: str) -> bool:
        try:
            # Deactivate all
            self.collection.update_many({'user_id': user_id}, {'$set': {'is_active': False}})
            # Activate selected
            self.collection.update_one({'_id': ObjectId(api_id)}, {'$set': {'is_active': True}})
            return True
        except Exception as e:
            logger.error(f"Error setting active credential: {e}")
            return False

class StrategyCRUD:
    def __init__(self):
        self.collection = db_instance.get_db().strategies

    def create_strategy(self, user_id: str, api_id: str, name: str, 
                       strategy_type: str, lot_size: int, direction: str, **kwargs) -> Optional[str]:
        try:
            from database.models import StrategyModel
            strategy_data = StrategyModel.create(user_id, api_id, name, strategy_type, 
                                                lot_size, direction, **kwargs)
            result = self.collection.insert_one(strategy_data)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error creating strategy: {e}")
            return None

    def get_user_strategies(self, user_id: str) -> List[Dict]:
        return list(self.collection.find({'user_id': user_id}))

    def get_strategy_by_id(self, strategy_id: str) -> Optional[Dict]:
        try:
            return self.collection.find_one({'_id': ObjectId(strategy_id)})
        except:
            return None

    def delete_strategy(self, strategy_id: str) -> bool:
        try:
            result = self.collection.delete_one({'_id': ObjectId(strategy_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting strategy: {e}")
            return False

class TradeCRUD:
    def __init__(self):
        self.collection = db_instance.get_db().trades

    def create_trade(self, user_id: str, api_id: str, strategy_id: str, 
                    strategy_type: str, call_symbol: str, put_symbol: str, 
                    strike: float, **kwargs) -> Optional[str]:
        try:
            from database.models import TradeModel
            trade_data = TradeModel.create(user_id, api_id, strategy_id, strategy_type,
                                          call_symbol, put_symbol, strike, **kwargs)
            result = self.collection.insert_one(trade_data)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error creating trade: {e}")
            return None

    def get_active_trades(self, user_id: str) -> List[Dict]:
        return list(self.collection.find({'user_id': user_id, 'status': 'active'}))

    def get_trade_by_id(self, trade_id: str) -> Optional[Dict]:
        try:
            return self.collection.find_one({'_id': ObjectId(trade_id)})
        except:
            return None

    def update_trade_exit(self, trade_id: str, call_exit_price: float, 
                         put_exit_price: float, pnl: float) -> bool:
        try:
            from datetime import datetime
            self.collection.update_one(
                {'_id': ObjectId(trade_id)},
                {'$set': {
                    'call_exit_price': call_exit_price,
                    'put_exit_price': put_exit_price,
                    'exit_time': datetime.utcnow(),
                    'pnl': pnl,
                    'status': 'closed'
                }}
            )
            return True
        except Exception as e:
            logger.error(f"Error updating trade exit: {e}")
            return False

    def get_trade_history(self, user_id: str, limit: int = 20) -> List[Dict]:
        return list(self.collection.find({'user_id': user_id})
                   .sort('entry_time', -1).limit(limit))
        
