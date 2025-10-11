# main.py

from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters
)
from contextlib import asynccontextmanager
from http import HTTPStatus
import uvicorn
from datetime import datetime

from config.settings import settings
from config.database import Database
from database.crud import create_indexes, create_order_state_indexes  # ✅ UPDATED IMPORT
from bot.handlers import (
    start_command,
    help_command,
    balance_command,
    show_balance,
    button_callback,
    add_api_start,
    receive_api_nickname,
    receive_api_key,
    receive_api_secret,
    list_apis,
    view_api_details,
    activate_api,
    delete_api,
    create_strategy_start,
    receive_strategy_name,
    receive_underlying,
    receive_direction,
    receive_expiry,
    receive_lot_size,
    receive_stop_loss,
    receive_sl_order_choice,
    receive_sl_trigger,
    receive_sl_limit,
    receive_target,
    receive_target_order_choice,
    receive_max_capital,
    receive_strike_offset,
    list_strategies,
    view_strategy_details,
    delete_strategy,
    trade_menu,
    select_api_for_trade,
    execute_trade_preview,
    confirm_trade_execution,
    show_positions,
    view_position_details,
    close_position_confirm,
    close_position_execute,
    show_history,
    cancel_conversation,
    error_handler,
    AWAITING_API_NICKNAME,
    AWAITING_API_KEY,
    AWAITING_API_SECRET,
    AWAITING_STRATEGY_NAME,
    AWAITING_LOT_SIZE,
    AWAITING_STOP_LOSS,
    AWAITING_SL_ORDER_CHOICE,
    AWAITING_SL_TRIGGER,
    AWAITING_SL_LIMIT,
    AWAITING_TARGET,
    AWAITING_TARGET_ORDER_CHOICE,
    AWAITING_MAX_CAPITAL,
    AWAITING_STRIKE_OFFSET,
    SELECTING_API,
    SELECTING_STRATEGY,
    CONFIRMING_TRADE
)

# ✅ ORDER MANAGEMENT IMPORTS
from bot.order_management import (
    show_order_management_menu,
    show_orders_for_api,
    view_order_details,
    show_edit_order_menu,
    edit_trigger_price_start,
    edit_limit_price_start,
    receive_trigger_price,
    receive_limit_price,
    sl_to_cost,
    cancel_order,
    SELECTING_ORDER_API,
    VIEWING_ORDERS,
    AWAITING_TRIGGER_PRICE,
    AWAITING_LIMIT_PRICE,
)

from bot.strangle_strategy import strangle_conv_handler
from utils.logger import bot_logger, trade_logger

