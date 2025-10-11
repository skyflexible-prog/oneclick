import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # https://your-app.onrender.com

# Database Configuration
MONGODB_URI = os.getenv('MONGODB_URI')
DB_NAME = 'straddle_bot'

# Encryption Configuration
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')

# Server Configuration
HOST = '0.0.0.0'
PORT = 10000

# Delta Exchange Configuration
DELTA_BASE_URL = 'https://api.india.delta.exchange'

# Admin Configuration
ADMIN_TELEGRAM_IDS = [int(id.strip()) for id in os.getenv('ADMIN_TELEGRAM_IDS', '').split(',') if id.strip()]

# Trading Configuration
MAX_RETRIES = 3
API_TIMEOUT = 10
OPTION_CHAIN_CACHE_SECONDS = 30

# Risk Management
DEFAULT_MAX_LOSS_PER_TRADE_PCT = 5.0
DEFAULT_DAILY_LOSS_LIMIT_PCT = 10.0
