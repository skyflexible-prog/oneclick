from typing import Dict, Optional, Tuple, List
from trading.delta_api import DeltaExchangeAPI
from utils.logger import trade_logger
from datetime import datetime, timedelta
import asyncio


class StraddleCalculator:
    """Calculate ATM straddle strikes and premiums"""
    
    def __init__(self, api: DeltaExchangeAPI):
        self.api = api
    
    async def get_atm_strike(self, underlying: str, offset: int = 0) -> Optional[float]:
        """
        Get ATM strike price with optional offset
        Rounds to nearest 100 for fine granularity
        Examples: 123530 → 123500, 123690 → 123700
        """
        try:
            spot_price = await self.api.get_spot_price(underlying)
            if not spot_price:
                return None
            
            # FIXED: Always use 100 interval for nearest rounding
            strike_interval = 100.0
            
            # Calculate ATM strike (nearest 100)
            atm_strike = round(spot_price / strike_interval) * strike_interval
            
            # Apply offset if specified
            if offset != 0:
                atm_strike = atm_strike + (offset * strike_interval)
            
            trade_logger.info(f"ATM Strike for {underlying}: {atm_strike} (Spot: {spot_price}, Offset: {offset})")
            return atm_strike
        
        except Exception as e:
            trade_logger.error(f"Error calculating ATM strike: {e}", exc_info=True)
            return None
    
    async def get_option_chain(self, underlying: str, expiry_type: str) -> List[Dict]:
        """
        Get option chain from Delta Exchange
        Uses: /v2/tickers?contract_types=call_options,put_options&underlying_asset_symbols=BTC&expiry_date=DD-MM-YYYY
        """
        try:
            # Calculate expiry date based on expiry_type
            expiry_date = self._get_expiry_date(expiry_type)
            if not expiry_date:
                trade_logger.error(f"Could not determine expiry date for {expiry_type}")
                return []
            
            # Build option chain endpoint
            params = {
                'contract_types': 'call_options,put_options',
                'underlying_asset_symbols': underlying.upper()
            }
            
            # Add expiry date if specific
            if expiry_date != 'all':
                params['expiry_date'] = expiry_date
            
            trade_logger.info(f"Fetching option chain: {underlying}, expiry: {expiry_date}")
            
            # Make request
            response = await self.api._make_request('GET', '/v2/tickers', params=params)
            
            if not response or 'result' not in response:
                trade_logger.error(f"Invalid response from option chain: {response}")
                return []
            
            options = response['result']
            trade_logger.info(f"Fetched {len(options)} options for {underlying}")
            
            return options
            
        except Exception as e:
            trade_logger.error(f"Error fetching option chain: {e}", exc_info=True)
            return []
    
    def _get_expiry_date(self, expiry_type: str) -> Optional[str]:
        """Convert expiry type to date format DD-MM-YYYY"""
        try:
            now = datetime.utcnow()
            
            if expiry_type.lower() == 'daily':
                # Today or tomorrow
                target_date = now + timedelta(days=1)
            elif expiry_type.lower() == 'weekly':
                # Next Friday (weekly expiry)
                days_ahead = 4 - now.weekday()  # Friday is 4
                if days_ahead <= 0:
                    days_ahead += 7
                target_date = now + timedelta(days=days_ahead)
            elif expiry_type.lower() == 'monthly':
                # Last Friday of month
                # For simplicity, use end of month
                if now.month == 12:
                    target_date = datetime(now.year + 1, 1, 1)
                else:
                    target_date = datetime(now.year, now.month + 1, 1)
                target_date = target_date - timedelta(days=1)
            else:
                # Return 'all' to get all expiries
                return 'all'
            
            # Format as DD-MM-YYYY
            return target_date.strftime('%d-%m-%Y')
            
        except Exception as e:
            trade_logger.error(f"Error calculating expiry date: {e}")
            return None
    
    async def find_option_contracts(
        self,
        underlying: str,
        strike: float,
        expiry_type: str
    ) -> Tuple[Optional[Dict], Optional[Dict]]:
        """Find call and put option contracts for given strike and expiry"""
        try:
            # Get option chain
            options = await self.get_option_chain(underlying, expiry_type)
            
            if not options:
                trade_logger.error("No options found in chain")
                return None, None
            
            trade_logger.info(f"Searching for strike {strike} in {len(options)} options")
            
            # Filter by strike (allow 50 tolerance)
            strike_options = [o for o in options if 
                            'strike_price' in o and 
                            abs(float(o['strike_price']) - strike) < 50]
            
            trade_logger.info(f"Found {len(strike_options)} options at strike ~{strike}")
            
            if not strike_options:
                # Log available strikes
                available_strikes = sorted(set([float(o.get('strike_price', 0)) 
                                               for o in options if 'strike_price' in o]))[:20]
                trade_logger.error(f"Strike {strike} not found. Available strikes: {available_strikes}")
                return None, None
            
            # Find call and put at exact same strike
            calls = [o for o in strike_options if o.get('contract_type') == 'call_options']
            puts = [o for o in strike_options if o.get('contract_type') == 'put_options']
            
            call_contract = calls[0] if calls else None
            put_contract = puts[0] if puts else None
            
            if call_contract:
                trade_logger.info(f"✅ Found Call: {call_contract.get('symbol')} at {call_contract.get('strike_price')}")
            else:
                trade_logger.error("❌ No Call option found")
            
            if put_contract:
                trade_logger.info(f"✅ Found Put: {put_contract.get('symbol')} at {put_contract.get('strike_price')}")
            else:
                trade_logger.error("❌ No Put option found")
            
            return call_contract, put_contract
        
        except Exception as e:
            trade_logger.error(f"Error finding option contracts: {e}", exc_info=True)
            return None, None
    
    # ... rest of the methods remain the same (get_option_premiums, calculate_straddle_cost, etc.) ...
    
    async def get_option_premiums(
        self,
        call_symbol: str,
        put_symbol: str
    ) -> Tuple[Optional[float], Optional[float]]:
        """Get current premiums for call and put options"""
        try:
            # Fetch both tickers concurrently
            call_task = self.api.get_tickers(call_symbol)
            put_task = self.api.get_tickers(put_symbol)
            
            call_response, put_response = await asyncio.gather(call_task, put_task)
            
            call_premium = None
            put_premium = None
            
            if 'result' in call_response:
                call_premium = float(call_response['result'].get('close', 0))
            
            if 'result' in put_response:
                put_premium = float(put_response['result'].get('close', 0))
            
            trade_logger.info(f"Premiums - Call: {call_premium}, Put: {put_premium}")
            return call_premium, put_premium
        
        except Exception as e:
            trade_logger.error(f"Error fetching option premiums: {e}")
            return None, None
    
    async def calculate_straddle_cost(
        self,
        call_premium: float,
        put_premium: float,
        lot_size: int,
        contract_size: float = 1.0
    ) -> float:
        """Calculate total cost of straddle"""
        total_premium = call_premium + put_premium
        total_cost = total_premium * lot_size * contract_size
        return round(total_cost, 2)
    
    async def calculate_straddle_targets(
        self,
        total_premium: float,
        stop_loss_pct: float,
        target_pct: Optional[float] = None
    ) -> Dict[str, float]:
        """Calculate stop loss and target levels"""
        sl_level = total_premium * (1 - stop_loss_pct / 100)
        
        targets = {
            "entry_premium": total_premium,
            "stop_loss": round(sl_level, 2),
            "stop_loss_amount": round(total_premium - sl_level, 2)
        }
        
        if target_pct:
            target_level = total_premium * (1 + target_pct / 100)
            targets["target"] = round(target_level, 2)
            targets["target_amount"] = round(target_level - total_premium, 2)
        
        return targets


