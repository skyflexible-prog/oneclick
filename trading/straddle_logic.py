from typing import Dict, Optional, Tuple, List
from trading.delta_api import DeltaExchangeAPI
from utils.logger import trade_logger
from datetime import datetime, timedelta
import asyncio


class StraddleCalculator:
    """Calculate ATM straddle strikes and premiums"""
    
    def __init__(self, api: DeltaExchangeAPI):
        self.api = api
    
    async def get_atm_strike(self, underlying: str, offset: int = 0, available_strikes: List[float] = None) -> Optional[float]:
        """
        Get ATM strike price with optional offset
        If available_strikes provided, finds nearest from those
        """
        try:
            spot_price = await self.api.get_spot_price(underlying)
            if not spot_price:
                return None
        
            # If we have available strikes, find the nearest one
            if available_strikes:
                atm_strike = min(available_strikes, key=lambda x: abs(x - spot_price))
            
                # Apply offset if specified
                if offset != 0:
                    strike_index = available_strikes.index(atm_strike)
                    new_index = strike_index + offset
                
                    # Ensure index is valid
                    if 0 <= new_index < len(available_strikes):
                        atm_strike = available_strikes[new_index]
            else:
                # Fallback: Round to nearest 100
                strike_interval = 100.0
                atm_strike = round(spot_price / strike_interval) * strike_interval
                
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
        Filters based on expiry_type from strategy settings
        """
        try:
            # Build products endpoint
            params = {
                'states': 'live',  # Only active contracts
                'contract_types': 'call_options,put_options',
                'underlying_asset_symbols': underlying.upper()
            }
        
            trade_logger.info(f"Fetching option chain: {underlying}, expiry type: {expiry_type}")
        
            # Make request
            response = await self.api._make_request('GET', '/v2/products', params=params)
        
            if not response or 'result' not in response:
                trade_logger.error(f"Invalid response from option chain: {response}")
                return []
        
            options = response['result']
            trade_logger.info(f"Fetched {len(options)} LIVE options for {underlying}")
        
            # Filter by expiry type
            filtered_options = self._filter_by_expiry_type(options, expiry_type)
            trade_logger.info(f"After filtering for {expiry_type} expiry: {len(filtered_options)} options")
        
            return filtered_options
        
        except Exception as e:
            trade_logger.error(f"Error fetching option chain: {e}", exc_info=True)
            return []

    def _filter_by_expiry_type(self, options: List[Dict], expiry_type: str) -> List[Dict]:
        """
        Filter options by expiry type: daily, weekly, or monthly
        Extracts expiry date from symbol: C-BTC-123600-081025 -> 08/10/25
        """
        try:
            from datetime import datetime, timedelta
        
            today = datetime.utcnow()
        
            # Extract all unique expiries from symbols
            expiry_dates = {}  # {expiry_str: date_obj}
        
            for option in options:
                symbol = option.get('symbol', '')
                parts = symbol.split('-')
            
                if len(parts) >= 4:
                    expiry_str = parts[-1]  # "081025"
                    
                    try:
                        # Parse DDMMYY format
                        expiry_date = datetime.strptime(expiry_str, '%d%m%y').date()
                        expiry_dates[expiry_str] = expiry_date
                    except:
                        continue
            
            if not expiry_dates:
                trade_logger.error("No valid expiry dates found in symbols")
                return []
            
            trade_logger.info(f"Available expiries: {sorted(expiry_dates.items(), key=lambda x: x[1])[:10]}")
        
            # Filter based on expiry type
            target_expiry_str = None
        
            if expiry_type.lower() == 'daily':
                # Get today's expiry
                today_str = today.strftime('%d%m%y')
            
                if today_str in expiry_dates:
                    target_expiry_str = today_str
                    trade_logger.info(f"✅ Using TODAY's expiry: {today_str} ({expiry_dates[today_str]})")
                else:
                    # Use nearest future expiry (next day)
                    future_expiries = {k: v for k, v in expiry_dates.items() if v >= today.date()}
                    if future_expiries:
                        target_expiry_str = min(future_expiries.items(), key=lambda x: x[1])[0]
                        trade_logger.info(f"⚠️ No today expiry, using nearest: {target_expiry_str} ({expiry_dates[target_expiry_str]})")
            
            elif expiry_type.lower() == 'weekly':
                # Get this week's Friday expiry (or nearest)
                days_to_friday = (4 - today.weekday()) % 7
                if days_to_friday == 0 and today.hour >= 12:  # After Friday noon UTC
                    days_to_friday = 7
            
                target_date = (today + timedelta(days=days_to_friday)).date()
            
                # Find closest match
                closest = min(expiry_dates.items(), 
                             key=lambda x: abs((x[1] - target_date).days))
                target_expiry_str = closest[0]
                trade_logger.info(f"✅ Using WEEKLY expiry: {target_expiry_str} ({expiry_dates[target_expiry_str]})")
        
            elif expiry_type.lower() == 'monthly':
                # Get last Friday of current month (or nearest)
                year = today.year
                month = today.month
            
                # Get last day of month
                if month == 12:
                    next_month = datetime(year + 1, 1, 1)
                else:
                    next_month = datetime(year, month + 1, 1)
            
                last_day = (next_month - timedelta(days=1)).date()
            
                # Find last Friday
                while last_day.weekday() != 4:  # 4 = Friday
                    last_day -= timedelta(days=1)
            
                # Find closest match
                closest = min(expiry_dates.items(), 
                             key=lambda x: abs((x[1] - last_day).days))
                target_expiry_str = closest[0]
                trade_logger.info(f"✅ Using MONTHLY expiry: {target_expiry_str} ({expiry_dates[target_expiry_str]})")
        
            else:
                trade_logger.error(f"Unknown expiry type: {expiry_type}")
                return []
        
            # Filter options by target expiry
            if target_expiry_str:
                filtered = [o for o in options if target_expiry_str in o.get('symbol', '')]
                trade_logger.info(f"Found {len(filtered)} options for expiry {target_expiry_str}")
                return filtered
        
            return []
        
        except Exception as e:
            trade_logger.error(f"Error filtering by expiry type: {e}", exc_info=True)
            return []

    def _get_expiry_date(self, expiry_type: str) -> Optional[str]:
        """
        Convert expiry type to date format DD-MM-YYYY
        Uses UTC time (Delta Exchange API standard)
        For 'daily', returns options expiring soonest (today or tomorrow)
        """
        try:
            from datetime import datetime, timedelta
        
            # Use UTC (Delta Exchange standard)
            now = datetime.utcnow()
        
            if expiry_type.lower() == 'daily':
                # For daily, we'll filter in the next step to get soonest expiring
                # Return None to fetch all and filter by expiry time
                return None  # Will filter to get soonest
        
            elif expiry_type.lower() == 'weekly':
                # Next Friday (weekly expiry day)
                days_ahead = 4 - now.weekday()  # Friday is 4
                if days_ahead <= 0:
                    days_ahead += 7
                target_date = now + timedelta(days=days_ahead)
        
            elif expiry_type.lower() == 'monthly':
                # Last Friday of current month
                # Move to next month, go back one day
                if now.month == 12:
                    target_date = datetime(now.year + 1, 1, 1)
                else:
                    target_date = datetime(now.year, now.month + 1, 1)
                # Find last Friday
                target_date = target_date - timedelta(days=1)
                while target_date.weekday() != 4:  # 4 = Friday
                    target_date = target_date - timedelta(days=1)
            else:
                return None  # Return None to fetch all
        
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
        
            # FIXED: Get all available strikes
            available_strikes = sorted(set([float(o.get('strike_price', 0)) 
                                       for o in options if 'strike_price' in o]))
        
            trade_logger.info(f"Available strikes: {available_strikes[:20]}")
        
            # FIXED: Find nearest strike if exact not found
            if strike not in available_strikes:
                nearest_strike = min(available_strikes, key=lambda x: abs(x - strike))
                trade_logger.info(f"⚠️ Strike {strike} not available. Using nearest: {nearest_strike}")
                strike = nearest_strike
            else:
                trade_logger.info(f"✅ Exact strike {strike} found")
        
            # Filter by strike (small tolerance for floating point)
            strike_options = [o for o in options if 
                            'strike_price' in o and 
                            abs(float(o['strike_price']) - strike) < 1.0]
            
            trade_logger.info(f"Found {len(strike_options)} options at strike {strike}")
        
            if not strike_options:
                trade_logger.error(f"No options at strike {strike}")
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
        use_stop_loss_order: bool = False,
        sl_trigger_pct: float = None,
        sl_limit_pct: float = None,
        use_target_order: bool = False,
        target_trigger_pct: float = None
    ) -> dict:
        """
        Execute long straddle (BUY both options) with optional stop-loss and target orders
    
        Args:
            call_symbol: Call option symbol
            put_symbol: Put option symbol
            lot_size: Number of contracts
            use_stop_loss_order: Whether to place stop-loss orders
            sl_trigger_pct: Stop-loss trigger percentage (e.g., 50 = 50% loss)
            sl_limit_pct: Stop-loss limit percentage (e.g., 55 = 55% loss)
            use_target_order: Whether to place target orders
            target_trigger_pct: Target trigger percentage (e.g., 100 = 100% profit)
    
        Returns:
            dict: Execution result with order details
        """
        trade_logger.info(f"Executing Long Straddle: {call_symbol}, {put_symbol}, Lot: {lot_size}")
    
        try:
            # Check available balance
            balance = await self.api.get_wallet_balance()
            available_balance = float(balance.get('available_balance', 0))
            trade_logger.info(f"Available balance: ${available_balance}")
        
            # Place market BUY orders for both options
            call_order = await self.api.place_order(
                symbol=call_symbol,
                side='buy',
                order_type='market_order',
                size=lot_size
            )
        
            put_order = await self.api.place_order(
                symbol=put_symbol,
                side='buy',
                order_type='market_order',
                size=lot_size
            )
        
            trade_logger.info(f"Long Straddle executed successfully")
        
            # Get filled prices for SL/Target calculation
            call_price = float(call_order['result'].get('average_fill_price', 0))
            put_price = float(put_order['result'].get('average_fill_price', 0))
        
            sl_orders = []
            target_orders = []
        
            # ✅ PLACE STOP-LOSS ORDERS (if enabled)
            if use_stop_loss_order and sl_trigger_pct and sl_limit_pct:
                trade_logger.info(f"Placing stop-loss orders (Trigger: {sl_trigger_pct}%, Limit: {sl_limit_pct}%)")
            
                # Calculate SL prices
                call_sl_trigger = call_price * (1 - sl_trigger_pct / 100)
                call_sl_limit = call_price * (1 - sl_limit_pct / 100)
            
                put_sl_trigger = put_price * (1 - sl_trigger_pct / 100)
                put_sl_limit = put_price * (1 - sl_limit_pct / 100)
            
                # Place stop-limit SELL orders for Call
                call_sl_order = await self.api.place_order(
                    symbol=call_symbol,
                    side='sell',
                    order_type='stop_limit_order',
                    size=lot_size,
                    limit_price=call_sl_limit,
                    stop_price=call_sl_trigger,
                    reduce_only=True  # Ensures it only closes existing position
                )
            
                # Place stop-limit SELL orders for Put
                put_sl_order = await self.api.place_order(
                    symbol=put_symbol,
                    side='sell',
                    order_type='stop_limit_order',
                    size=lot_size,
                    limit_price=put_sl_limit,
                    stop_price=put_sl_trigger,
                    reduce_only=True
                )
            
                sl_orders = [call_sl_order, put_sl_order]
                trade_logger.info(f"✅ Stop-loss orders placed successfully")
        
            # ✅ PLACE TARGET ORDERS (if enabled)
            if use_target_order and target_trigger_pct:
                trade_logger.info(f"Placing target orders (Target: {target_trigger_pct}%)")
                
                # Calculate target prices
                call_target_price = call_price * (1 + target_trigger_pct / 100)
                put_target_price = put_price * (1 + target_trigger_pct / 100)
            
                # Place limit SELL orders at target prices
                call_target_order = await self.api.place_order(
                    symbol=call_symbol,
                    side='sell',
                    order_type='limit_order',
                    size=lot_size,
                    limit_price=call_target_price,
                    reduce_only=True
                )
            
                put_target_order = await self.api.place_order(
                    symbol=put_symbol,
                    side='sell',
                    order_type='limit_order',
                    size=lot_size,
                    limit_price=put_target_price,
                    reduce_only=True
                )
            
                target_orders = [call_target_order, put_target_order]
                trade_logger.info(f"✅ Target orders placed successfully")
        
            return {
                'success': True,
                'call_order': call_order,
                'put_order': put_order,
                'sl_orders': sl_orders,
                'target_orders': target_orders,
                'call_price': call_price,
                'put_price': put_price
            }
        
        except Exception as e:
            trade_logger.error(f"Long straddle execution failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def execute_short_straddle(
        self, 
        call_symbol: str, 
        put_symbol: str, 
        lot_size: int,
        stop_loss_pct: float = None,
        use_stop_loss_order: bool = True,
        sl_trigger_pct: float = None,
        sl_limit_pct: float = None,
        use_target_order: bool = False,
        target_trigger_pct: float = None
    ) -> dict:
        """
        Execute short straddle (SELL both options) with optional stop-loss and target orders
    
        Args:
            call_symbol: Call option symbol
            put_symbol: Put option symbol
            lot_size: Number of contracts
            stop_loss_pct: Stop loss percentage (legacy, for backward compatibility)
            use_stop_loss_order: Whether to place stop-loss orders
            sl_trigger_pct: Stop-loss trigger percentage
            sl_limit_pct: Stop-loss limit percentage
            use_target_order: Whether to place target orders
            target_trigger_pct: Target trigger percentage
    
        Returns:
            dict: Execution result with order details
        """
        trade_logger.info(f"Executing Short Straddle: {call_symbol}, {put_symbol}, Lot: {lot_size}")
        
        try:
            # Check available balance
            balance = await self.api.get_wallet_balance()
            available_balance = float(balance.get('available_balance', 0))
            trade_logger.info(f"Available balance: ${available_balance}")
        
            # Place market SELL orders for both options
            call_order = await self.api.place_order(
                symbol=call_symbol,
                side='sell',
                order_type='market_order',
                size=lot_size
            )
        
            put_order = await self.api.place_order(
                symbol=put_symbol,
                side='sell',
                order_type='market_order',
                size=lot_size
            )
        
            trade_logger.info(f"Short Straddle executed successfully")
        
            # Get filled prices
            call_price = float(call_order['result'].get('average_fill_price', 0))
            put_price = float(put_order['result'].get('average_fill_price', 0))
        
            sl_orders = []
            target_orders = []
        
            # ✅ PLACE STOP-LOSS ORDERS (if enabled)
            if use_stop_loss_order and sl_trigger_pct and sl_limit_pct:
                trade_logger.info(f"Placing stop-loss orders (Trigger: {sl_trigger_pct}%, Limit: {sl_limit_pct}%)")
            
                # For short positions, SL = BUY at higher price
                call_sl_trigger = call_price * (1 + sl_trigger_pct / 100)
                call_sl_limit = call_price * (1 + sl_limit_pct / 100)
            
                put_sl_trigger = put_price * (1 + sl_trigger_pct / 100)
                put_sl_limit = put_price * (1 + sl_limit_pct / 100)
            
                # Place stop-limit BUY orders
                call_sl_order = await self.api.place_order(
                    symbol=call_symbol,
                    side='buy',
                    order_type='stop_limit_order',
                    size=lot_size,
                    limit_price=call_sl_limit,
                    stop_price=call_sl_trigger,
                    reduce_only=True
                )
            
                put_sl_order = await self.api.place_order(
                    symbol=put_symbol,
                    side='buy',
                    order_type='stop_limit_order',
                    size=lot_size,
                    limit_price=put_sl_limit,
                    stop_price=put_sl_trigger,
                    reduce_only=True
                )
            
                sl_orders = [call_sl_order, put_sl_order]
                trade_logger.info(f"✅ Stop-loss orders placed successfully")
        
            # ✅ PLACE TARGET ORDERS (if enabled)
            if use_target_order and target_trigger_pct:
                trade_logger.info(f"Placing target orders (Target: {target_trigger_pct}%)")
            
                # For short positions, target = BUY at lower price (profit)
                call_target_price = call_price * (1 - target_trigger_pct / 100)
                put_target_price = put_price * (1 - target_trigger_pct / 100)
            
                # Place limit BUY orders at target prices
                call_target_order = await self.api.place_order(
                    symbol=call_symbol,
                    side='buy',
                    order_type='limit_order',
                    size=lot_size,
                    limit_price=call_target_price,
                    reduce_only=True
                )
            
                put_target_order = await self.api.place_order(
                    symbol=put_symbol,
                    side='buy',
                    order_type='limit_order',
                    size=lot_size,
                    limit_price=put_target_price,
                    reduce_only=True
                )
            
                target_orders = [call_target_order, put_target_order]
                trade_logger.info(f"✅ Target orders placed successfully")
        
            return {
                'success': True,
                'call_order': call_order,
                'put_order': put_order,
                'sl_orders': sl_orders,
                'target_orders': target_orders,
                'call_price': call_price,
                'put_price': put_price
            }
        
        except Exception as e:
            trade_logger.error(f"Short straddle execution failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def _place_straddle_stop_loss(
        self,
        call_symbol: str,
        put_symbol: str,
        lot_size: int,
        call_premium: float,
        put_premium: float,
        stop_loss_pct: float
    ) -> None:
        """Place stop-loss orders for both legs of straddle"""
        try:
            # Calculate stop-loss levels
            # For short straddle, buy back when premium increases
            call_sl_trigger = call_premium * (1 + stop_loss_pct / 100)
            call_sl_limit = call_sl_trigger * 1.02  # 2% slippage allowance
        
            put_sl_trigger = put_premium * (1 + stop_loss_pct / 100)
            put_sl_limit = put_sl_trigger * 1.02
        
            # Place stop-loss buy orders
            call_sl_task = self.api.place_stop_limit_order(
                product_symbol=call_symbol,
                side='buy',  # Buy to close short
                size=lot_size,
                stop_price=str(call_sl_trigger),
                limit_price=str(call_sl_limit),
                reduce_only=True
            )
        
            put_sl_task = self.api.place_stop_limit_order(
                product_symbol=put_symbol,
                side='buy',
                size=lot_size,
                stop_price=str(put_sl_trigger),
                limit_price=str(put_sl_limit),
                reduce_only=True
            )
        
            call_sl, put_sl = await asyncio.gather(call_sl_task, put_sl_task)
        
            if 'result' in call_sl and 'result' in put_sl:
                trade_logger.info(f"✅ Stop-loss orders placed: Call @ {call_sl_trigger}, Put @ {put_sl_trigger}")
            else:
                trade_logger.error(f"Failed to place stop-loss orders: Call={call_sl}, Put={put_sl}")
        
        except Exception as e:
            trade_logger.error(f"Error placing stop-loss: {e}")

    
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
      
