from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Telegram Configuration
    telegram_bot_token: str
    webhook_url: str
    
    # MongoDB Configuration
    mongodb_uri: str
    
    # Encryption
    encryption_key: str
    
    # Admin Configuration
    admin_telegram_ids: str
    
    # Environment
    environment: str = "development"
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 10000
    
    # Delta Exchange API
    delta_base_url: str = "https://api.india.delta.exchange"
    
    # Rate Limiting
    api_call_timeout: int = 30
    max_retries: int = 3
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @property
    def admin_ids_list(self) -> List[int]:
        """Convert comma-separated admin IDs to list of integers"""
        return [int(id.strip()) for id in self.admin_telegram_ids.split(",")]
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment.lower() == "production"


# Initialize settings instance
settings = Settings()
