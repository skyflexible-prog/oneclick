import logging
from flask import Flask, request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from config.settings import TELEGRAM_BOT_TOKEN, WEBHOOK_URL, HOST, PORT
from config.database import db_instance
from bot.handlers import (
    start_command, help_command, add_api_start, create_strategy_start,
    list_strategies_command, list_apis_command, check_balance_command,
    show_positions_command, trade_history_command, handle_text_input,
    handle_callback_query
)
from utils.logger import setup_logger
import asyncio

# Setup logging
logger = setup_logger()

# Initialize Flask app for webhook
app = Flask(__name__)

# Initialize Telegram bot application
telegram_app = None

def create_telegram_app():
    """Create and configure Telegram application"""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("addapi", add_api_start))
    application.add_handler(CommandHandler("createstrategy", create_strategy_start))
    application.add_handler(CommandHandler("liststrategy", list_strategies_command))
    application.add_handler(CommandHandler("listapis", list_apis_command))
    application.add_handler(CommandHandler("balance", check_balance_command))
    application.add_handler(CommandHandler("positions", show_positions_command))
    application.add_handler(CommandHandler("history", trade_history_command))
    
    # Message handler for text input
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    
    # Callback query handler for inline buttons
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    return application

@app.route('/webhook', methods=['POST'])
async def webhook():
    """Handle incoming webhook updates from Telegram"""
    try:
        json_data = request.get_json(force=True)
        update = Update.de_json(json_data, telegram_app.bot)
        await telegram_app.process_update(update)
        return Response(status=200)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return Response(status=500)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for UptimeRobot"""
    try:
        # Check database connection
        db = db_instance.get_db()
        db.command('ping')
        return {'status': 'healthy', 'service': 'telegram-bot'}, 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {'status': 'unhealthy', 'error': str(e)}, 500

@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return {'message': 'Telegram Straddle Bot is running', 'status': 'active'}, 200

async def setup_webhook():
    """Setup webhook with Telegram"""
    global telegram_app
    
    telegram_app = create_telegram_app()
    await telegram_app.initialize()
    await telegram_app.bot.delete_webhook(drop_pending_updates=True)
    
    webhook_url = f"{WEBHOOK_URL}/webhook"
    success = await telegram_app.bot.set_webhook(
        url=webhook_url,
        allowed_updates=["message", "callback_query"]
    )
    
    if success:
        logger.info(f"Webhook set successfully: {webhook_url}")
    else:
        logger.error("Failed to set webhook")
    
    await telegram_app.start()

def run_flask():
    """Run Flask server"""
    logger.info(f"Starting Flask server on {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=False)

if __name__ == '__main__':
    try:
        # Connect to database
        logger.info("Connecting to MongoDB...")
        db_instance.connect()
        
        # Setup webhook
        logger.info("Setting up Telegram webhook...")
        loop = asyncio.get_event_loop()
        loop.run_until_complete(setup_webhook())
        
        # Run Flask server
        run_flask()
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        db_instance.close()
    except Exception as e:
        logger.error(f"Application error: {e}")
        db_instance.close()
    
