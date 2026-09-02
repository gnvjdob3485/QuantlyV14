import yfinance as yf
import pandas as pd
from typing import Optional


class DataProvider:
    """Modular data layer. Currently uses yfinance. Swap provider by subclassing."""

    INTERVAL_MAP = {
        '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
        '1h': '1h', '1d': '1d', '1wk': '1wk', '1mo': '1mo',
    }

    # yfinance limits intraday history
    INTRADAY_LIMITS = {
        '1m': 7, '5m': 60, '15m': 60, '30m': 60, '1h': 730,
    }

    @classmethod
    def fetch(cls, ticker: str, start: str, end: str, interval: str = '1d') -> pd.DataFrame:
        interval = cls.INTERVAL_MAP.get(interval, '1d')
        tk = yf.Ticker(ticker)

        if interval in ('1m', '5m', '15m', '30m'):
            max_days = cls.INTRADAY_LIMITS.get(interval, 60)
            df = tk.history(period=f'{max_days}d', interval=interval, auto_adjust=True)
        elif interval == '1h':
            df = tk.history(period='730d', interval=interval, auto_adjust=True)
        else:
            df = tk.history(start=start, end=end, interval=interval, auto_adjust=True)

        if df is not None and not df.empty:
            df.index = df.index.tz_localize(None) if df.index.tz else df.index
            if interval in ('1d', '1wk', '1mo'):
                start_dt = pd.to_datetime(start)
                end_dt = pd.to_datetime(end)
                df = df[(df.index >= start_dt) & (df.index <= end_dt)]

        return df if df is not None else pd.DataFrame()

    @classmethod
    def validate_ticker(cls, ticker: str) -> dict:
        try:
            tk = yf.Ticker(ticker)
            info = tk.info or {}
            if 'symbol' in info or 'shortName' in info:
                return {
                    'valid': True,
                    'name': info.get('shortName', ticker),
                    'type': info.get('quoteType', 'Equity'),
                    'exchange': info.get('exchange', ''),
                    'currency': info.get('currency', 'USD'),
                }
            hist = tk.history(period='5d')
            if hist is not None and not hist.empty:
                return {'valid': True, 'name': ticker, 'type': 'Unknown', 'exchange': '', 'currency': 'USD'}
            return {'valid': False}
        except Exception:
            return {'valid': False}

    @classmethod
    def get_available_intervals(cls, ticker: str) -> list:
        return ['1d', '1wk', '1mo']

    @classmethod
    def get_market_overview(cls) -> dict:
        indices = {
            '^GSPC': 'S&P 500',
            '^DJI': 'Dow Jones',
            '^IXIC': 'NASDAQ',
            '^VIX': 'VIX',
        }
        results = {}
        for sym, name in indices.items():
            try:
                tk = yf.Ticker(sym)
                hist = tk.history(period='5d')
                if hist is not None and len(hist) >= 2:
                    last = hist['Close'].iloc[-1]
                    prev = hist['Close'].iloc[-2]
                    change_pct = ((last - prev) / prev) * 100
                    results[sym] = {
                        'name': name, 'price': round(float(last), 2),
                        'change': round(float(change_pct), 2),
                    }
            except Exception:
                pass
        return results
