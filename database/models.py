# database/models.py

from pydantic import BaseModel, Field
from typing import Dict, Optional
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


async def create_strangle_preset(
    db,
    user_id: int,
    api_id: str,
    preset_name: str,
    direction: str,
    strike_method: str,
    strike_type: Optional[str],
    strike_value: float,
    sl_trigger_method: str,
    sl_trigger_value: float,
    sl_limit_method: str,
    sl_limit_value: float,
    asset: str = "BTC",
    expiry_type: str = "daily",
    lot_size: int = 1
) -> str:
    """
    Create a strangle strategy preset
    
    Args:
        direction: "long" or "short"
        strike_method: "percentage" or "atm_offset"
        strike_type: "otm" or "itm" (only for percentage method)
        strike_value: Percentage (1-50) or offset (1-10)
        sl_trigger_method: "percentage", "numerical", or "multiple"
        sl_limit_method: "percentage", "numerical", or "multiple"
    
    Returns:
        Preset ID
    """
    preset = {
        "preset_name": preset_name,
        "user_id": user_id,
        "api_id": api_id,
        "strategy_type": "strangle",
        "direction": direction,
        "strike_method": strike_method,
        "strike_type": strike_type,
        "strike_value": strike_value,
        "sl_trigger_method": sl_trigger_method,
        "sl_trigger_value": sl_trigger_value,
        "sl_limit_method": sl_limit_method,
        "sl_limit_value": sl_limit_value,
        "asset": asset,
        "expiry_type": expiry_type,
        "lot_size": lot_size,
        "created_at": datetime.utcnow(),
        "is_active": True
    }
    
    result = await db.strangle_presets.insert_one(preset)
    return str(result.inserted_id)


async def get_strangle_presets(db, user_id: int):
    """Get all strangle presets for a user"""
    presets = await db.strangle_presets.find({
        "user_id": user_id,
        "is_active": True
    }).to_list(None)
    return presets


async def get_strangle_preset_by_id(db, preset_id: str):
    """Get a specific strangle preset by ID"""
    return await db.strangle_presets.find_one({"_id": ObjectId(preset_id)})


async def delete_strangle_preset(db, preset_id: str):
    """Delete a strangle preset"""
    await db.strangle_presets.update_one(
        {"_id": ObjectId(preset_id)},
        {"$set": {"is_active": False}}
    )
