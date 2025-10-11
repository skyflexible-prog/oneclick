# trading/strangle_executor.py

from typing import Dict, Tuple, Optional
from trading.delta_api import DeltaExchangeAPI
from trading.strangle_calculator import StrangleCalculator
from utils.logger import bot_logger
import asyncio


class StrangleExecutor:
    """Execute strangle strategy trades"""
    
    @staticmethod
    async def execute_strangle(
        api_key: str,
        api_secret: str,
        preset: Dict
    ) -> Dict:
        """
        Execute a strangle strategy based on preset configuration
        
        Args:
            api_key: Delta Exchange API key
            api_secret: Delta Exchange API secret
            preset: Strangle preset configuration
        
        Returns:
            Execution result with order details
        """
        try:
            async with DeltaExchangeAPI(api_key, api_secret) as delta_api:
                # Step 1: Get current spot price
                spot_price = await delta_api.get_spot_price(preset['asset'])
                bot_logger.info(f"Current {preset['asset']} spot price: ${spot_price:.2f}")
                
                # Step 2: Calculate target strikes
                call_strike, put_strike = StrangleCalculator.calculate_strikes(
                    spot_price=spot_price,
                    method=preset['strike_method'],
                    strike_type=preset.get('strike_type'),
                    value=preset['strike_value'],
                    asset=preset['asset']
                )
                
                # Step 3: Get option chain
                option_chain = await delta_api.get_option_chain(
                    asset=preset['asset'],
                    expiry_type=preset['expiry_type']
                )
                
                if not option_chain:
                    raise Exception("Failed to fetch option chain")
                
                # Step 4: Get expiry date
                from trading.trade_executor import TradeExecutor
                expiry = TradeExecutor.get_target_expiry(
                    option_chain,
                    preset['expiry_type']
                )
                
                if not expiry:
                    raise Exception("No suitable expiry found")
                
                # Step 5: Find nearest strikes
                call_symbol, put_symbol = StrangleCalculator.find_nearest_strikes(
                    target_call=call_strike,
                    target_put=put_strike,
                    option_chain=option_chain,
                    expiry=expiry
                )
                
                if not call_symbol or not put_symbol:
                    raise Exception("Could not find suitable strikes")
                
                # Step 6: Get current premiums
                call_ticker = await delta_api.get_ticker(call_symbol)
                put_ticker = await delta_api.get_ticker(put_symbol)
                
                call_premium = float(call_ticker.get('mark_price', 0))
                put_premium = float(put_ticker.get('mark_price', 0))
                
                total_premium = call_premium + put_premium
                
                bot_logger.info(f"Premiums:")
                bot_logger.info(f"  Call ({call_symbol}): ${call_premium:.2f}")
                bot_logger.info(f"  Put ({put_symbol}): ${put_premium:.2f}")
                bot_logger.info(f"  Total: ${total_premium:.2f}")
                
                # Step 7: Calculate stop-loss
                sl_trigger, sl_limit = StrangleCalculator.calculate_stop_loss(
                    entry_price=total_premium,
                    trigger_method=preset['sl_trigger_method'],
                    trigger_value=preset['sl_trigger_value'],
                    limit_method=preset['sl_limit_method'],
                    limit_value=preset['sl_limit_value'],
                    direction=preset['direction']
                )
                
                # Step 8: Execute orders
                direction = preset['direction']
                lot_size = preset['lot_size']
                
                if direction == "long":
                    # Buy strangle: Buy call + Buy put
                    call_side = "buy"
                    put_side = "buy"
                else:
                    # Short strangle: Sell call + Sell put
                    call_side = "sell"
                    put_side = "sell"
                
                # Place call order
                call_order = await delta_api.place_order(
                    symbol=call_symbol,
                    side=call_side,
                    order_type="market_order",
                    size=lot_size
                )
                
                bot_logger.info(f"Call order placed: {call_order.get('id')}")
                
                # Place put order
                put_order = await delta_api.place_order(
                    symbol=put_symbol,
                    side=put_side,
                    order_type="market_order",
                    size=lot_size
                )
                
                bot_logger.info(f"Put order placed: {put_order.get('id')}")
                
                # Step 9: Place stop-loss orders
                # For long: SL is sell orders at higher price
                # For short: SL is buy orders at higher price
                sl_side = "sell" if direction == "long" else "buy"
                
                # Call stop-loss
                call_sl_order = await delta_api.place_stop_loss_order(
                    symbol=call_symbol,
                    side=sl_side,
                    size=lot_size,
                    stop_price=sl_trigger,
                    limit_price=sl_limit
                )
                
                bot_logger.info(f"Call SL order placed: {call_sl_order.get('id')}")
                
                # Put stop-loss
                put_sl_order = await delta_api.place_stop_loss_order(
                    symbol=put_symbol,
                    side=sl_side,
                    size=lot_size,
                    stop_price=sl_trigger,
                    limit_price=sl_limit
                )
                
                bot_logger.info(f"Put SL order placed: {put_sl_order.get('id')}")
                
                # Return execution summary
                return {
                    "success": True,
                    "call_symbol": call_symbol,
                    "put_symbol": put_symbol,
                    "call_premium": call_premium,
                    "put_premium": put_premium,
                    "total_premium": total_premium,
                    "call_order_id": call_order.get('id'),
                    "put_order_id": put_order.get('id'),
                    "call_sl_order_id": call_sl_order.get('id'),
                    "put_sl_order_id": put_sl_order.get('id'),
                    "sl_trigger": sl_trigger,
                    "sl_limit": sl_limit
                }
        
        except Exception as e:
            bot_logger.error(f"Error executing strangle: {e}")
            return {
                "success": False,
                "error": str(e)
              }
          
