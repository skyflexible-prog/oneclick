import logging
import os
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime


def setup_logger(name: str, log_file: str, level=logging.INFO):
    """Setup logger with file and console handlers"""
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # Create formatters
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler with daily rotation
    file_handler = TimedRotatingFileHandler(
        f"logs/{log_file}",
        when="midnight",
        interval=1,
        backupCount=30
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


# Initialize loggers
bot_logger = setup_logger("bot", "bot.log")
trade_logger = setup_logger("trades", "trades.log")
api_logger = setup_logger("api", "api.log")
error_logger = setup_logger("errors", "errors.log", level=logging.ERROR)
