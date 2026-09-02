"""
Research Data Intelligence Layer.

Gathers and normalises market data, fundamentals, valuation, technicals, news
and macro data from real data sources (currently Yahoo Finance via yfinance).

This is the MODULAR data abstraction layer: every data access for the research
platform flows through this module. A different provider can be plugged in by
subclassing DataIntelligenceProvider without changing the rest of the app.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import math
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List


# In-memory cache for individual data lookups so we don't hammer Yahoo Finance
# with duplicate requests (which triggers 429 rate-limiting). Each method is
# cached by (ticker, param) with a TTL. Errors are not cached so a transient
# failure can be retried on the next request.
_data_cache = {}
_CACHE_TTL = 300  # seconds


def _cached(key, ttl, func):
    now = time.time()
    hit = _data_cache.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    result = func()
    # cache only successful results (dicts without 'error', non-empty lists)
    if not (isinstance(result, dict) and result.get('error')):
        _data_cache[key] = (now, result)
    return result


def _memo(method_name, ttl=_CACHE_TTL):
    """Decorator for classmethods that caches the raw return value."""
    def deco(fn):
        def wrapper(cls, *args, **kwargs):
            key = (method_name, args, tuple(sorted(kwargs.items())))
            return _cached(key, ttl, lambda: fn(cls, *args, **kwargs))
        return wrapper
    return deco


class DataIntelligence:
    """Collects and normalises all data needed for an asset research dashboard."""

    TIMEFRAMES = {
        '1D': {'period': '5d', 'interval': '1d'},
        '1W': {'period': '1mo', 'interval': '1d'},
        '1M': {'period': '3mo', 'interval': '1d'},
        '6M': {'period': '6mo', 'interval': '1d'},
        '1Y': {'period': '1y', 'interval': '1d'},
        '5Y': {'period': '5y', 'interval': '1wk'},
        'MAX': {'period': 'max', 'interval': '1mo'},
    }

    @staticmethod
    def _safe_float(val, default=None):
        try:
            v = float(val)
            if math.isnan(v) or math.isinf(v):
                return default
            return v
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _get_ticker(ticker: str) -> yf.Ticker:
        return yf.Ticker(ticker)

    # ─── QUOTE / PRICE ───
    @classmethod
    @_memo('is_valid', ttl=60)
    def is_valid(cls, ticker: str) -> bool:
        """Cheap existence check. One minimal history call; returns False quickly
        for invalid tickers without running the heavy research pipeline."""
        try:
            tk = cls._get_ticker(ticker)
            hist = tk.history(period='5d', interval='1d')
            if hist is None or hist.empty:
                return False
            # Some providers return a full frame with NaN when ticker is bogus
            if len(hist) and all(v is None or (v != v) for v in hist['Close']):
                return False
            return True
        except Exception:
            return False

    @classmethod
    @_memo('get_quote', ttl=120)
    def get_quote(cls, ticker: str) -> dict:
        try:
            tk = cls._get_ticker(ticker)
            info = tk.info or {}
            hist = tk.history(period='5d', interval='1d')
            last_close = cls._safe_float(hist['Close'].iloc[-1]) if hist is not None and len(hist) else None
            prev_close = cls._safe_float(hist['Close'].iloc[-2]) if hist is not None and len(hist) > 1 else None

            price = cls._safe_float(info.get('currentPrice')) or last_close
            change = None
            change_pct = None
            if price and prev_close:
                change = price - prev_close
                change_pct = (change / prev_close) * 100

            market_state = info.get('marketState')
            state_label = 'open' if market_state == 'REGULAR' else 'closed'

            return {
                'ticker': ticker,
                'name': info.get('shortName') or info.get('longName') or ticker,
                'long_name': info.get('longName'),
                'price': round(price, 2) if price else None,
                'change': round(change, 2) if change is not None else None,
                'change_pct': round(change_pct, 2) if change_pct is not None else None,
                'currency': info.get('currency', 'USD'),
                'exchange': info.get('exchange'),
                'market_state': state_label,
                'market_cap': info.get('marketCap'),
                'sector': info.get('sector'),
                'industry': info.get('industry'),
                'quoteType': info.get('quoteType', 'EQUITY'),
            }
        except Exception:
            return {'ticker': ticker, 'name': ticker, 'price': None, 'error': 'Could not fetch quote'}

    # ─── PRICE HISTORY ───
    @classmethod
    @_memo('get_price_history', ttl=120)
    def get_price_history(cls, ticker: str, timeframe: str = '1Y') -> dict:
        config = cls.TIMEFRAMES.get(timeframe)
        if config is None:
            return {'error': f'Unknown timeframe {timeframe}'}
        try:
            tk = cls._get_ticker(ticker)
            hist = tk.history(period=config['period'], interval=config['interval'], auto_adjust=True)
            if hist is None or hist.empty:
                return {'error': 'No price data available'}

            hist = hist.dropna(subset=['Close'])
            closes = hist['Close'].values
            dates = [d.strftime('%Y-%m-%d') for d in hist.index]

            return {
                'timeframe': timeframe,
                'dates': dates,
                'prices': [round(float(c), 2) for c in closes],
                'highs': [round(float(h), 2) for h in hist['High'].values],
                'lows': [round(float(l), 2) for l in hist['Low'].values],
                'volumes': [int(v) for v in hist['Volume'].values],
            }
        except Exception as e:
            return {'error': str(e)}

    # ─── PERIOD RETURNS ───
    @classmethod
    def get_period_returns(cls, ticker: str) -> dict:
        try:
            tk = cls._get_ticker(ticker)
            info = tk.info or {}
            out = {}
            for period, abbrev in [('1d', '1D'), ('1mo', '1M'), ('6mo', '6M'), ('1y', '1Y')]:
                key = {1: '1D', 2: '1W', 1: '1M'}.get(period, abbrev)
            # Use info where available, fall back to history
            if info:
                mapping = {
                    '5y': '5Y', '10y': '10Y', 'max': 'MAX',
                }
            for key, val in info.items():
                if key in ('52WeekChange',):
                    out['1Y'] = cls._safe_float(val * 100) if val is not None else None
            return out
        except Exception:
            return {}

    # ─── STATISTICS ───
    @classmethod
    @_memo('get_statistics', ttl=600)
    def get_statistics(cls, ticker: str) -> dict:
        try:
            tk = cls._get_ticker(ticker)
            info = tk.info or {}

            def val(info_key):
                return cls._safe_float(info.get(info_key))

            return {
                'market_cap': cls._safe_float(info.get('marketCap')),
                'beta': val('beta'),
                'trailing_pe': val('trailingPE'),
                'forward_pe': val('forwardPE'),
                'peg_ratio': val('pegRatio'),
                'price_to_sales': val('priceToSalesTrailing12Months'),
                'price_to_book': val('priceToBook'),
                'enterprise_value': cls._safe_float(info.get('enterpriseValue')),
                'eps': val('trailingEps'),
                'eps_forward': val('forwardEps'),
                'dividend_yield': cls._safe_float(info.get('dividendYield')),
                'dividend_rate': cls._safe_float(info.get('dividendRate')),
                'payout_ratio': cls._safe_float(info.get('payoutRatio')),
                'revenue': val('totalRevenue'),
                'revenue_growth': val('revenueGrowth'),
                'gross_margins': val('grossMargins'),
                'operating_margins': val('operatingMargins'),
                'profit_margins': val('profitMargins'),
                'ebitda': cls._safe_float(info.get('EBITDA')),
                'free_cashflow': val('freeCashflow'),
                'operating_cashflow': val('operatingCashflow'),
                'total_debt': cls._safe_float(info.get('totalDebt')),
                'total_cash': cls._safe_float(info.get('totalCash')),
                'debt_to_equity': val('debtToEquity'),
                'return_on_equity': val('returnOnEquity'),
                'return_on_assets': val('returnOnAssets'),
                'current_ratio': val('currentRatio'),
                'quick_ratio': val('quickRatio'),
                'book_value': val('bookValue'),
                '52_week_high': cls._safe_float(info.get('fiftyTwoWeekHigh')),
                '52_week_low': cls._safe_float(info.get('fiftyTwoWeekLow')),
                'recommendation_mean': cls._safe_float(info.get('recommendationMean')),
                'recommendation_key': info.get('recommendationKey'),
                'target_mean': cls._safe_float(info.get('targetMeanPrice')),
                'target_high': cls._safe_float(info.get('targetHighPrice')),
                'target_low': cls._safe_float(info.get('targetLowPrice')),
                'number_of_analysts': cls._safe_float(info.get('numberOfAnalystOpinions')),
                'float_shares': cls._safe_float(info.get('floatShares')),
                'shares_outstanding': cls._safe_float(info.get('sharesOutstanding')),
                'insider_holdings': cls._safe_float(info.get('heldPercentInsiders')),
                'institution_holdings': cls._safe_float(info.get('heldPercentInstitutions')),
                'short_ratio': cls._safe_float(info.get('shortRatio')),
            }
        except Exception as e:
            return {'error': str(e)}

    # ─── TECHNICALS ───
    @classmethod
    @_memo('get_technicals', ttl=300)
    def get_technicals(cls, ticker: str) -> dict:
        try:
            tk = cls._get_ticker(ticker)
            hist = tk.history(period='1y', interval='1d', auto_adjust=True)
            if hist is None or hist.empty or len(hist) < 30:
                return {'error': 'Not enough price data for technicals'}

            closes = hist['Close']
            current = closes.iloc[-1]

            def rsi(series, period=14):
                delta = series.diff()
                gain = delta.where(delta > 0, 0.0).rolling(window=period).mean()
                loss = -delta.where(delta < 0, 0.0).rolling(window=period).mean()
                rs = gain / (loss.replace(0, np.nan))
                rsi_val = 100 - (100 / (1 + rs))
                return rsi_val

            sma20 = closes.rolling(20).mean().iloc[-1]
            sma50 = closes.rolling(50).mean().iloc[-1]
            sma100 = closes.rolling(100).mean().iloc[-1]
            sma200 = closes.rolling(200).mean().iloc[-1]
            ema20 = closes.ewm(span=20, adjust=False).mean().iloc[-1]
            rsi_14 = rsi(closes).iloc[-1]

            # MACD
            ema12 = closes.ewm(span=12, adjust=False).mean()
            ema26 = closes.ewm(span=26, adjust=False).mean()
            macd = ema12 - ema26
            signal = macd.ewm(span=9, adjust=False).mean()
            macd_now = macd.iloc[-1]
            signal_now = signal.iloc[-1]
            macd_bullish = macd_now > signal_now

            # Volume
            vol_sma20 = hist['Volume'].rolling(20).mean().iloc[-1]
            vol_now = hist['Volume'].iloc[-1]
            vol_ratio = vol_now / vol_sma20 if vol_sma20 else None

            # 52-week range
            hi52 = closes.max()
            lo52 = closes.min()

            def pct(v):
                if v is None or not v:
                    return None
                return round(float((current / v - 1) * 100), 1)

            support = float(closes.tail(60).min())
            resistance = float(closes.tail(60).max())

            # Determine trend
            trend = 'Uptrend' if current > sma200 else 'Downtrend'
            if current > sma50 > sma200:
                trend = 'Strong uptrend'
            elif current < sma50 < sma200:
                trend = 'Strong downtrend'
            elif sma50 > sma200:
                trend = 'Uptrend'

            return {
                'current_price': round(float(current), 2),
                'sma20': round(float(sma20), 2),
                'sma50': round(float(sma50), 2),
                'sma100': round(float(sma100), 2),
                'sma200': round(float(sma200), 2),
                'ema20': round(float(ema20), 2),
                'price_vs_sma20': pct(sma20),
                'price_vs_sma50': pct(sma50),
                'price_vs_sma200': pct(sma200),
                'rsi': round(float(rsi_14), 1),
                'rsi_level': 'Overbought' if rsi_14 > 70 else ('Oversold' if rsi_14 < 30 else 'Neutral'),
                'macd': round(float(macd_now), 3),
                'macd_signal': round(float(signal_now), 3),
                'macd_bullish': macd_bullish,
                'volume_ratio': round(float(vol_ratio), 2) if vol_ratio else None,
                'trend': trend,
                '52w_high': round(float(hi52), 2),
                '52w_low': round(float(lo52), 2),
                '52w_position': round(float((current - lo52) / (hi52 - lo52) * 100), 1) if hi52 != lo52 else None,
                'support': round(float(support), 2),
                'resistance': round(float(resistance), 2),
                'volatility_1y': round(float(closes.pct_change().std() * np.sqrt(252) * 100), 2),
                'data_points': len(closes),
            }
        except Exception as e:
            return {'error': str(e)}

    # ─── VALUATION ───
    @classmethod
    @_memo('get_valuation', ttl=600)
    def get_valuation(cls, ticker: str) -> dict:
        try:
            tk = cls._get_ticker(ticker)
            info = tk.info or {}
            f_metrics = {
                'trailingPE': info.get('trailingPE'),
                'forwardPE': info.get('forwardPE'),
                'pegRatio': info.get('pegRatio'),
                'priceToSalesTrailing12Months': info.get('priceToSalesTrailing12Months'),
                'priceToBook': info.get('priceToBook'),
                'enterpriseToRevenue': info.get('enterpriseToRevenue'),
                'enterpriseToEbitda': info.get('enterpriseToEbitda'),
                'priceToBook': info.get('priceToBook'),
            }
            return {k: cls._safe_float(v) for k, v in f_metrics.items() if v is not None}
        except Exception as e:
            return {'error': str(e)}

    # ─── NEWS ───
    @classmethod
    @_memo('get_news', ttl=600)
    def get_news(cls, ticker: str) -> List[dict]:
        try:
            tk = cls._get_ticker(ticker)
            news = tk.news
            if not news:
                return []
            result = []
            for item in news[:12]:
                published = item.get('providerPublishTime')
                date = datetime.fromtimestamp(published).strftime('%Y-%m-%d') if published else None
                result.append({
                    'title': item.get('title'),
                    'publisher': item.get('publisher'),
                    'source': item.get('publisher'),
                    'date': date,
                    'type': item.get('type'),
                    'link': item.get('link'),
                    'summary': item.get('summary', ''),
                })
            return result
        except Exception:
            return []

    # ─── INCOME / BALANCE / CASHFLOW ───
    @classmethod
    @_memo('get_financials', ttl=600)
    def get_financials(cls, ticker: str) -> dict:
        try:
            tk = cls._get_ticker(ticker)
            info = tk.info or {}
            return {
                'revenue': cls._safe_float(info.get('totalRevenue')),
                'revenue_growth': cls._safe_float(info.get('revenueGrowth')),
                'gross_margin': cls._safe_float(info.get('grossMargins')),
                'operating_margin': cls._safe_float(info.get('operatingMargins')),
                'net_margin': cls._safe_float(info.get('profitMargins')),
                'eps': cls._safe_float(info.get('trailingEps')),
                'forward_eps': cls._safe_float(info.get('forwardEps')),
                'free_cashflow': cls._safe_float(info.get('freeCashflow')),
                'operating_cashflow': cls._safe_float(info.get('operatingCashflow')),
                'total_debt': cls._safe_float(info.get('totalDebt')),
                'total_cash': cls._safe_float(info.get('totalCash')),
                'roe': cls._safe_float(info.get('returnOnEquity')),
                'roa': cls._safe_float(info.get('returnOnAssets')),
                'dividend_yield': cls._safe_float(info.get('dividendYield')),
            }
        except Exception as e:
            return {'error': str(e)}

    # ─── MACRO ───
    @classmethod
    @_memo('get_macro_snapshot', ttl=120)
    def get_macro_snapshot(cls) -> dict:
        """Real recent macro proxies via index/ETF quotes. No fabricated data."""
        tickers = {
            '^GSPC': 'S&P 500', '^IXIC': 'NASDAQ', '^DJI': 'Dow Jones',
            '^FTSE': 'FTSE 100', '^GDAXI': 'DAX', '^N225': 'Nikkei 225',
            'BTC-USD': 'Bitcoin', 'GC=F': 'Gold', 'CL=F': 'Oil (WTI)',
            '^TNX': 'US 10Y Yield', '^VIX': 'VIX', 'DX-Y.NYB': 'US Dollar',
            'EURUSD=X': 'EUR/USD', 'GBPUSD=X': 'GBP/USD',
        }
        out = {}
        for sym, name in tickers.items():
            try:
                tk = yf.Ticker(sym)
                hist = tk.history(period='5d')
                if hist is not None and len(hist) >= 2:
                    last = hist['Close'].iloc[-1]
                    prev = hist['Close'].iloc[-2]
                    change = ((last - prev) / prev) * 100
                    out[sym] = {
                        'name': name, 'price': round(float(last), 2),
                        'change': round(float(change), 2),
                        'type': cls._classify_asset(name),
                    }
            except Exception:
                continue
        return out

    @staticmethod
    def _classify_asset(name: str) -> str:
        if name in ('S&P 500', 'NASDAQ', 'Dow Jones', 'FTSE 100', 'DAX', 'Nikkei 225'):
            return 'index'
        if name == 'Bitcoin':
            return 'crypto'
        if 'Gold' in name or 'Oil' in name:
            return 'commodity'
        if 'Yield' in name or 'Dollar' in name or '/USD' in name:
            return 'fx'
        if name == 'VIX':
            return 'volatility'
        return 'index'

    # ─── COMPETITORS ───
    @classmethod
    @_memo('get_competitors', ttl=600)
    def get_competitors(cls, ticker: str) -> List[dict]:
        """Identify plausible peer tickers based on the sector/industry. Only returns
        tickers we can actually fetch data for; never fabricates metrics."""
        sector_map = {
            'Technology': ['MSFT', 'AAPL', 'GOOGL', 'META', 'AMD', 'INTC', 'CRM'],
            'Semiconductors': ['AMD', 'INTC', 'NVDA', 'QCOM', 'AVGO', 'MU', 'TSM'],
            'Communication Services': ['GOOGL', 'META', 'NFLX', 'DIS', 'TMUS'],
            'Financial Services': ['JPM', 'BAC', 'WFC', 'GS', 'MS', 'V', 'MA'],
            'Consumer Defensive': ['KO', 'PEP', 'PG', 'WMT', 'COST'],
            'Consumer Cyclical': ['AMZN', 'TSLA', 'HD', 'MCD', 'NKE'],
            'Healthcare': ['JNJ', 'PFE', 'UNH', 'MRK', 'LLY'],
            'Energy': ['XOM', 'CVX', 'COP', 'SLB'],
            'Industrials': ['CAT', 'BA', 'GE', 'HON', 'UPS'],
            'Utilities': ['NEE', 'DUK', 'SO', 'AEP'],
            'Real Estate': ['AMT', 'PLD', 'SPG', 'O'],
            'Basic Materials': ['LIN', 'SHW', 'FCX', 'NEM'],
        }
        try:
            tk = cls._get_ticker(ticker)
            info = tk.info or {}
            sector = info.get('sector', '')
            industry = info.get('industry', '')
            peers = sector_map.get(sector, [])
            if industry and 'semiconductor' in industry.lower() and 'Technology' not in peers:
                peers = sector_map.get('Semiconductors', [])
            peers = [p for p in peers if p != ticker][:5]

            result = []
            for peer in peers:
                try:
                    ptk = yf.Ticker(peer)
                    pinfo = ptk.info or {}
                    hist = ptk.history(period='1d')
                    price = cls._safe_float(pinfo.get('currentPrice')) or (cls._safe_float(hist['Close'].iloc[-1]) if hist is not None and len(hist) else None)
                    result.append({
                        'ticker': peer,
                        'name': pinfo.get('shortName') or peer,
                        'price': round(price, 2) if price else None,
                        'market_cap': pinfo.get('marketCap'),
                        'pe': cls._safe_float(pinfo.get('trailingPE')),
                        'revenue_growth': cls._safe_float(pinfo.get('revenueGrowth')),
                        'gross_margin': cls._safe_float(pinfo.get('grossMargins')),
                        'operating_margin': cls._safe_float(pinfo.get('operatingMargins')),
                        'profit_margin': cls._safe_float(pinfo.get('profitMargins')),
                        'sector': sector,
                    })
                except Exception:
                    continue
            return result
        except Exception:
            return []

    # ─── HOLDERS ───
    @classmethod
    @_memo('get_holders', ttl=600)
    def get_holders(cls, ticker: str) -> dict:
        try:
            tk = cls._get_ticker(ticker)
            info = tk.info or {}
            return {
                'insiders_pct': cls._safe_float(info.get('heldPercentInsiders')),
                'institutions_pct': cls._safe_float(info.get('heldPercentInstitutions')),
            }
        except Exception:
            return {}

    # ─── FULL QUOTE with assembled research data ───
    @classmethod
    @_memo('get_name', ttl=600)
    def get_name(cls, ticker: str) -> str:
        try:
            tk = cls._get_ticker(ticker)
            info = tk.info or {}
            return info.get('shortName') or info.get('longName') or ticker
        except Exception:
            return ticker

    @classmethod
    @_memo('get_analyst_sentiment', ttl=600)
    def get_analyst_sentiment(cls, ticker: str) -> dict:
        try:
            tk = cls._get_ticker(ticker)
            info = tk.info or {}
            return {
                'rating': info.get('recommendationKey'),
                'score': cls._safe_float(info.get('recommendationMean')),
                'target_price': cls._safe_float(info.get('targetMeanPrice')),
                'high': cls._safe_float(info.get('targetHighPrice')),
                'low': cls._safe_float(info.get('targetLowPrice')),
                'count': cls._safe_float(info.get('numberOfAnalystOpinions')),
            }
        except Exception:
            return {}
