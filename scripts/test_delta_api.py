"""
Test Delta Exchange API connectivity
Usage: python scripts/test_delta_api.py
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from trading.delta_api import DeltaExchangeAPI
from dotenv import load_dotenv

load_dotenv()

async def test_api():
    """Test Delta Exchange API"""
    
    # Get credentials from environment or input
    api_key = input("Enter your Delta Exchange API Key: ").strip()
    api_secret = input("Enter your Delta Exchange API Secret: ").strip()
    
    print("\n" + "="*60)
    print("TESTING DELTA EXCHANGE API")
    print("="*60 + "\n")
    
    async with DeltaExchangeAPI(api_key, api_secret) as api:
        # Test 1: Get wallet balance
        print("Test 1: Fetching wallet balance...")
        balance = await api.get_wallet_balance()
        if 'error' in balance:
            print(f"❌ Error: {balance['error']}")
        else:
            print("✅ Success!")
            if 'result' in balance:
                for wallet in balance['result']:
                    print(f"   {wallet.get('asset_symbol')}: {wallet.get('balance')}")
        
        print()
        
        # Test 2: Get BTC spot price
        print("Test 2: Fetching BTC spot price...")
        spot_price = await api.get_spot_price('BTC')
        if spot_price:
            print(f"✅ BTC Spot Price: ${spot_price}")
        else:
            print("❌ Failed to fetch spot price")
        
        print()
        
        # Test 3: Get products
        print("Test 3: Fetching available products...")
        products = await api.get_products()
        if 'error' in products:
            print(f"❌ Error: {products['error']}")
        else:
            print(f"✅ Found {len(products.get('result', []))} products")
        
        print()
        
        # Test 4: Get positions
        print("Test 4: Fetching open positions...")
        positions = await api.get_positions()
        if 'error' in positions:
            print(f"❌ Error: {positions['error']}")
        else:
            open_pos = [p for p in positions.get('result', []) if int(p.get('size', 0)) != 0]
            print(f"✅ Open positions: {len(open_pos)}")
    
    print("\n" + "="*60)
    print("API TEST COMPLETED")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(test_api())
