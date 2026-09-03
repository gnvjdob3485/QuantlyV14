"""
Financial Modeling Prep (FMP) data provider — hybrid version.

Uses FMP's free Basic plan (250 calls/day) for what it supports:
  - Real-time quotes, company profile, financial statements, ratios
  - Sector/market data for the home page

Falls back to yfinance for:
  - Historical price data (charts)
  - News
  - Technicals (computed from price history)

If yfinance is unreachable (e.g. on Render), these features degrade gracefully
instead of crashing the whole page.

API key: set FMP_API_KEY env var (Render) or write to fmp_key.txt (local).
"""

import os
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List


BASE = "https://financialmodelingprep.com"
_cache: Dict[str, tuple] = {}
_TTL = 600  # seconds


def get_api_key() -> Optional[str]:
    key = os.environ.get('FMP_API_KEY', '').strip()
    if key:
        return key
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fmp_key.txt')) as f:
            return f.read().strip() or None
    except Exception:
        return None


def _request(path: str, params: dict):
    key = get_api_key()
    if not key:
        raise RuntimeError("FMP_API_KEY is not set")
    import requests as _requests
    url = f"{BASE}{path}"
    params = dict(params or {})
    params['apikey'] = key
    for attempt in range(2):
        try:
            r = _requests.get(url, params=params, timeout=20)
            if r.status_code == 429:
                raise RuntimeError("rate limited")
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and (data.get('Error Message') or data.get('error')):
                raise RuntimeError(str(data.get('Error Message') or data.get('error')))
            return data
        except _requests.HTTPError as e:
            if attempt == 0 and r.status_code in (429, 500, 502, 503):
                time.sleep(2)
                continue
            raise
        except RuntimeError:
            if attempt == 0:
                time.sleep(2)
                continue
            raise


def _cached(key: str, ttl: int, func):
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    result = func()
    _cache[key] = (now, result)
    return result


def _fnum(v, default=None):
    try:
        if v is None or v == '':
            return default
        return float(v)
    except Exception:
        return default


# ─── Profile ────────────────────────────────────────────────
def _profile(ticker: str) -> dict:
    def load():
        data = _request("/stable/profile", {'symbol': ticker})
        return data[0] if isinstance(data, list) and data else {}
    return _cached(f'p_{ticker.upper()}', _TTL, load)


# ─── Quote ──────────────────────────────────────────────────
def get_quote(ticker: str) -> dict:
    def load():
        data = _request("/stable/quote", {'symbol': ticker})
        q = data[0] if isinstance(data, list) and data else {}
        if not q:
            raise RuntimeError("no quote")
        price = _fnum(q.get('price')) or _fnum(q.get('previousClose'))
        change_pct = _fnum(q.get('changesPercentage'))
        return {
            'ticker': ticker.upper(),
            'price': round(price, 2) if price else None,
            'change': _fnum(q.get('change')),
            'change_pct': round(change_pct, 2) if change_pct is not None else change_pct,
            'currency': q.get('currency', 'USD'),
            'exchange': q.get('exchange'),
            'market_cap': _fnum(q.get('marketCap')),
            'market_state': 'open',
            'quoteType': 'EQUITY',
        }
    try:
        return _cached(f'q_{ticker.upper()}', 60, load)
    except Exception as e:
        return {'ticker': ticker.upper(), 'name': ticker.upper(), 'price': None, 'error': str(e)}


def enrich_profile(q: dict, ticker: str) -> dict:
    try:
        p = _profile(ticker)
        q['name'] = p.get('companyName') or q.get('ticker') or ticker
        q['long_name'] = p.get('companyName')
        q['sector'] = p.get('sector')
        q['industry'] = p.get('industry')
        q['description'] = p.get('description')
        q['website'] = p.get('website')
        q['exchange'] = p.get('exchange') or q.get('exchange')
        q['currency'] = p.get('currency') or q.get('currency', 'USD')
        q['market_cap'] = _fnum(p.get('marketCap')) or q.get('market_cap')
        q['ceo'] = p.get('ceo')
        q['phone'] = p.get('phone')
        q['address'] = p.get('address')
    except Exception:
        q.setdefault('name', ticker.upper())
    return q


# ─── Price history (from yfinance — FMP free doesn't have this) ──
def get_price_history(ticker: str, timeframe: str = '1Y') -> dict:
    try:
        from research_data import DataIntelligence
        return DataIntelligence._yf_history(ticker, timeframe)
    except Exception as e:
        return {'error': str(e)}


