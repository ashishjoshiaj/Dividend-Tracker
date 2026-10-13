import csv
import io
import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional, List, Any
import requests

logger = logging.getLogger(__name__)

CACHE_FILE = Path(__file__).parent / "isin_cache.json"
NSE_EQUITY_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"

class ISINResolver:
    """Manages local symbol to ISIN mapping for all NSE listed equities."""
    
    _instance = None
    _mapping: Dict[str, str] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ISINResolver, cls).__new__(cls)
            cls._instance._mapping = {}
            cls._instance.initialize()
        return cls._instance

    def initialize(self):
        """Load cache from disk, or fetch from NSE if not present."""
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    self._mapping = json.load(f)
                logger.info(f"Loaded {len(self._mapping)} symbol-to-ISIN mappings from {CACHE_FILE.name}")
                if len(self._mapping) > 100:
                    return
            except Exception as e:
                logger.warning(f"Failed to read {CACHE_FILE}: {e}")
        
        # Download if file doesn't exist or was empty
        self.refresh_from_nse()

    def refresh_from_nse(self) -> int:
        """Download latest EQUITY_L.csv from NSE and save to local JSON cache."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        try:
            logger.info(f"Downloading NSE equity master list from {NSE_EQUITY_URL}...")
            resp = requests.get(NSE_EQUITY_URL, headers=headers, timeout=15)
            if resp.status_code == 200:
                reader = csv.DictReader(io.StringIO(resp.text))
                new_map = {}
                for row in reader:
                    cleaned = {k.strip(): v.strip() for k, v in row.items() if k}
                    sym = cleaned.get("SYMBOL")
                    isin = cleaned.get("ISIN NUMBER")
                    if sym and isin:
                        new_map[sym.upper()] = isin
                
                if new_map:
                    self._mapping.update(new_map)
                    with open(CACHE_FILE, "w", encoding="utf-8") as f:
                        json.dump(self._mapping, f, indent=2)
                    logger.info(f"Successfully cached {len(self._mapping)} ISIN mappings to {CACHE_FILE.name}")
                    return len(self._mapping)
            else:
                logger.warning(f"NSE returned status {resp.status_code} while fetching equity master list.")
        except Exception as e:
            logger.error(f"Error downloading NSE equity master list: {e}")

        # Fallback dictionary of common dividend paying companies if download failed
        if not self._mapping:
            self._mapping = {
                "HCLTECH": "INE860A01027",
                "TCS": "INE467B01029",
                "INFY": "INE009A01021",
                "ITC": "INE154A01025",
                "PERSISTENT": "INE262H01021",
                "METROPOLIS": "INE112L01020",
                "HINDCOMPOS": "INE310C01029",
                "ROSSELLIND": "INE847C01020",
                "SCHAEFFLER": "INE513A01022",
                "UNIENTER": "INE037A01022",
                "VEDL": "INE205A01025",
                "COALINDIA": "INE522F01014",
                "IOC": "INE242A01010",
                "BPCL": "INE029A01011",
                "ONGC": "INE213A01029",
                "RECLTD": "INE020B01018",
                "PFC": "INE134E01011"
            }
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._mapping, f, indent=2)

        return len(self._mapping)

    def get_isin(self, symbol: str) -> Optional[str]:
        """Look up ISIN for given stock symbol (e.g. 'HCLTECH' -> 'INE860A01027')."""
        if not symbol:
            return None
        return self._mapping.get(symbol.strip().upper())

    def enrich_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich dividend records in-place by filling missing ISINs."""
        for r in records:
            current_isin = r.get("isin")
            if not current_isin or current_isin == "-":
                resolved = self.get_isin(r.get("symbol", ""))
                if resolved:
                    r["isin"] = resolved
        return records

# Singleton instance
isin_resolver = ISINResolver()
