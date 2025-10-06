"""
Setup MongoDB collections and indexes
Run this after deploying for the first time
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.database import Database, create_indexes
from dotenv import load_dotenv

load_dotenv()

async def setup_database():
    """Setup MongoDB database"""
    
    print("\n" + "="*60)
    print("MONGODB SETUP")
    print("="*60 + "\n")
    
    # Connect to database
    print("Connecting to MongoDB...")
    await Database.connect_db()
    print("✅ Connected successfully!\n")
    
    # Create indexes
    print("Creating indexes...")
    await create_indexes()
    print("✅ Indexes created!\n")
    
    # List collections
    db = Database.get_database()
    collections = await db.list_collection_names()
    print(f"Collections in database: {', '.join(collections) if collections else 'None'}\n")
    
    # Close connection
    await Database.close_db()
    print("✅ Setup completed!\n")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(setup_database())
  