# Initialize Telegram Bot Application
ptb = (
    Application.builder()
    .updater(None)
    .token(settings.telegram_bot_token)
    .read_timeout(7)
    .get_updates_read_timeout(42)
    .build()
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Application lifespan manager"""
    bot_logger.info("Starting application...")
    await Database.connect_db()
    
    try:
        await create_indexes()
        await create_order_state_indexes()  # ✅ CREATE ORDER STATE INDEXES
        bot_logger.info("✅ Database indexes created/verified")
    except Exception as e:
        bot_logger.error(f"Error creating indexes: {e}")
    
    webhook_url = f"{settings.webhook_url}"
    await ptb.bot.setWebhook(webhook_url)
    bot_logger.info(f"Webhook set to: {webhook_url}")
    
    register_handlers()
    
    async with ptb:
        await ptb.start()
        bot_logger.info("Bot started successfully!")
        yield
    
    bot_logger.info("Shutting down...")
    await ptb.stop()
    await Database.close_db()


app = FastAPI(lifespan=lifespan)


def register_handlers():
    """Register all bot handlers - ORDER MATTERS!"""
    
    # Command handlers
    ptb.add_handler(CommandHandler("start", start_command))
    ptb.add_handler(CommandHandler("help", help_command))
    ptb.add_handler(CommandHandler("balance", balance_command))
    
    # API Management Conversation Handler
    api_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_api_start, pattern="^add_api$")],
        states={
            AWAITING_API_NICKNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_api_nickname)],
            AWAITING_API_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_api_key)],
            AWAITING_API_SECRET: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_api_secret)]
        },
        fallbacks=[CallbackQueryHandler(cancel_conversation, pattern="^main_menu$")],
        allow_reentry=True
    )
    ptb.add_handler(api_conv_handler)
    
    # Strategy Creation Conversation Handler
    strategy_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(create_strategy_start, pattern="^create_strategy$")],
        states={
            AWAITING_STRATEGY_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_strategy_name),
                CallbackQueryHandler(receive_underlying, pattern="^underlying_"),
                CallbackQueryHandler(receive_direction, pattern="^direction_"),
                CallbackQueryHandler(receive_expiry, pattern="^expiry_")
            ],
            AWAITING_LOT_SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_lot_size)],
            AWAITING_STOP_LOSS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_stop_loss)],
            AWAITING_SL_ORDER_CHOICE: [CallbackQueryHandler(receive_sl_order_choice, pattern="^sl_order_")],
            AWAITING_SL_TRIGGER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_sl_trigger)],
            AWAITING_SL_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_sl_limit)],
            AWAITING_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_target)],
            AWAITING_TARGET_ORDER_CHOICE: [CallbackQueryHandler(receive_target_order_choice, pattern="^target_order_")],
            AWAITING_MAX_CAPITAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_max_capital)],
            AWAITING_STRIKE_OFFSET: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_strike_offset)]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_conversation, pattern="^cancel$"),
            CommandHandler("cancel", cancel_conversation)
        ],
        allow_reentry=True
    )
    ptb.add_handler(strategy_conv_handler)
    
    # Trade Conversation Handler
    trade_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(trade_menu, pattern="^trade$")],
        states={
            SELECTING_API: [CallbackQueryHandler(select_api_for_trade, pattern="^trade_api_")],
            SELECTING_STRATEGY: [CallbackQueryHandler(execute_trade_preview, pattern="^execute_")],
            CONFIRMING_TRADE: [CallbackQueryHandler(confirm_trade_execution, pattern="^confirm_trade")],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_conversation, pattern="^main_menu$"),
            CommandHandler("cancel", cancel_conversation)
        ],
        per_message=False,
        allow_reentry=True
    )
    ptb.add_handler(trade_conv_handler)
    
    # ==================== ORDER MANAGEMENT CONVERSATION HANDLER ====================
    order_management_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(show_order_management_menu, pattern="^orders_menu$")
        ],
        states={
            SELECTING_ORDER_API: [
                CallbackQueryHandler(show_orders_for_api, pattern="^orders_api_")
            ],
            VIEWING_ORDERS: [
                CallbackQueryHandler(view_order_details, pattern="^view_order_"),
                CallbackQueryHandler(show_edit_order_menu, pattern="^edit_order_"),
                CallbackQueryHandler(edit_trigger_price_start, pattern="^edit_trigger_"),
                CallbackQueryHandler(edit_limit_price_start, pattern="^edit_limit_"),
                CallbackQueryHandler(sl_to_cost, pattern="^sl_to_cost_"),
                CallbackQueryHandler(cancel_order, pattern="^cancel_order_"),
                CallbackQueryHandler(show_orders_for_api, pattern="^orders_api_"),
            ],
            AWAITING_TRIGGER_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_trigger_price)
            ],
            AWAITING_LIMIT_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_limit_price)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_conversation, pattern="^main_menu$"),
            CallbackQueryHandler(show_order_management_menu, pattern="^orders_menu$"),
            CommandHandler("cancel", cancel_conversation)
        ],
        per_message=False,
        allow_reentry=True
    )
    ptb.add_handler(order_management_conv)
    
    # SPECIFIC callback handlers BEFORE generic ones
    ptb.add_handler(CallbackQueryHandler(list_apis, pattern="^list_apis$"))
    ptb.add_handler(CallbackQueryHandler(view_api_details, pattern="^view_api_"))
    ptb.add_handler(CallbackQueryHandler(activate_api, pattern="^activate_api_"))
    ptb.add_handler(CallbackQueryHandler(delete_api, pattern="^delete_api_"))
    
    ptb.add_handler(CallbackQueryHandler(list_strategies, pattern="^list_strategies$"))
    ptb.add_handler(CallbackQueryHandler(list_strategies, pattern="^strategies$"))
    ptb.add_handler(CallbackQueryHandler(view_strategy_details, pattern="^view_strategy_"))
    ptb.add_handler(CallbackQueryHandler(delete_strategy, pattern="^delete_strategy_"))
    
    ptb.add_handler(CallbackQueryHandler(show_positions, pattern="^positions$"))
    ptb.add_handler(CallbackQueryHandler(view_position_details, pattern="^view_position_"))
    ptb.add_handler(CallbackQueryHandler(close_position_confirm, pattern="^close_position_"))
    ptb.add_handler(CallbackQueryHandler(close_position_execute, pattern="^confirm_close_"))
    
    ptb.add_handler(CallbackQueryHandler(show_balance, pattern="^balance$"))
    ptb.add_handler(CallbackQueryHandler(show_history, pattern="^history$"))
    
    # Generic callback handlers (LAST)
    ptb.add_handler(CallbackQueryHandler(button_callback))
    
    ptb.add_error_handler(error_handler)
    
    bot_logger.info("All handlers registered successfully")


@app.post("/webhook")
async def process_update(request: Request):
    """Process incoming Telegram updates via webhook"""
    try:
        req = await request.json()
        update = Update.de_json(req, ptb.bot)
        await ptb.process_update(update)
        return Response(status_code=HTTPStatus.OK)
    except Exception as e:
        bot_logger.error(f"Error processing update: {e}")
        return Response(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "status": "running",
        "bot": "ATM Straddle Trading Bot",
        "version": "1.0.0",
        "features": [
            "Order Management",
            "Order Fill Notifications",
            "SL to Cost",
            "Strategy Execution"
        ]
    }


@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check(request: Request):
    """Health check endpoint supporting both GET and HEAD requests"""
    if request.method == "HEAD":
        return Response(status_code=200)
    
    return {
        "status": "ok",
        "bot": "healthy",
        "database": "connected" if Database.client else "disconnected"
    }


@app.get("/healthz")
async def detailed_health():
    """Detailed health check with database and bot status"""
    try:
        db_status = "connected" if Database.client else "disconnected"
        bot_status = "running" if ptb else "not_initialized"
        
        return {
            "status": "healthy",
            "bot": bot_status,
            "database": db_status,
            "timestamp": datetime.utcnow().isoformat(),
            "service": "telegram-straddle-bot"
        }
    except Exception as e:
        bot_logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@app.get("/stats")
async def stats():
    """Basic statistics endpoint"""
    try:
        db = Database.get_database()
        user_count = await db.users.count_documents({})
        strategy_count = await db.strategies.count_documents({})
        trade_count = await db.trades.count_documents({})
        open_positions = await db.trades.count_documents({"status": "open"})
        
        # ✅ ADD ORDER NOTIFICATION STATS
        pending_orders = await db.order_states.count_documents({"state": "pending"})
        filled_orders = await db.order_states.count_documents({"state": "filled"})
        
        return {
            "users": user_count,
            "strategies": strategy_count,
            "total_trades": trade_count,
            "open_positions": open_positions,
            "pending_orders": pending_orders,
            "filled_orders_tracked": filled_orders
        }
    except Exception as e:
        bot_logger.error(f"Error fetching stats: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    bot_logger.info(f"Starting bot on {settings.host}:{settings.port}")
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level="info"
    )
    
