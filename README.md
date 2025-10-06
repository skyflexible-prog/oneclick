# Telegram ATM Straddle Trading Bot

A modular Python Telegram bot for executing ATM straddle options trades on Delta Exchange India with single-click execution and multi-API support.

## Features

- 🤖 Single-click trade execution
- 💼 Multi-API credential management
- 📊 Real-time position monitoring
- 🎯 Preset strategy configurations
- 🔐 Encrypted API credential storage
- 📈 ATM straddle calculation (BTC, ETH)
- ⚡ FastAPI webhook integration
- 🗄️ MongoDB database

## Setup Instructions

### 1. Clone Repository
git clone https://github.com/yourusername/telegram-straddle-bot.git
cd telegram-straddle-bot

text

### 2. Install Dependencies
python -m venv venv
source venv/bin/activate # On Windows: venv\Scripts\activate
pip install -r requirements.txt

text

### 3. Configure Environment Variables
cp .env.example .env

Edit .env with your actual values
text

### 4. Generate Encryption Key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

text

### 5. Deploy to Render.com
- Push code to GitHub
- Connect repository to Render.com
- Add environment variables in Render dashboard
- Deploy!
## Commands

- `/start` - Welcome message
- `/addapi` - Add Delta Exchange API credentials
- `/listapis` - View all registered APIs
- `/createstrategy` - Configure new trade preset
- `/trade` - Execute trades with single click
- `/positions` - View active positions
- `/balance` - Check wallet balance
- `/history` - Trade history

## Project Structure

telegram-straddle-bot/
├── main.py # Entry point
├── config/ # Configuration
├── bot/ # Telegram bot logic
├── trading/ # Trading operations
├── database/ # Database models & CRUD
└── utils/ # Utilities