# ─── Statistics ─────────────────────────────────────────────
def get_statistics(ticker: str) -> dict:
    try:
        q = get_quote(ticker)
        p = _profile(ticker)
        r = _ratios(ticker)
        return {
            'market_cap': _fnum(p.get('marketCap')) or _fnum(q.get('market_cap')),
            'beta': _fnum(p.get('beta')),
            'trailing_pe': _fnum(q.get('pe')),
            'forward_pe': _fnum(p.get('forwardPE')) or _fnum(p.get('forwardPe')),
            'price_to_sales': _fnum(r.get('priceToSalesRatio')),
            'price_to_book': _fnum(r.get('priceToBookRatio')),
            'eps': _fnum(q.get('eps')),
            'eps_forward': _fnum(p.get('forwardEps')),
            'dividend_yield': _fnum(r.get('dividendYield')),
            'payout_ratio': _fnum(r.get('payoutRatio')),
            'revenue': _fnum(p.get('revenue')) or _fnum(p.get('revenueTtm')),
            'revenue_growth': _fnum(r.get('revenueGrowth')),
            'gross_margins': _fnum(r.get('grossProfitMargin')),
            'operating_margins': _fnum(r.get('operatingProfitMargin')),
            'profit_margins': _fnum(r.get('netProfitMargin')),
            'ebitda': _fnum(p.get('ebitda')),
            'free_cashflow': _fnum(p.get('freeCashFlowPerShare')),
            'peg_ratio': _fnum(r.get('pegRatio')),
            'enterprise_value': _fnum(p.get('enterpriseValue')),
            'dividend_rate': None,
            'operating_cashflow': _fnum(p.get('operatingCashFlowPerShare')),
        }
    except Exception as e:
        return {'error': str(e)}


def _ratios(ticker: str) -> dict:
    def load():
        data = _request("/stable/ratios", {'symbol': ticker, 'period': 'annual', 'limit': 1})
        return data[0] if isinstance(data, list) and data else {}
    return _cached(f'r_{ticker.upper()}', _TTL, load)


# ─── Valuation ──────────────────────────────────────────────
def get_valuation(ticker: str) -> dict:
    try:
        s = get_statistics(ticker)
        q = get_quote(ticker)
        p = _profile(ticker)
        price = _fnum(q.get('price'))
        pe = _fnum(q.get('pe'))
        eps = _fnum(q.get('eps'))
        return {
            'pe_trailing': pe,
            'pe_forward': _fnum(p.get('forwardPE')) or _fnum(p.get('forwardPe')),
            'price_to_sales': s.get('price_to_sales'),
            'price_to_book': s.get('price_to_book'),
            'peg': s.get('peg_ratio'),
            'market_cap': s.get('market_cap'),
            'price': price,
            'eps': eps,
            'ev_to_ebitda': (_fnum(p.get('enterpriseValue')) / _fnum(p.get('ebitda'))
                             if _fnum(p.get('ebitda')) else None),
        }
    except Exception as e:
        return {'error': str(e)}


# ─── Financials ─────────────────────────────────────────────
def get_financials(ticker: str) -> dict:
    def load():
        r = _ratios(ticker)
        data = _request("/stable/income-statement",
                        {'symbol': ticker, 'period': 'annual', 'limit': 2})
        inc = data[0] if isinstance(data, list) and data else {}
        prev = data[1] if isinstance(data, list) and len(data) > 1 else {}
        rev = _fnum(inc.get('revenue'))
        prev_rev = _fnum(prev.get('revenue'))
        growth = ((rev / prev_rev) - 1) * 100 if rev and prev_rev else None
        return {
            'revenue': rev,
            'revenue_growth': round(growth, 2) if growth is not None else None,
            'gross_margin': _fnum(r.get('grossProfitMargin')),
            'operating_margin': _fnum(r.get('operatingProfitMargin')),
            'net_margin': _fnum(r.get('netProfitMargin')),
            'net_income': _fnum(inc.get('netIncome')),
            'eps': _fnum(inc.get('eps')),
            'eps_diluted': _fnum(inc.get('epsDiluted')),
            'ebitda': _fnum(inc.get('ebitda')),
            'gross_profit': _fnum(inc.get('grossProfit')),
            'operating_income': _fnum(inc.get('operatingIncome')),
            'shares_outstanding': _fnum(inc.get('weightedAverageShsOut')),
            'period': inc.get('calendarYear'),
        }
    try:
        return _cached(f'f_{ticker.upper()}', _TTL, load)
    except Exception as e:
        return {'error': str(e)}


# ─── Technicals (computed from yfinance history) ────────────
def get_technicals(ticker: str) -> dict:
    try:
        from research_data import DataIntelligence
        return DataIntelligence._yf_technicals(ticker)
    except Exception as e:
        return {'error': str(e)}