class StraddleExecutor:
    """Execute straddle trades"""
    
    def __init__(self, api: DeltaExchangeAPI):
        self.api = api
        self.calculator = StraddleCalculator(api)
    
    async def execute_long_straddle(
        self,
        call_symbol: str,
        put_symbol: str,
        lot_size: int,
        use_limit: bool = False,
        price_tolerance: float = 0.02
    ) -> Dict:
        """Execute long straddle (buy call + buy put)"""
        try:
            trade_logger.info(f"Executing Long Straddle: {call_symbol}, {put_symbol}, Lot: {lot_size}")
            
            # Check margin requirements
            margin_check = await self.api.check_margin_requirements(call_symbol, lot_size)
            if not margin_check.get("sufficient"):
                return {
                    "success": False,
                    "error": "Insufficient margin",
                    "details": margin_check
                }
            
            # Place orders concurrently
            if use_limit:
                # Get current premiums for limit orders
                call_premium, put_premium = await self.calculator.get_option_premiums(
                    call_symbol, put_symbol
                )
                
                if not call_premium or not put_premium:
                    return {"success": False, "error": "Failed to fetch premiums"}
                
                # Add tolerance to limit prices
                call_limit = call_premium * (1 + price_tolerance)
                put_limit = put_premium * (1 + price_tolerance)
                
                call_task = self.api.place_limit_order(call_symbol, "buy", lot_size, call_limit)
                put_task = self.api.place_limit_order(put_symbol, "buy", lot_size, put_limit)
            else:
                # Market orders
                call_task = self.api.place_market_order(call_symbol, "buy", lot_size)
                put_task = self.api.place_market_order(put_symbol, "buy", lot_size)
            
            call_order, put_order = await asyncio.gather(call_task, put_task)
            
            # Check if both orders succeeded
            if 'error' in call_order or 'error' in put_order:
                # Rollback: cancel filled orders
                if 'error' not in call_order:
                    await self.api.cancel_order(call_order['result']['id'])
                if 'error' not in put_order:
                    await self.api.cancel_order(put_order['result']['id'])
                
                return {
                    "success": False,
                    "error": "Order execution failed",
                    "call_order": call_order,
                    "put_order": put_order
                }
            
            trade_logger.info("Long Straddle executed successfully")
            return {
                "success": True,
                "call_order": call_order['result'],
                "put_order": put_order['result']
            }
        
        except Exception as e:
            trade_logger.error(f"Error executing long straddle: {e}")
            return {"success": False, "error": str(e)}
    
    async def execute_short_straddle(
        self,
        call_symbol: str,
        put_symbol: str,
        lot_size: int,
        use_limit: bool = False,
        price_tolerance: float = 0.02
    ) -> Dict:
        """Execute short straddle (sell call + sell put)"""
        try:
            trade_logger.info(f"Executing Short Straddle: {call_symbol}, {put_symbol}, Lot: {lot_size}")
            
            # Check margin requirements (higher for short positions)
            margin_check = await self.api.check_margin_requirements(call_symbol, lot_size)
            if not margin_check.get("sufficient"):
                return {
                    "success": False,
                    "error": "Insufficient margin",
                    "details": margin_check
                }
            
            # Place orders concurrently
            if use_limit:
                call_premium, put_premium = await self.calculator.get_option_premiums(
                    call_symbol, put_symbol
                )
                
                if not call_premium or not put_premium:
                    return {"success": False, "error": "Failed to fetch premiums"}
                
                # Reduce tolerance for sell orders
                call_limit = call_premium * (1 - price_tolerance)
                put_limit = put_premium * (1 - price_tolerance)
                
                call_task = self.api.place_limit_order(call_symbol, "sell", lot_size, call_limit)
                put_task = self.api.place_limit_order(put_symbol, "sell", lot_size, put_limit)
            else:
                # Market orders
                call_task = self.api.place_market_order(call_symbol, "sell", lot_size)
                put_task = self.api.place_market_order(put_symbol, "sell", lot_size)
            
            call_order, put_order = await asyncio.gather(call_task, put_task)
            
            # Check if both orders succeeded
            if 'error' in call_order or 'error' in put_order:
                # Rollback
                if 'error' not in call_order:
                    await self.api.cancel_order(call_order['result']['id'])
                if 'error' not in put_order:
                    await self.api.cancel_order(put_order['result']['id'])
                
                return {
                    "success": False,
                    "error": "Order execution failed",
                    "call_order": call_order,
                    "put_order": put_order
                }
            
            trade_logger.info("Short Straddle executed successfully")
            return {
                "success": True,
                "call_order": call_order['result'],
                "put_order": put_order['result']
            }
        
        except Exception as e:
            trade_logger.error(f"Error executing short straddle: {e}")
            return {"success": False, "error": str(e)}
    
    async def close_straddle_position(
        self,
        call_symbol: str,
        put_symbol: str,
        lot_size: int,
        is_long: bool
    ) -> Dict:
        """Close straddle position"""
        try:
            trade_logger.info(f"Closing Straddle Position: {call_symbol}, {put_symbol}")
            
            # Opposite side for closing
            side = "sell" if is_long else "buy"
            
            # Close both legs concurrently
            call_task = self.api.place_market_order(call_symbol, side, lot_size)
            put_task = self.api.place_market_order(put_symbol, side, lot_size)
            
            call_order, put_order = await asyncio.gather(call_task, put_task)
            
            if 'error' in call_order or 'error' in put_order:
                return {
                    "success": False,
                    "error": "Failed to close position",
                    "call_order": call_order,
                    "put_order": put_order
                }
            
            trade_logger.info("Straddle position closed successfully")
            return {
                "success": True,
                "call_order": call_order['result'],
                "put_order": put_order['result']
            }
        
        except Exception as e:
            trade_logger.error(f"Error closing straddle: {e}")
            return {"success": False, "error": str(e)}
      
