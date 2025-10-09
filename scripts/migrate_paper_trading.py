# scripts/migrate_paper_trading.py

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import settings
from datetime import datetime

async def migrate_users_for_paper_trading():
    """Add paper trading fields to existing users"""
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client[settings.database_name]
    
    print("🔄 Starting paper trading migration...")
    
    # Get all users
    users = await db.users.find({}).to_list(None)
    
    print(f"📊 Found {len(users)} users to migrate")
    
    # Add paper trading fields to each user
    for user in users:
        telegram_id = user['telegram_id']
        
        # Check if already has paper trading fields
        if 'trading_mode' not in user:
            await db.users.update_one(
                {"telegram_id": telegram_id},
                {
                    "$set": {
                        "trading_mode": "live",
                        "paper_balance": 10000.0,
                        "paper_trades": [],
                        "paper_stats": {
                            "total_trades": 0,
                            "winning_trades": 0,
                            "total_pnl": 0.0,
                            "started_at": None
                        }
                    }
                }
            )
            print(f"✅ Migrated user {telegram_id}")
        else:
            print(f"⏭️  User {telegram_id} already migrated")
    
    print("✅ Migration complete!")
    
    # Close connection
    client.close()

if __name__ == "__main__":
    asyncio.run(migrate_users_for_paper_trading())
  
