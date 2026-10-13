import requests
import json
import logging
from typing import Dict, List, Optional, Any
from config import UPSTOX_TOKEN, load_env

logger = logging.getLogger(__name__)

class UpstoxClient:
    """Client for Upstox API v2 endpoints using user's access token."""
    
    BASE_URL = "https://api.upstox.com/v2"

    def __init__(self, token: Optional[str] = None):
        self.token = token or UPSTOX_TOKEN or load_env().get("TOKEN", "")

    def reload_token(self):
        """Reload token from .env file."""
        self.token = load_env().get("TOKEN", "")

    def _headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}"
        }

    def is_configured(self) -> bool:
        """Check if token is provided."""
        return bool(self.token and len(self.token) > 20)

    def validate_token(self) -> Dict[str, Any]:
        """Test token validity using a lightweight fundamentals call."""
        if not self.is_configured():
            return {"valid": False, "message": "No Upstox token configured in .env"}
        try:
            # Query TCS fundamentals as validation test
            url = f"{self.BASE_URL}/fundamentals/INE467B01029/corporate-actions"
            resp = requests.get(url, headers=self._headers(), timeout=7)
            if resp.status_code == 200:
                return {"valid": True, "message": "Upstox Token is active and valid"}
            elif resp.status_code == 401:
                return {"valid": False, "message": "Upstox Token expired or unauthorized (401)"}
            else:
                return {"valid": False, "message": f"Upstox API returned status {resp.status_code}"}
        except Exception as e:
            return {"valid": False, "message": f"Connection error: {str(e)}"}

    def get_ltp(self, instrument_keys: List[str]) -> Dict[str, float]:
        """
        Fetch Last Traded Price (LTP) for a list of instrument keys.
        Example keys: ['NSE_EQ|INE467B01029', 'NSE_EQ|INE205A01025']
        Returns dict: {'NSE_EQ:TCS': 2125.0, ...} and maps by ISIN as well.
        """
        if not self.is_configured() or not instrument_keys:
            return {}

        ltp_map = {}
        # Batch in chunks of 50 instruments
        chunk_size = 50
        for i in range(0, len(instrument_keys), chunk_size):
            chunk = instrument_keys[i:i + chunk_size]
            keys_param = ",".join(chunk)
            url = f"{self.BASE_URL}/market-quote/ltp?instrument_key={keys_param}"
            try:
                resp = requests.get(url, headers=self._headers(), timeout=10)
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    for k, val in data.items():
                        price = val.get("last_price", 0.0)
                        ltp_map[k] = price
                        inst_token = val.get("instrument_token", "")
                        if inst_token:
                            ltp_map[inst_token] = price
                            # Also map plain ISIN if present
                            if "|" in inst_token:
                                isin = inst_token.split("|", 1)[1]
                                ltp_map[isin] = price
            except Exception as e:
                logger.error(f"Error fetching LTP from Upstox: {e}")

        return ltp_map

    def get_quotes(self, instrument_keys: List[str]) -> Dict[str, Any]:
        """Fetch full quotes (OHLC, change, volume) for given instrument keys."""
        if not self.is_configured() or not instrument_keys:
            return {}

        quotes_map = {}
        chunk_size = 50
        for i in range(0, len(instrument_keys), chunk_size):
            chunk = instrument_keys[i:i + chunk_size]
            keys_param = ",".join(chunk)
            url = f"{self.BASE_URL}/market-quote/quotes?instrument_key={keys_param}"
            try:
                resp = requests.get(url, headers=self._headers(), timeout=10)
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    for k, val in data.items():
                        quotes_map[k] = val
                        inst_token = val.get("instrument_token", "")
                        if inst_token:
                            quotes_map[inst_token] = val
                            if "|" in inst_token:
                                isin = inst_token.split("|", 1)[1]
                                quotes_map[isin] = val
            except Exception as e:
                logger.error(f"Error fetching quotes from Upstox: {e}")

        return quotes_map

    def get_corporate_actions(self, isin: str) -> List[Dict[str, Any]]:
        """
        Fetch company fundamentals corporate actions from Upstox by ISIN.
        Returns list of dividend and corporate events with details.
        """
        if not self.is_configured() or not isin:
            return []

        url = f"{self.BASE_URL}/fundamentals/{isin}/corporate-actions"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", [])
            else:
                logger.warning(f"Upstox corporate actions for {isin} returned {resp.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error fetching Upstox corporate actions for {isin}: {e}")
            return []