# ─── News (from yfinance) ──────────────────────────────────
def get_news(ticker: str) -> List[dict]:
    try:
        from research_data import DataIntelligence
        return DataIntelligence._yf_news(ticker)
    except Exception:
        return []


# ─── Analyst sentiment (from profile data) ──────────────────
def get_analyst_sentiment(ticker: str) -> dict:
    def load():
        try:
            p = _profile(ticker)
            return {
                'recommendation_mean': _fnum(p.get('recommendationMean')),
                'recommendation_key': p.get('recommendationKey'),
                'target_mean': _fnum(p.get('targetMeanPrice')),
                'target_high': _fnum(p.get('targetHighPrice')),
                'target_low': _fnum(p.get('targetLowPrice')),
                'number_of_analysts': _fnum(p.get('numberOfAnalystOpinions')),
            }
        except Exception:
            return {}
    return _cached(f'an_{ticker.upper()}', _TTL, load)


# ─── Name ───────────────────────────────────────────────────
def get_name(ticker: str) -> str:
    try:
        p = _profile(ticker)
        return p.get('companyName') or ticker.upper()
    except Exception:
        return ticker.upper()


# ─── Validity check ─────────────────────────────────────────
def is_valid(ticker: str) -> bool:
    try:
        q = _request("/stable/quote", {'symbol': ticker})
        return isinstance(q, list) and bool(q)
    except Exception:
        return False


# ─── Competitors ────────────────────────────────────────────
def get_competitors(ticker: str) -> List[dict]:
    """Use FMP profile sector to find peers, then batch lookup."""
    try:
        p = _profile(ticker)
        sector = p.get('sector', '')
        industry = p.get('industry', '')
        sector_map = {
            'Technology': ['MSFT', 'AAPL', 'GOOGL', 'META', 'AMD', 'CRM'],
            'Semiconductors': ['AMD', 'INTC', 'NVDA', 'QCOM', 'AVGO', 'MU', 'TSM'],
            'Communication Services': ['GOOGL', 'META', 'NFLX', 'DIS'],
            'Financial Services': ['JPM', 'BAC', 'WFC', 'GS', 'MS', 'V', 'MA'],
            'Consumer Defensive': ['KO', 'PEP', 'PG', 'WMT', 'COST'],
            'Consumer Cyclical': ['AMZN', 'TSLA', 'HD', 'MCD', 'NKE'],
            'Healthcare': ['JNJ', 'PFE', 'UNH', 'MRK', 'LLY'],
            'Energy': ['XOM', 'CVX', 'COP', 'SLB'],
            'Industrials': ['CAT', 'BA', 'GE', 'HON', 'UPS'],
            'Utilities': ['NEE', 'DUK', 'SO', 'AEP'],
        }
        peers = sector_map.get(sector, [])
        if industry and 'semiconductor' in industry.lower():
            peers = sector_map.get('Semiconductors', peers)
        peers = [p for p in peers if p != ticker.upper()][:6]
        result = []
        for peer in peers:
            try:
                q = get_quote(peer)
                if q.get('price') is not None:
                    result.append({
                        'ticker': peer,
                        'name': q.get('name', peer),
                        'price': q.get('price'),
                        'change_pct': q.get('change_pct'),
                        'market_cap': q.get('market_cap'),
                    })
            except Exception:
                continue
        return result
    except Exception:
        return []


# ─── Holders ────────────────────────────────────────────────
def get_holders(ticker: str) -> dict:
    try:
        p = _profile(ticker)
        return {
            'insiders_pct': _fnum(p.get('volAvg')),
            'institutions_pct': _fnum(p.get('ownedPercent')),
        }
    except Exception:
        return {}


# ─── Period returns ─────────────────────────────────────────
def get_period_returns(ticker: str) -> dict:
    try:
        q = get_quote(ticker)
        p = _profile(ticker)
        price = _fnum(q.get('price'))
        out = {}
        if price and _fnum(q.get('previousClose')):
            out['1D'] = round((price / _fnum(q.get('previousClose')) - 1) * 100, 2)
        return out
    except Exception:
        return {}


# ─── Macro snapshot ─────────────────────────────────────────
def get_macro_snapshot() -> dict:
    def load():
        idx = {'^GSPC': 'S&P 500', '^IXIC': 'NASDAQ', '^DJI': 'Dow Jones'}
        result = []
        for sym, name in idx.items():
            try:
                data = _request("/stable/quote", {'symbol': sym})
                row = data[0] if isinstance(data, list) and data else {}
                result.append({
                    'ticker': name,
                    'price': _fnum(row.get('price')),
                    'change_pct': _fnum(row.get('changesPercentage')),
                })
            except Exception:
                continue
        return {'indices': result}
    try:
        return _cached('macro', 300, load)
    except Exception as e:
        return {'error': str(e)}
