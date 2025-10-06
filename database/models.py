from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId


class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic"""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)
    
    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")


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
        json_encoders = {ObjectId: str}


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
        json_encoders = {ObjectId: str}


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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


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
        json_encoders = {ObjectId: str}


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
        json_encoders = {ObjectId: str}
