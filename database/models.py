# database/models.py

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId


class PyObjectId(str):
    """Custom ObjectId type for Pydantic v2"""
    
    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        from pydantic_core import core_schema
        
        return core_schema.union_schema([
            core_schema.is_instance_schema(ObjectId),
            core_schema.chain_schema([
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(cls.validate),
            ]),
        ],
        serialization=core_schema.plain_serializer_function_ser_schema(
            lambda x: str(x)
        ))
    
    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        raise ValueError("Invalid ObjectId")


class UserModel(BaseModel):
    """User database model"""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    telegram_id: int
    username: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class APICredentialModel(BaseModel):
    """API credential database model"""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id: PyObjectId
    nickname: str
    api_key_encrypted: str
    api_secret_encrypted: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class StrategyModel(BaseModel):
    """Trading strategy database model"""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id: PyObjectId
    api_id: PyObjectId
    name: str
    lot_size: int
    direction: str  # "long" or "short"
    stop_loss_pct: float
    target_pct: Optional[float] = None
    expiry_type: str  # "daily", "weekly", "monthly"
    strike_offset: int = 0
    max_capital: float
    trailing_sl: bool = False
    underlying: str = "BTC"  # "BTC" or "ETH"
    
    # Automatic order fields
    use_stop_loss_order: bool = False
    sl_trigger_pct: Optional[float] = None
    sl_limit_pct: Optional[float] = None
    
    use_target_order: bool = False
    target_trigger_pct: Optional[float] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class TradeModel(BaseModel):
    """Trade database model"""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id: PyObjectId
    api_id: PyObjectId
    strategy_id: PyObjectId
    call_symbol: str
    put_symbol: str
    strike: float
    spot_price: float
    entry_time: datetime = Field(default_factory=datetime.utcnow)
    exit_time: Optional[datetime] = None
    call_entry_price: float
    put_entry_price: float
    call_exit_price: Optional[float] = None
    put_exit_price: Optional[float] = None
    lot_size: int
    pnl: float = 0.0
    status: str = "open"  # "open", "closed", "partial"
    fees: float = 0.0
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class OrderModel(BaseModel):
    """Order database model"""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    trade_id: PyObjectId
    order_id_delta: str
    symbol: str
    side: str  # "buy" or "sell"
    order_type: str  # "market", "limit", "stop"
    quantity: int
    price: float
    status: str = "pending"  # "pending", "filled", "cancelled", "rejected"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        
