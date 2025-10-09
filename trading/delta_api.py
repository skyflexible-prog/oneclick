import hmac
import hashlib
import time
import aiohttp
from typing import Dict, List, Optional
from config.settings import settings
from utils.logger import api_logger
import asyncio


class DeltaExchangeAPI:
    """Delta Exchange India API wrapper"""
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = settings.delta_base_url
        self.session = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    def _generate_signature(self, method: str, endpoint: str, query_string: str = "", body: str = "") -> tuple:
        """Generate HMAC-SHA256 signature for authentication"""
        timestamp = str(int(time.time()))
        message = method + timestamp + endpoint + query_string + body
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature, timestamp
    
    def _get_headers(self, method: str, endpoint: str, query_string: str, body: str) -> Dict[str, str]:
        """Generate request headers with signature"""
        timestamp = str(int(time.time()))
    
        # Build signature data
        # Format: METHOD + timestamp + endpoint + ? + query_string + body
        signature_data = method + timestamp + endpoint
    
        if query_string:
            signature_data += "?" + query_string
    
        signature_data += body
    
        # Generate signature
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
        return {
            'api-key': self.api_key,
            'timestamp': timestamp,
            'signature': signature,
            'Content-Type': 'application/json',
            'User-Agent': 'python-rest-client'
        }
    
    async def _make_request(
            self,
            method: str,
            endpoint: str,
            params: Dict = None,
            data: Dict = None,
            retry_count: int = 0
        ) -> Dict:
            """Make authenticated API request with retry logic"""
            if not self.session:
                self.session = aiohttp.ClientSession()
        
            url = f"{self.base_url}{endpoint}"
        
            # Build query string for signature (sorted alphabetically)
            query_string = ""
            if params:
                # Filter out None values and sort alphabetically
                filtered_params = {k: v for k, v in params.items() if v is not None}
                sorted_params = sorted(filtered_params.items())
                query_string = "&".join([f"{k}={v}" for k, v in sorted_params])
        
            # Build body for signature
            body = ""
            if data:
                import json
                body = json.dumps(data)
            
            # Get headers with correct signature
            headers = self._get_headers(method, endpoint, query_string, body)
            
            try:
                # Build request kwargs - only add params/data if they exist
                request_kwargs = {
                    'method': method,
                    'url': url,
                    'headers': headers,
                    'timeout': aiohttp.ClientTimeout(total=settings.api_call_timeout)
                }
            
                # Only add params if not None and not empty
                if params:
                    request_kwargs['params'] = params
            
                # Only add json data if not None
                if data:
                    request_kwargs['json'] = data
            
                async with self.session.request(**request_kwargs) as response:
                    # Handle different content types
                    content_type = response.headers.get('Content-Type', '')
                
                    if 'application/json' in content_type:
                        response_data = await response.json()
                    elif response.status == 200:
                        # Some endpoints return empty body on success
                        text = await response.text()
                        if text.strip():
                            try:
                                response_data = await response.json()
                            except:
                                response_data = {'result': text}
                        else:
                            response_data = {'result': 'success'}
                    else:
                        text = await response.text()
                        api_logger.error(f"Unexpected content type: {content_type}, body: {text}")
                        return {"error": f"Unexpected content type: {content_type}", "body": text}
                
                    if response.status == 200:
                        api_logger.info(f"API call successful: {method} {endpoint}")
                        return response_data
                    else:
                        api_logger.error(f"API error: {response.status} - {response_data}")
                    
                        # Retry on specific errors
                        if retry_count < settings.max_retries and response.status in [429, 500, 502, 503]:
                            wait_time = 2 ** retry_count  # Exponential backoff
                            api_logger.info(f"Retrying after {wait_time}s...")
                            await asyncio.sleep(wait_time)
                            return await self._make_request(method, endpoint, params, data, retry_count + 1)
                    
                        return {"error": response_data, "status": response.status}
        
            except asyncio.TimeoutError:
                api_logger.error(f"Request timeout: {method} {endpoint}")
                if retry_count < settings.max_retries:
                    return await self._make_request(method, endpoint, params, data, retry_count + 1)
                return {"error": "Request timeout"}
        
            except Exception as e:
                api_logger.error(f"Request exception: {str(e)}", exc_info=True)
                return {"error": str(e)}
        
    # ==================== MARKET DATA ENDPOINTS ====================
    
    async def get_products(self, symbol: str = None) -> Dict:
        """Get all available products/contracts"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        
        return await self._make_request('GET', '/v2/products', params=params)
    
    async def get_tickers(self, symbol: str = None) -> Dict:
        """Get real-time ticker data"""
        endpoint = '/v2/tickers'
        if symbol:
            endpoint += f'/{symbol}'
        
        return await self._make_request('GET', endpoint)
    
    async def get_ticker_by_symbol(self, symbol: str) -> Optional[Dict]:
        """
        Get real-time ticker data for a specific symbol
    
        Args:
            symbol: Product symbol (e.g., 'C-BTC-122000-081025')
    
        Returns:
            Ticker data dict with mark_price, close, etc. or None
        """
        try:
            response = await self.get_tickers(symbol)
        
            if response and 'result' in response:
                return response['result']
        
            api_logger.warning(f"No ticker data for {symbol}")
            return None
        
        except Exception as e:
            api_logger.error(f"Error fetching ticker for {symbol}: {e}")
            return None
    
    async def get_orderbook(self, symbol: str) -> Dict:
        """Get orderbook for a symbol"""
        return await self._make_request('GET', f'/v2/l2orderbook/{symbol}')
    
    async def get_spot_price(self, underlying: str) -> Optional[float]:
        """Get current spot price for underlying (BTC, ETH)"""
        try:
            # Use perpetual contract symbols (these return actual data)
            contract_map = {
                "BTC": "BTCUSD",
                "ETH": "ETHUSD"
            }
        
            contract_symbol = contract_map.get(underlying.upper())
            if not contract_symbol:
                api_logger.error(f"Unsupported underlying: {underlying}")
                return None
        
            api_logger.info(f"Fetching spot price for {underlying} using {contract_symbol}")
        
            # Get ticker for perpetual contract
            response = await self._make_request('GET', f'/v2/tickers/{contract_symbol}')
        
            if not response or not isinstance(response, dict):
                api_logger.error(f"Invalid response: {response}")
                return None
        
            if not response.get('success'):
                api_logger.error(f"API error: {response}")
                return None
        
            result = response.get('result')
            if not result:
                api_logger.error(f"No result for {contract_symbol}: {response}")
                return None
        
            # Get mark price from perpetual
            mark_price = result.get('mark_price')
            if not mark_price:
                api_logger.error(f"No mark_price in result: {result}")
                return None
        
            price = float(mark_price)
            api_logger.info(f"✅ {underlying} spot price: ₹{price:,.2f}")
            return price
        
        except Exception as e:
            api_logger.error(f"Exception: {e}", exc_info=True)
            return None

    async def get_option_chain(self, underlying: str, expiry_date: str = None) -> List[Dict]:
        """Get option chain for underlying"""
        try:
            response = await self.get_products()
            
            if 'result' not in response:
                return []
            
            options = []
            for product in response['result']:
                # Filter options for specific underlying
                if (product.get('product_type') == 'call_options' or 
                    product.get('product_type') == 'put_options'):
                    if underlying.upper() in product.get('symbol', ''):
                        if expiry_date is None or expiry_date in product.get('symbol', ''):
                            options.append(product)
            
            return options
        except Exception as e:
            api_logger.error(f"Error fetching option chain: {e}")
            return []
    
    # ==================== ACCOUNT ENDPOINTS ====================
    
    async def get_wallet_balance(self) -> Dict:
        """Get wallet balance and available margin"""
        return await self._make_request('GET', '/v2/wallet/balances')
    
    async def get_positions(self) -> List[Dict]:
        """
        Get all open positions for BTC and ETH
    
        Returns:
            List of position dictionaries
        """
        try:
            all_positions = []
        
            # Fetch positions for BTC
            btc_params = {'underlying_asset_symbol': 'BTC'}
            btc_response = await self._make_request('GET', '/v2/positions', params=btc_params)
        
            # ✅ DEBUG: Log raw API response
            api_logger.info(f"BTC positions response: {btc_response}")
        
            if 'result' in btc_response:
                all_positions.extend(btc_response['result'])
                # ✅ DEBUG: Log first position structure
                if btc_response['result']:
                    api_logger.info(f"Sample BTC position: {btc_response['result'][0]}")
        
            # Fetch positions for ETH
            eth_params = {'underlying_asset_symbol': 'ETH'}
            eth_response = await self._make_request('GET', '/v2/positions', params=eth_params)
        
            # ✅ DEBUG: Log raw API response
            api_logger.info(f"ETH positions response: {eth_response}")
        
            if 'result' in eth_response:
                all_positions.extend(eth_response['result'])
                # ✅ DEBUG: Log first position structure
                if eth_response['result']:
                    api_logger.info(f"Sample ETH position: {eth_response['result'][0]}")
        
            api_logger.info(f"Fetched {len(all_positions)} positions (BTC + ETH)")
        
            # ✅ DEBUG: Log all positions
            for idx, pos in enumerate(all_positions):
                api_logger.info(f"Position {idx}: size={pos.get('size')}, product={pos.get('product')}, keys={list(pos.keys())}")
        
            return all_positions
    
        except Exception as e:
            api_logger.error(f"Error getting positions: {e}", exc_info=True)
            return []

    async def get_position_by_symbol(self, symbol: str) -> Optional[Dict]:
        """
        Get position for a specific symbol by filtering all positions
    
        Args:
            symbol: Option symbol (e.g., 'C-BTC-124200-071025')
    
        Returns:
            Position dictionary or None if not found
        """
        try:
            # Get all positions
            all_positions = await self.get_positions()
        
            # Find position matching symbol
            for position in all_positions:
                product = position.get('product', {})
                if product.get('symbol') == symbol:
                    api_logger.info(f"Found position for {symbol}")
                    return position
        
            api_logger.info(f"No position found for symbol {symbol}")
            return None
    
        except Exception as e:
            api_logger.error(f"Error getting position for {symbol}: {e}", exc_info=True)
            return None

    async def get_position_margin(self, symbol: str) -> Dict:
        """Get position margin requirements"""
        return await self._make_request('GET', f'/v2/positions/margined/{symbol}')
    
    # ==================== ORDER ENDPOINTS ====================
    
    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        size: int,
        limit_price: float = None,
        stop_price: float = None,
        post_only: bool = False,
        reduce_only: bool = False,
        time_in_force: str = "gtc"
    ) -> Dict:
        """Place an order"""
        data = {
            "product_symbol": symbol,
            "size": size,
            "side": side,  # "buy" or "sell"
            "order_type": order_type,  # "market_order", "limit_order", "stop_market_order"
            "time_in_force": time_in_force,  # "gtc", "ioc", "fok"
            "post_only": post_only,
            "reduce_only": reduce_only
        }
        
        if limit_price and order_type == "limit_order":
            data["limit_price"] = str(limit_price)
        
        if stop_price:
            data["stop_order_type"] = "stop_loss_order"
            data["stop_price"] = str(stop_price)
        
        return await self._make_request('POST', '/v2/orders', data=data)
    
    async def place_market_order(self, symbol: str, side: str, size: int) -> Dict:
        """Place a market order"""
        return await self.place_order(symbol, side, "market_order", size)
    
    async def place_limit_order(self, symbol: str, side: str, size: int, price: float) -> Dict:
        """Place a limit order"""
        return await self.place_order(symbol, side, "limit_order", size, limit_price=price)
    
    async def place_bracket_order(
        self,
        symbol: str,
        side: str,
        size: int,
        stop_loss_price: float,
        take_profit_price: float = None
    ) -> Dict:
        """Place bracket order with stop loss and optional take profit"""
        # Place main order first
        main_order = await self.place_market_order(symbol, side, size)
        
        if 'error' in main_order:
            return main_order
        
        # Place stop loss order
        sl_side = "sell" if side == "buy" else "buy"
        sl_order = await self.place_order(
            symbol, sl_side, "stop_market_order", size,
            stop_price=stop_loss_price, reduce_only=True
        )
        
        result = {
            "main_order": main_order,
            "stop_loss_order": sl_order
        }
        
        # Place take profit order if specified
        if take_profit_price:
            tp_order = await self.place_order(
                symbol, sl_side, "limit_order", size,
                limit_price=take_profit_price, reduce_only=True
            )
            result["take_profit_order"] = tp_order
        
        return result
    
    async def cancel_order(self, order_id: str) -> Dict:
        """Cancel an order"""
        return await self._make_request('DELETE', f'/v2/orders/{order_id}')
    
    async def cancel_all_orders(self, symbol: str = None) -> Dict:
        """Cancel all orders"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        
        return await self._make_request('DELETE', '/v2/orders/all', params=params)
    
    async def get_order(self, order_id: str) -> Dict:
        """Get order details"""
        return await self._make_request('GET', f'/v2/orders/{order_id}')
    
    async def get_order_history(self, symbol: str = None, limit: int = 100) -> Dict:
        """Get order history"""
        params = {'limit': limit}
        if symbol:
            params['symbol'] = symbol
        
        return await self._make_request('GET', '/v2/orders/history', params=params)
    
    # ==================== HELPER METHODS ====================
    
    async def get_contract_size(self, symbol: str) -> Optional[float]:
        """Get contract size for a symbol"""
        try:
            response = await self.get_products(symbol)
            if 'result' in response and response['result']:
                return float(response['result'][0].get('contract_value', 1.0))
            return None
        except Exception as e:
            api_logger.error(f"Error fetching contract size: {e}")
            return None

    # trading/delta_api.py (ADD THESE METHODS)

    async def get_open_orders(self, product_id: int = None):
        """Get open orders"""
        params = {"state": "open"}
        if product_id:
            params["product_id"] = product_id
    
        response = await self._make_request("GET", "/v2/orders", params=params)
        return response.get("result", [])


    async def edit_order(self, product_id: int, order_id: int, **kwargs):
        """
        Edit an existing order
    
        Args:
            product_id: Product ID
            order_id: Order ID to edit
            **kwargs: Fields to update (stop_price, limit_price, size, etc.)
        """
        payload = {
            "product_id": product_id,
            "id": order_id,
            **kwargs
        }
    
        response = await self._make_request("PUT", f"/v2/orders/{order_id}", json_data=payload)
        return response.get("result")


    async def cancel_order(self, product_id: int, order_id: int):
        """Cancel an order"""
        response = await self._make_request("DELETE", f"/v2/orders/{order_id}", params={"product_id": product_id})
        return response.get("result")


    # trading/delta_api.py

    async def get_position(self, product_id: int = None):
        """
        Get positions for a product
        Returns a list of positions
        """
        params = {}
        if product_id:
            params["product_id"] = product_id
    
        response = await self._make_request("GET", "/v2/positions/margined", params=params)
    
        # Delta API returns: {"success": true, "result": [...]}
        if response.get("success") and "result" in response:
            return response["result"]  # Return the list of positions
    
        return []

    async def check_margin_requirements(self, symbol: str, size: int) -> Dict:
        """Check if sufficient margin available for order"""
        try:
            balance = await self.get_wallet_balance()
            margin_info = await self.get_position_margin(symbol)
            
            available_margin = 0
            if 'result' in balance:
                for wallet in balance['result']:
                    if wallet.get('asset_symbol') == 'INR':
                        available_margin = float(wallet.get('available_balance', 0))
            
            required_margin = 0
            if 'result' in margin_info:
                required_margin = float(margin_info['result'].get('margin', 0)) * size
            
            return {
                "sufficient": available_margin >= required_margin,
                "available": available_margin,
                "required": required_margin
            }
        except Exception as e:
            api_logger.error(f"Error checking margin: {e}")
            return {"sufficient": False, "error": str(e)}
                                    
    async def place_stop_limit_order(
        self,
        product_symbol: str,
        side: str,  # 'buy' or 'sell'
        size: int,
        stop_price: str,  # Trigger price
        limit_price: str,  # Execution price
        reduce_only: bool = True  # True for stop-loss
    ) -> Dict:
        """
        Place stop-limit order for stop-loss protection
    
        Args:
            product_symbol: Option symbol (e.g., 'C-BTC-123600-081025')
            side: 'buy' for closing short, 'sell' for closing long
            size: Number of contracts
            stop_price: Price at which order is triggered
            limit_price: Maximum/minimum price to execute
            reduce_only: True to only close positions (recommended for SL)
    
        Returns:
            API response with order details
        """
        try:
            # Get product ID from symbol
            product_response = await self._make_request('GET', f'/v2/products')
        
            if 'result' not in product_response:
                return {'error': 'Failed to fetch products'}
        
            product_id = None
            for product in product_response['result']:
                if product.get('symbol') == product_symbol:
                    product_id = product.get('id')
                    break
            
            if not product_id:
                return {'error': f'Product not found: {product_symbol}'}
        
            # Place stop-limit order
            order_data = {
                'product_id': product_id,
                'size': size,
                'side': side,
                'order_type': 'limit_order',  # Limit order
                'limit_price': limit_price,
                'stop_order_type': 'stop_loss_order',  # Stop-loss type
                'stop_price': stop_price,  # Trigger price
                'reduce_only': reduce_only,  # Only close position
                'time_in_force': 'gtc'  # Good-till-cancel
            }
        
            response = await self._make_request('POST', '/v2/orders', data=order_data)
        
            if 'result' in response:
                api_logger.info(f"Stop-loss order placed: {product_symbol} @ stop={stop_price}, limit={limit_price}")
                return response
            else:
                api_logger.error(f"Failed to place stop-loss: {response}")
                return response
        
        except Exception as e:
            api_logger.error(f"Error placing stop-loss order: {e}", exc_info=True)
            return {'error': str(e)}
                        
