import hmac
import hashlib
import time
import requests
from typing import Dict, List, Optional, Any
from config.settings import DELTA_BASE_URL, API_TIMEOUT, MAX_RETRIES
import logging

logger = logging.getLogger(__name__)

class DeltaExchangeAPI:
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = DELTA_BASE_URL

    def _generate_signature(self, method: str, endpoint: str, 
                           query_string: str = '', body: str = '') -> tuple:
        """Generate HMAC-SHA256 signature for Delta Exchange API"""
        timestamp = str(int(time.time()))
        message = method + timestamp + endpoint + query_string + body
        
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature, timestamp

    def _make_request(self, method: str, endpoint: str, 
                     params: Optional[Dict] = None, 
                     data: Optional[Dict] = None) -> Optional[Dict]:
        """Make authenticated request to Delta Exchange API"""
        url = f"{self.base_url}{endpoint}"
        query_string = ''
        body = ''
        
        if params:
            query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
            url += f"?{query_string}"
        
        if data:
            import json
            body = json.dumps(data)
        
        signature, timestamp = self._generate_signature(method, endpoint, query_string, body)
        
        headers = {
            'api-key': self.api_key,
            'signature': signature,
            'timestamp': timestamp,
            'User-Agent': 'TelegramStraddleBot/1.0',
            'Content-Type': 'application/json'
        }
        
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.request(
                    method, url, headers=headers, 
                    json=data if data else None,
                    timeout=API_TIMEOUT
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"API Error: {response.status_code} - {response.text}")
                    if attempt == MAX_RETRIES - 1:
                        return None
                    time.sleep(2 ** attempt)  # Exponential backoff
                    
            except Exception as e:
                logger.error(f"Request exception (attempt {attempt + 1}): {e}")
                if attempt == MAX_RETRIES - 1:
                    return None
                time.sleep(2 ** attempt)
        
        return None

    def get_products(self, contract_types: str = 'call_options,put_options') -> Optional[List[Dict]]:
        """Fetch available option contracts"""
        response = self._make_request('GET', '/v2/products', 
                                     params={'contract_types': contract_types})
        if response and 'result' in response:
            return response['result']
        return None

    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Get real-time ticker data for a symbol"""
        response = self._make_request('GET', '/v2/tickers', params={'symbol': symbol})
        if response and 'result' in response:
            return response['result'][0] if response['result'] else None
        return None

    def get_spot_price(self, symbol: str = 'BTCUSD') -> Optional[float]:
        """Get current spot price"""
        ticker = self.get_ticker(symbol)
        if ticker and 'mark_price' in ticker:
            return float(ticker['mark_price'])
        return None

    def place_order(self, product_id: int, size: int, side: str, 
                   order_type: str = 'market_order', 
                   limit_price: Optional[float] = None) -> Optional[Dict]:
        """Place an order"""
        order_data = {
            'product_id': product_id,
            'size': size,
            'side': side,  # 'buy' or 'sell'
            'order_type': order_type,
            'time_in_force': 'ioc'  # Immediate or cancel
        }
        
        if limit_price and order_type == 'limit_order':
            order_data['limit_price'] = str(limit_price)
        
        response = self._make_request('POST', '/v2/orders', data=order_data)
        if response and 'result' in response:
            return response['result']
        return None

    def get_order_status(self, order_id: int) -> Optional[Dict]:
        """Check order status"""
        response = self._make_request('GET', f'/v2/orders/{order_id}')
        if response and 'result' in response:
            return response['result']
        return None

    def get_positions(self) -> Optional[List[Dict]]:
        """Fetch active positions"""
        response = self._make_request('GET', '/v2/positions')
        if response and 'result' in response:
            return response['result']
        return None

    def get_wallet_balance(self) -> Optional[Dict]:
        """Check wallet balance"""
        response = self._make_request('GET', '/v2/wallet/balances')
        if response and 'result' in response:
            return response['result']
        return None

    def close_position(self, product_id: int) -> Optional[Dict]:
        """Close a position"""
        positions = self.get_positions()
        if not positions:
            return None
        
        for position in positions:
            if position.get('product_id') == product_id:
                size = abs(int(position.get('size', 0)))
                side = 'sell' if float(position.get('size', 0)) > 0 else 'buy'
                return self.place_order(product_id, size, side)
        
        return None
        
