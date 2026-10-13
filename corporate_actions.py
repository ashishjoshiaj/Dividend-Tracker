import os
import re
import json
import time
import logging
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import requests

from config import CACHE_FILE, CACHE_TTL
from upstox_client import UpstoxClient
from isin_resolver import isin_resolver

logger = logging.getLogger(__name__)

class CorporateActionsManager:
    """Manages fetching, parsing, caching, and enriching dividend corporate actions."""

    def __init__(self, upstox_client: Optional[UpstoxClient] = None):
        self.upstox = upstox_client or UpstoxClient()
        self.div_pattern = re.compile(r'\b(?:div|dividend)\b', re.IGNORECASE)
        self.amount_pattern = re.compile(
            r'(?:Rs\.?|Re\.?|INR)\s*([\d\.]+)', re.IGNORECASE
        )

    def _parse_date(self, date_str: str) -> Optional[datetime.date]:
        """Parse various exchange date formats (e.g. 14-Oct-2026, 14-10-2026, October 16, 2026, 21 September 2026)."""
        if not date_str or date_str == "-":
            return None
        clean = date_str.replace(",", "").strip()
        parts = clean.split()
        if len(parts) == 3:
            clean = " ".join(parts)
        formats = [
            "%d-%b-%Y", "%d-%b-%y",
            "%d-%B-%Y", "%d-%m-%Y",
            "%Y-%m-%d", "%d/%m/%Y",
            "%d %b %Y", "%d %B %Y",
            "%B %d %Y", "%b %d %Y"
        ]
        for fmt in formats:
            try:
                return datetime.datetime.strptime(clean, fmt).date()
            except ValueError:
                continue
        return None

    def _classify_dividend_type(self, subject: str) -> str:
        """Classify dividend into Interim, Final, Special, or Dividend."""
        subj_upper = subject.upper()
        if "SPECIAL" in subj_upper:
            return "Special Dividend"
        elif "INTERIM" in subj_upper:
            return "Interim Dividend"
        elif "FINAL" in subj_upper:
            return "Final Dividend"
        return "Dividend"

    def _extract_amount(self, subject: str) -> float:
        """Extract per share dividend amount from subject string using prioritized regex patterns."""
        # Priority 1: Exact per-share specification (e.g. "Rs 4 per share", "₹ 2.00 per Equity Share")
        p1 = re.search(r'(?:Rs\.?|Re\.?|INR|₹|&#8377;)\s*(\d+(?:\.\d+)?)\s*(?:/-)?\s*per\s+(?:equity\s+)?share', subject, re.IGNORECASE)
        if p1:
            try:
                return float(p1.group(1))
            except ValueError:
                pass

        # Priority 2: "Dividend of Rs 12"
        p2 = re.search(r'dividend\s+(?:of\s+)?(?:Rs\.?|Re\.?|INR|₹|&#8377;)?\s*(\d+(?:\.\d+)?)', subject, re.IGNORECASE)
        if p2:
            try:
                return float(p2.group(1))
            except ValueError:
                pass

        # Priority 3: "Dividend - Rs 10 Per Share" or "Dividend - Rs 5"
        p3 = re.search(r'dividend\s*-\s*(?:Rs\.?|Re\.?|INR|₹|&#8377;)?\s*(\d+(?:\.\d+)?)', subject, re.IGNORECASE)
        if p3:
            try:
                return float(p3.group(1))
            except ValueError:
                pass

        # Priority 4: Generic amount pattern
        p4 = re.search(r'(?:Rs\.?|Re\.?|INR|₹|&#8377;)\s*(\d+(?:\.\d+)?)', subject, re.IGNORECASE)
        if p4:
            try:
                return float(p4.group(1))
            except ValueError:
                pass

        return 0.0

    def fetch_exchange_actions(self, days_back: int = 15, days_forward: int = 100) -> List[Dict[str, Any]]:
        """Fetch official equity corporate actions from NSE India."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-actions",
        }
        session = requests.Session()
        session.headers.update(headers)
        
        today = datetime.date.today()
        from_date = (today - datetime.timedelta(days=days_back)).strftime("%d-%m-%Y")
        to_date = (today + datetime.timedelta(days=days_forward)).strftime("%d-%m-%Y")

        # NSE requires visiting home page to establish session cookies
        try:
            session.get("https://www.nseindia.com", timeout=8)
        except Exception as e:
            logger.warning(f"Could not connect to NSE homepage: {e}")

        # Try with date range first
        url = f"https://www.nseindia.com/api/corporates-corporateActions?index=equities&from_date={from_date}&to_date={to_date}"
        try:
            resp = session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data:
                    return data
        except Exception as e:
            logger.warning(f"NSE date-range query failed: {e}")

        # Fallback to default corporate actions endpoint
        try:
            fallback_url = "https://www.nseindia.com/api/corporates-corporateActions?index=equities"
            resp = session.get(fallback_url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.error(f"NSE default endpoint failed: {e}")

        return []

    def fetch_live_announcements(self, days_back: int = 45) -> List[Dict[str, Any]]:
        """Fetch real-time corporate announcements from NSE to capture all breaking dividend declarations."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com",
        }
        session = requests.Session()
        session.headers.update(headers)
        try:
            session.get("https://www.nseindia.com", timeout=8)
        except Exception:
            pass

        today = datetime.date.today()
        from_str = (today - datetime.timedelta(days=days_back)).strftime("%d-%m-%Y")
        from_recent = (today - datetime.timedelta(days=7)).strftime("%d-%m-%Y")
        today_str = today.strftime("%d-%m-%Y")

        items = []
        seen_keys = set()

        # Targeted fast queries for Dividend and Record Date + recent general feed
        urls = [
            f"https://www.nseindia.com/api/corporate-announcements?index=equities&from_date={from_str}&to_date={today_str}&subject=Dividend",
            f"https://www.nseindia.com/api/corporate-announcements?index=equities&from_date={from_str}&to_date={today_str}&subject=Record+Date",
            f"https://www.nseindia.com/api/corporate-announcements?index=equities&from_date={from_recent}&to_date={today_str}"
        ]

        for u in urls:
            try:
                resp = session.get(u, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        for it in data:
                            key = (it.get("symbol"), it.get("an_dt"), it.get("desc"))
                            if key not in seen_keys:
                                seen_keys.add(key)
                                items.append(it)
            except Exception as e:
                logger.warning(f"Error fetching announcements from {u}: {e}")

        if not items:
            return []

        by_symbol = {}
        for it in items:
            sym = it.get("symbol")
            if sym:
                by_symbol.setdefault(sym, []).append(it)

        date_patterns = [
            r'(\d{1,2}-[A-Za-z]{3,9}-\d{4})',
            r'([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})',
            r'(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})'
        ]

        breaking_divs = []
        for sym, anns in by_symbol.items():
            combined = " ".join([f"{a.get('desc','')} {a.get('attchmntText','')}" for a in anns])
            if not self.div_pattern.search(combined):
                continue

            # Skip negative announcements
            if "not recommend any dividend" in combined.lower() or "no dividend" in combined.lower():
                continue
            if "unclaimed" in combined.lower() and not ("declared" in combined.lower() or "interim" in combined.lower() or "record date" in combined.lower()):
                continue

            div_amt = self._extract_amount(combined)

            # Extract record date / ex date
            rec_m = re.search(r'Record\s+date.*?([0-9]{1,2}-[A-Za-z]{3,9}-[0-9]{4}|[A-Za-z]{3,9}\s+[0-9]{1,2},?\s+[0-9]{4}|[0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4})', combined, re.IGNORECASE)
            date_str = rec_m.group(1) if rec_m else ""
            if not date_str:
                for p in date_patterns:
                    m = re.findall(p, combined)
                    if m:
                        date_str = m[0]
                        break

            ex_dt = self._parse_date(date_str)
            days_left = (ex_dt - today).days if ex_dt else None

            # Include upcoming or active announced dividends
            if days_left is not None and days_left >= -1:
                div_type = "Special Interim Dividend" if "SPECIAL" in combined.upper() else ("Interim Dividend" if "INTERIM" in combined.upper() else "Dividend")
                amt_label = f"Rs {div_amt} Per Share" if div_amt > 0 else "Amount TBA"
                breaking_divs.append({
                    "symbol": sym,
                    "company_name": anns[0].get("sm_name") or sym,
                    "isin": isin_resolver.get_isin(sym) or "-",
                    "series": "EQ",
                    "face_value": "10",
                    "subject": f"{div_type} - {amt_label} (Announced)",
                    "dividend_type": div_type,
                    "dividend_amount": div_amt,
                    "annual_dividend": 0.0,
                    "ex_date": ex_dt.isoformat() if ex_dt else date_str,
                    "ex_date_formatted": ex_dt.strftime("%d %b %Y") if ex_dt else (date_str or "To be notified"),
                    "record_date": ex_dt.isoformat() if ex_dt else date_str,
                    "record_date_formatted": ex_dt.strftime("%d %b %Y") if ex_dt else (date_str or "To be notified"),
                    "days_remaining": days_left,
                    "is_upcoming": (days_left >= 0),
                    "within_5_days": (0 <= days_left <= 5),
                    "within_10_days": (0 <= days_left <= 10),
                    "within_20_days": (0 <= days_left <= 20),
                    "within_30_days": (0 <= days_left <= 30),
                    "within_45_days": (0 <= days_left <= 45),
                    "within_60_days": (0 <= days_left <= 60),
                    "within_75_days": (0 <= days_left <= 75),
                    "within_90_days": (0 <= days_left <= 90),
                    "ltp": 0.0,
                    "net_change": 0.0,
                    "day_change_percent": 0.0,
                    "dividend_yield": 0.0,
                    "source": "NSE Announcements"
                })

        return breaking_divs

    def parse_dividends(self, raw_actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter and parse dividend records from raw corporate action items."""
        today = datetime.date.today()
        dividends = []
        seen_keys = set()

        for item in raw_actions:
            subject = str(item.get("subject", "") or item.get("purpose", "")).strip()
            
            # Avoid matching stock splits that say "Sub-division" unless it's a dividend
            if "SPLIT" in subject.upper() and not ("DIVIDEND" in subject.upper()):
                continue
            
            if not self.div_pattern.search(subject):
                continue

            symbol = item.get("symbol", "").strip()
            ex_date_str = item.get("exDate", "").strip()
            unique_key = f"{symbol}_{ex_date_str}"
            if unique_key in seen_keys:
                continue
            seen_keys.add(unique_key)

            ex_date = self._parse_date(ex_date_str)
            rec_date_str = item.get("recDate", "").strip()
            rec_date = self._parse_date(rec_date_str)

            days_left = (ex_date - today).days if ex_date else None
            div_amount = self._extract_amount(subject)
            div_type = self._classify_dividend_type(subject)

            dividends.append({
                "symbol": symbol,
                "company_name": item.get("comp", "") or item.get("companyName", "") or symbol,
                "isin": item.get("isin", "").strip() or isin_resolver.get_isin(symbol) or "-",
                "series": item.get("series", "EQ").strip(),
                "face_value": item.get("faceVal", "10").strip(),
                "subject": subject,
                "dividend_type": div_type,
                "dividend_amount": div_amount,
                "annual_dividend": 0.0,
                "ex_date": ex_date.isoformat() if ex_date else ex_date_str,
                "ex_date_formatted": ex_date.strftime("%d %b %Y") if ex_date else ex_date_str,
                "record_date": rec_date.isoformat() if rec_date else rec_date_str,
                "record_date_formatted": rec_date.strftime("%d %b %Y") if rec_date else rec_date_str,
                "days_remaining": days_left,
                "is_upcoming": (days_left is not None and days_left >= 0),
                # Time frame flags (5, 10, 20, 30, 45, 60, 75, 90 days)
                "within_5_days": (days_left is not None and 0 <= days_left <= 5),
                "within_10_days": (days_left is not None and 0 <= days_left <= 10),
                "within_20_days": (days_left is not None and 0 <= days_left <= 20),
                "within_30_days": (days_left is not None and 0 <= days_left <= 30),
                "within_45_days": (days_left is not None and 0 <= days_left <= 45),
                "within_60_days": (days_left is not None and 0 <= days_left <= 60),
                "within_75_days": (days_left is not None and 0 <= days_left <= 75),
                "within_90_days": (days_left is not None and 0 <= days_left <= 90),
                # Upstox live enrichment placeholders
                "ltp": 0.0,
                "net_change": 0.0,
                "day_change_percent": 0.0,
                "dividend_yield": 0.0,
                "source": "NSE + Upstox"
            })

        return dividends

    def enrich_with_upstox(self, dividends: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich dividend stocks with live price and yield data from Upstox."""
        if not dividends:
            return dividends

        # 1. Build list of instrument keys for Upstox quote query
        instrument_keys = []
        for d in dividends:
            isin = d.get("isin")
            if isin and isin != "-":
                instrument_keys.append(f"NSE_EQ|{isin}")

        if not instrument_keys:
            return dividends

        # Fetch quotes and LTP from Upstox
        quotes_map = self.upstox.get_quotes(instrument_keys)
        ltp_map = self.upstox.get_ltp(instrument_keys) if not quotes_map else {}

        for d in dividends:
            isin = d.get("isin", "")
            key = f"NSE_EQ|{isin}"
            symbol_key = f"NSE_EQ:{d['symbol']}"

            quote = quotes_map.get(key) or quotes_map.get(symbol_key) or quotes_map.get(isin)
            if quote:
                ltp = float(quote.get("last_price", 0.0))
                net_change = float(quote.get("net_change", 0.0))
                close = quote.get("ohlc", {}).get("close", ltp)
                pct_change = round(((net_change / close) * 100), 2) if close else 0.0
                d["ltp"] = ltp
                d["net_change"] = net_change
                d["day_change_percent"] = pct_change
            elif key in ltp_map or isin in ltp_map or symbol_key in ltp_map:
                ltp = float(ltp_map.get(key) or ltp_map.get(isin) or ltp_map.get(symbol_key) or 0.0)
                d["ltp"] = ltp

        # 2. Automated high-speed price fallback for any stocks unmapped in Upstox
        missing_stocks = [d for d in dividends if d.get("ltp", 0.0) <= 0 and d.get("symbol")]
        if missing_stocks:
            try:
                import yfinance as yf
                tickers_str = " ".join([f"{d['symbol']}.NS" for d in missing_stocks])
                yf_tickers = yf.Tickers(tickers_str)
                for d in missing_stocks:
                    sym = d["symbol"]
                    t = yf_tickers.tickers.get(f"{sym}.NS")
                    if t:
                        try:
                            price = t.fast_info.last_price
                            if price and price > 0:
                                prev_close = t.fast_info.previous_close or price
                                chg = round(price - prev_close, 2)
                                pct = round((chg / prev_close) * 100, 2) if prev_close else 0.0
                                d["ltp"] = round(float(price), 2)
                                d["net_change"] = chg
                                d["day_change_percent"] = pct
                                d["source"] = "NSE + Exchange Quote"
                        except Exception as e:
                            logger.warning(f"Price fallback error for {sym}: {e}")
            except Exception as e:
                logger.warning(f"Error in price fallback: {e}")

        # 3. Calculate Annual Dividends Per Share & Dividend Yield
        # Formula: Dividend Yield = (Annual Dividends Per Share / Price Per Share) * 100
        valid_symbols = list({d["symbol"] for d in dividends if d.get("symbol") and d.get("symbol") != "-"})
        annual_div_map = {}
        if valid_symbols:
            try:
                import yfinance as yf
                tickers_str = " ".join([f"{s}.NS" for s in valid_symbols])
                yf_tickers = yf.Tickers(tickers_str)
                one_year_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=365)

                for sym in valid_symbols:
                    t = yf_tickers.tickers.get(f"{sym}.NS")
                    sum_1y = 0.0
                    if t:
                        try:
                            divs = t.dividends
                            if divs is not None and not divs.empty:
                                divs_1y = divs[divs.index >= one_year_ago]
                                if not divs_1y.empty:
                                    sum_1y = float(divs_1y.sum())
                        except Exception:
                            pass
                    annual_div_map[sym] = round(sum_1y, 2)
            except Exception as e:
                logger.warning(f"Error fetching historical dividends for yield: {e}")

        for d in dividends:
            sym = d.get("symbol")
            curr_div = float(d.get("dividend_amount", 0.0) or 0.0)
            hist_1y = annual_div_map.get(sym, 0.0)

            # Compute Annual Dividends Per Share:
            # Trailing 12 months + newly declared dividend if it's a special or higher interim event
            if hist_1y > 0:
                if curr_div > hist_1y:
                    annual_div = round(hist_1y + curr_div, 2)
                else:
                    annual_div = round(hist_1y, 2)
            elif curr_div > 0:
                annual_div = round(curr_div, 2)
            else:
                annual_div = 0.0

            d["annual_dividend"] = annual_div

            # Formula: Dividend Yield = (Annual Dividends Per Share / Price Per Share) * 100
            ltp = float(d.get("ltp", 0.0) or 0.0)
            if ltp > 0 and annual_div > 0:
                d["dividend_yield"] = round((annual_div / ltp) * 100, 2)
            else:
                d["dividend_yield"] = 0.0

        return dividends

    def get_all_dividends(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Fetch all dividends using cache if valid, or fresh from sources."""
        # Check cache if not forcing refresh
        if not force_refresh and CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                    cached_time = cache_data.get("timestamp", 0)
                    if (time.time() - cached_time) < CACHE_TTL:
                        cached_divs = cache_data.get("dividends", [])
                        return isin_resolver.enrich_records(cached_divs)
            except Exception as e:
                logger.warning(f"Error reading dividend cache: {e}")

        # Fetch fresh data from both formal calendar and real-time board declarations
        raw_actions = self.fetch_exchange_actions(days_back=15, days_forward=100)
        parsed = self.parse_dividends(raw_actions)
        breaking = self.fetch_live_announcements(days_back=45)

        # Merge breaking announcements with formal calendar
        parsed_by_sym = {d["symbol"]: d for d in parsed if d.get("is_upcoming")}
        for b in breaking:
            sym = b["symbol"]
            if sym not in parsed_by_sym:
                parsed.append(b)
                parsed_by_sym[sym] = b
            else:
                existing = parsed_by_sym[sym]
                # Upgrade dividend amount if announcement has the newly approved board figure
                if existing.get("dividend_amount", 0.0) <= 0 and b.get("dividend_amount", 0.0) > 0:
                    existing["dividend_amount"] = b["dividend_amount"]
                    existing["subject"] = b["subject"]
                    existing["dividend_type"] = b["dividend_type"]
                # Upgrade dates if calendar had placeholder
                if (not existing.get("record_date") or existing.get("record_date") == "-") and b.get("record_date"):
                    existing["record_date"] = b["record_date"]
                    existing["record_date_formatted"] = b["record_date_formatted"]

        parsed = isin_resolver.enrich_records(parsed)
        enriched = self.enrich_with_upstox(parsed)

        # Sort: upcoming first by days_remaining ascending, then past
        enriched.sort(key=lambda x: (
            0 if x.get("is_upcoming") else 1,
            x.get("days_remaining") if x.get("days_remaining") is not None else 999
        ))

        # Save to cache
        try:
            cache_payload = {
                "timestamp": time.time(),
                "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_count": len(enriched),
                "dividends": enriched
            }
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache_payload, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving dividend cache: {e}")

        return enriched

    def filter_by_timeframe(self, dividends: List[Dict[str, Any]], timeframe: Optional[Any] = None) -> List[Dict[str, Any]]:
        """
        Filter dividends by timeframe:
        - 5: within 5 days
        - 10: within 10 days
        - 20: within 20 days
        - 30: within 30 days
        - 45: within 45 days
        - 60: within 60 days
        - 75: within 75 days
        - 90: within 90 days
        - 'all': all upcoming dividends (days_remaining >= 0)
        - 'recent': past dividends (days_remaining < 0)
        """
        if not timeframe or timeframe in ("all", "upcoming"):
            return [d for d in dividends if d.get("is_upcoming")]
        
        if timeframe == "recent":
            return [d for d in dividends if not d.get("is_upcoming")]

        try:
            tf_days = int(timeframe)
            return [
                d for d in dividends
                if d.get("days_remaining") is not None and 0 <= d["days_remaining"] <= tf_days
            ]
        except (ValueError, TypeError):
            return dividends

    def get_statistics(self, dividends: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute summary KPI statistics across all time frames."""
        upcoming = [d for d in dividends if d.get("is_upcoming")]
        in_5d = [d for d in upcoming if d.get("within_5_days")]
        in_10d = [d for d in upcoming if d.get("within_10_days")]
        in_20d = [d for d in upcoming if d.get("within_20_days")]
        in_30d = [d for d in upcoming if d.get("within_30_days")]
        in_45d = [d for d in upcoming if d.get("within_45_days")]
        in_60d = [d for d in upcoming if d.get("within_60_days")]
        in_75d = [d for d in upcoming if d.get("within_75_days")]
        in_90d = [d for d in upcoming if d.get("within_90_days")]

        yields = [d["dividend_yield"] for d in upcoming if d.get("dividend_yield", 0) > 0]
        avg_yield = round(sum(yields) / len(yields), 2) if yields else 0.0

        highest_yield_stock = None
        if upcoming:
            stocks_with_yield = sorted(upcoming, key=lambda x: x.get("dividend_yield", 0), reverse=True)
            if stocks_with_yield and stocks_with_yield[0].get("dividend_yield", 0) > 0:
                highest_yield_stock = stocks_with_yield[0]

        return {
            "total_upcoming": len(upcoming),
            "count_5_days": len(in_5d),
            "count_10_days": len(in_10d),
            "count_20_days": len(in_20d),
            "count_30_days": len(in_30d),
            "count_45_days": len(in_45d),
            "count_60_days": len(in_60d),
            "count_75_days": len(in_75d),
            "count_90_days": len(in_90d),
            "average_yield": avg_yield,
            "highest_yield_stock": highest_yield_stock
        }

    def fetch_symbol_corporate_actions(self, symbol: str) -> List[Dict[str, Any]]:
        """Fetch historical corporate actions for a specific symbol directly from exchange."""
        if not symbol:
            return []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-actions",
        }
        session = requests.Session()
        session.headers.update(headers)
        try:
            session.get("https://www.nseindia.com", timeout=5)
            url = f"https://www.nseindia.com/api/corporates-corporateActions?index=equities&symbol={symbol.upper()}"
            resp = session.get(url, timeout=7)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.warning(f"Error fetching symbol corporate actions for {symbol}: {e}")
        return []

    def get_complete_dividend_history(self, identifier: str) -> List[Dict[str, Any]]:
        """Fetch complete multi-year dividend track record with authentic Record Dates and Ex-Dates."""
        if not identifier:
            return []

        isin = identifier
        symbol = identifier
        if identifier.startswith("INE"):
            for s, i in isin_resolver._mapping.items():
                if i == identifier:
                    symbol = s
                    break
        else:
            isin = isin_resolver.get_isin(identifier) or ""
            symbol = identifier

        history_records = []
        seen_dates = set()

        # 1. Fetch official exchange corporate action history with full Record Dates
        if symbol:
            try:
                actions = self.fetch_symbol_corporate_actions(symbol)
                for item in actions:
                    subj = item.get("subject", "")
                    if "DIV" in subj.upper():
                        ex_str = item.get("exDate", "").strip()
                        rec_str = item.get("recDate", "").strip()
                        ex_dt = self._parse_date(ex_str)
                        rec_dt = self._parse_date(rec_str)

                        ex_fmt = ex_dt.strftime("%d %b %Y") if ex_dt else ex_str
                        rec_fmt = rec_dt.strftime("%d %b %Y") if rec_dt else (rec_str or "-")
                        amt = self._extract_amount(subj)
                        div_type = self._classify_dividend_type(subj)

                        d_key = ex_dt.isoformat() if ex_dt else ex_str
                        if d_key and d_key not in seen_dates:
                            seen_dates.add(d_key)
                            history_records.append({
                                "name": div_type,
                                "date_key": d_key,
                                "expiry_date": ex_fmt,
                                "amount": amt,
                                "record_date": rec_fmt
                            })
            except Exception as e:
                logger.warning(f"Error processing exchange history for {symbol}: {e}")

        # 2. Supplementary check via broker corporate actions if available
        if isin and self.upstox.is_configured():
            try:
                broker_actions = self.upstox.get_corporate_actions(isin)
                for a in broker_actions:
                    if "DIVIDEND" in str(a.get("name", "")).upper():
                        dt_str = a.get("expiry_date") or ""
                        amt = float(a.get("amount") or 0.0)
                        rec_date = "-"
                        if a.get("event_details") and isinstance(a.get("event_details"), list):
                            rec_obj = next((d for d in a["event_details"] if "record" in str(d.get("name", "")).lower()), None)
                            if rec_obj:
                                rec_date = rec_obj.get("value", "-")

                        dt_key = dt_str
                        try:
                            p_dt = datetime.datetime.strptime(dt_str, "%d %b %Y").date()
                            dt_key = p_dt.isoformat()
                        except Exception:
                            pass

                        # If not already recorded or if existing record lacked record date
                        existing = next((r for r in history_records if r.get("date_key") == dt_key), None)
                        if existing:
                            if (not existing.get("record_date") or existing.get("record_date") == "-") and rec_date != "-":
                                existing["record_date"] = rec_date
                        elif dt_key not in seen_dates:
                            seen_dates.add(dt_key)
                            history_records.append({
                                "name": a.get("name", "Dividend"),
                                "date_key": dt_key,
                                "expiry_date": dt_str,
                                "amount": amt,
                                "record_date": rec_date
                            })
            except Exception as e:
                logger.warning(f"Error fetching broker actions for {isin}: {e}")

        # 3. Supplemental multi-year historical pricing check via yfinance (for older records)
        if symbol:
            try:
                import yfinance as yf
                ticker = yf.Ticker(f"{symbol}.NS")
                div_series = ticker.dividends
                if div_series is not None and not div_series.empty:
                    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=365 * 5)
                    recent = div_series[div_series.index >= cutoff]
                    for dt, amt in recent.items():
                        d_obj = dt.date()
                        d_iso = d_obj.isoformat()

                        # Deduplicate within +/- 3 day window
                        is_seen = False
                        for sd in seen_dates:
                            try:
                                sd_obj = datetime.date.fromisoformat(sd)
                                if abs((sd_obj - d_obj).days) <= 3:
                                    is_seen = True
                                    break
                            except Exception:
                                pass

                        if not is_seen:
                            # In Indian settlement, record date is Ex-Date or next business day
                            calc_rec = d_obj.strftime("%d %b %Y")
                            history_records.append({
                                "name": "Dividend",
                                "date_key": d_iso,
                                "expiry_date": d_obj.strftime("%d %b %Y"),
                                "amount": round(float(amt), 2),
                                "record_date": calc_rec
                            })
                            seen_dates.add(d_iso)
            except Exception as e:
                logger.warning(f"Error fetching historical series for {symbol}: {e}")

        # Sort descending by ex-date
        history_records.sort(key=lambda x: x.get("date_key", ""), reverse=True)
        return history_records
