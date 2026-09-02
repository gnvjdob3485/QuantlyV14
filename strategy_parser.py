import re
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple


class Strategy:
    def __init__(self):
        self.id = str(uuid.uuid4())[:8]
        self.name = "Custom Strategy"
        self.description = ""
        self.raw_text = ""
        self.ticker = "SPY"
        self.direction = "long"
        self.buy_signals: List[Dict] = []
        self.sell_signals: List[Dict] = []
        self.indicators: Dict = {}
        self.position_size = 1.0
        self.risk_per_trade = 1.0
        self.stop_loss_pct = None
        self.take_profit_pct = None
        self.trailing_stop_pct = None
        self.timeframe = "1d"
        self.suggested_start = None
        self.suggested_end = None
        self.assumptions: List[str] = []
        self.created_at = datetime.now().isoformat()
        self.last_tested = None
        self.results = None

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'description': self.description,
            'raw_text': self.raw_text, 'ticker': self.ticker,
            'direction': self.direction,
            'buy_signals': self.buy_signals, 'sell_signals': self.sell_signals,
            'indicators': self.indicators, 'position_size': self.position_size,
            'risk_per_trade': self.risk_per_trade,
            'stop_loss_pct': self.stop_loss_pct,
            'take_profit_pct': self.take_profit_pct,
            'trailing_stop_pct': self.trailing_stop_pct,
            'timeframe': self.timeframe,
            'suggested_start': self.suggested_start,
            'suggested_end': self.suggested_end,
            'assumptions': self.assumptions,
            'created_at': self.created_at,
            'last_tested': self.last_tested,
        }


class StrategyParser:
    """Enhanced NLP parser: auto-detects asset, direction, indicators, timeframe, risk params."""

    INDICATOR_KEYWORDS = {
        'sma': 'SMA', 'simple moving average': 'SMA',
        'ema': 'EMA', 'exponential moving average': 'EMA',
        'rsi': 'RSI', 'relative strength index': 'RSI',
        'macd': 'MACD', 'bollinger': 'BOLLINGER',
        'bollinger bands': 'BOLLINGER', 'bb': 'BOLLINGER',
        'volume': 'VOLUME', 'vwap': 'VWAP',
        'atr': 'ATR', 'average true range': 'ATR',
        'stochastic': 'STOCHASTIC', 'stoch': 'STOCHASTIC',
        'adx': 'ADX', 'average directional': 'ADX',
        'ichimoku': 'ICHIMOKU', 'parabolic': 'SAR', 'psar': 'SAR',
    }

    TIMEFRAME_KEYWORDS = {
        '1 minute': '1m', '1min': '1m', '1m chart': '1m',
        '5 minute': '5m', '5min': '1m', '5m chart': '5m',
        '15 minute': '15m', '15min': '15m', '15m chart': '15m',
        '30 minute': '30m', '30min': '30m', '30m chart': '30m',
        'hourly': '1h', '1 hour': '1h', '1h': '1h', '1h chart': '1h',
        '4 hour': '1h', '4h': '1h', '4h chart': '1h',
        'daily': '1d', 'day': '1d', 'daily chart': '1d',
        'weekly': '1wk', 'week': '1wk', 'weekly chart': '1wk',
        'monthly': '1mo', 'month': '1mo', 'monthly chart': '1mo',
    }

    ASSET_KEYWORDS = {
        'sp500': '^GSPC', 's&p 500': '^GSPC', 's&p500': '^GSPC',
        's&p': '^GSPC', 'spy': 'SPY', 'qqq': 'QQQ',
        'nasdaq': '^IXIC', 'dow jones': '^DJI', 'dow': '^DJI',
        'russell': '^RUT', 'russell 2000': '^RUT',
        'vix': '^VIX', 'bitcoin': 'BTC-USD', 'btc': 'BTC-USD',
        'ethereum': 'ETH-USD', 'eth': 'ETH-USD',
        'gold': 'GLD', 'silver': 'SLV', 'oil': 'USO',
        'treasury': 'TLT', 'bonds': 'TLT',
        'aapl': 'AAPL', 'apple': 'AAPL', 'msft': 'MSFT',
        'microsoft': 'MSFT', 'googl': 'GOOGL', 'google': 'GOOGL',
        'amzn': 'AMZN', 'amazon': 'AMZN', 'tsla': 'TSLA',
        'tesla': 'TSLA', 'nvda': 'NVDA', 'nvidia': 'NVDA',
        'meta': 'META', 'facebook': 'META',
    }

    def parse(self, text: str, ticker_override: str = None) -> Strategy:
        text_lower = text.lower().strip()
        strategy = Strategy()
        strategy.raw_text = text
        strategy.description = text

        if ticker_override:
            strategy.ticker = ticker_override.upper()
        else:
            strategy.ticker = self._detect_ticker(text_lower) or "SPY"

        strategy.direction = self._detect_direction(text_lower)
        strategy.timeframe = self._detect_timeframe(text_lower)
        self._detect_indicators(text_lower, strategy)
        self._detect_buy_signals(text_lower, strategy)
        self._detect_sell_signals(text_lower, strategy)
        self._detect_risk_params(text_lower, strategy)
        self._detect_position_sizing(text_lower, strategy)
        self._set_suggested_dates(strategy)

        if not strategy.buy_signals and not strategy.sell_signals:
            self._fallback_parse(text_lower, strategy)

        if strategy.direction == 'short':
            if not strategy.sell_signals:
                strategy.sell_signals.append({
                    'type': 'rsi_overbought', 'threshold': 70,
                    'description': 'RSI rises above 70'
                })
                strategy.indicators['RSI'] = strategy.indicators.get('RSI', 14)
            if not strategy.buy_signals:
                strategy.buy_signals.append({
                    'type': 'rsi_oversold', 'threshold': 30,
                    'description': 'RSI drops below 30'
                })
                strategy.indicators['RSI'] = strategy.indicators.get('RSI', 14)

        strategy.name = self._generate_name(strategy)
        strategy.assumptions = self._generate_assumptions(strategy)
        return strategy

    def _detect_ticker(self, text: str) -> Optional[str]:
        for keyword, ticker in self.ASSET_KEYWORDS.items():
            if keyword in text:
                return ticker
        match = re.search(r'\b([A-Z]{1,5})\b', text.upper())
        if match:
            return match.group(1)
        return None

    def _detect_direction(self, text: str) -> str:
        short_keywords = ['short', 'go short', 'sell short', 'short selling', 'bearish', 'put']
        if any(kw in text for kw in short_keywords):
            return 'short'
        return 'long'

    def _detect_timeframe(self, text: str) -> str:
        for keyword, tf in self.TIMEFRAME_KEYWORDS.items():
            if keyword in text:
                return tf
        return '1d'

    def _detect_indicators(self, text: str, strategy: Strategy):
        matched = set()
        for keyword, indicator in self.INDICATOR_KEYWORDS.items():
            if keyword in text:
                matched.add(indicator)

        if 'EMA' in matched or 'SMA' in matched:
            for indicator in ('EMA', 'SMA'):
                if indicator in matched:
                    periods = self._extract_all_periods(text, indicator)
                    strategy.indicators[indicator] = periods if len(periods) > 1 else periods[0]
            for keyword, indicator in self.INDICATOR_KEYWORDS.items():
                if indicator in matched and indicator not in ('EMA', 'SMA'):
                    period = self._extract_period(text, keyword, indicator)
                    if indicator not in strategy.indicators:
                        strategy.indicators[indicator] = period
        else:
            for keyword, indicator in self.INDICATOR_KEYWORDS.items():
                if keyword in text:
                    period = self._extract_period(text, keyword, indicator)
                    strategy.indicators[indicator] = period

    def _extract_all_periods(self, text: str, indicator: str) -> list:
        ind = indicator.lower()
        periods = []
        for pattern in [rf'(\d+)\s*(?:day|period)?\s*{re.escape(ind)}',
                         rf'{re.escape(ind)}\s*(?:of\s*)?(\d+)',
                         rf'(\d+)\s*{re.escape(ind)}']:
            for match in re.finditer(pattern, text):
                val = int(match.group(1))
                if 2 <= val <= 500 and val not in periods:
                    periods.append(val)
        if not periods:
            periods.append(20)
        return sorted(periods)

    def _extract_period(self, text: str, keyword: str, indicator: str) -> any:
        patterns = [
            rf'(\d+)\s*(?:day|period)?\s*{re.escape(keyword)}',
            rf'{re.escape(keyword)}\s*(?:of\s*)?(\d+)',
            rf'(\d+)\s*{re.escape(keyword)}',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                val = int(match.group(1))
                if indicator in ('MACD',):
                    return [12, 26, 9] if val == 12 else [val, val * 2, 9]
                return val

        defaults = {
            'SMA': 50, 'EMA': 20, 'RSI': 14, 'MACD': [12, 26, 9],
            'BOLLINGER': 20, 'VOLUME': 20, 'ATR': 14, 'STOCHASTIC': 14,
            'ADX': 14, 'ICHIMOKU': 26, 'SAR': 0.02, 'VWAP': 0, 'DD': 0,
        }
        return defaults.get(indicator, 20)

    def _detect_buy_signals(self, text: str, strategy: Strategy):
        buy_kw = ['buy', 'enter', 'long', 'go long', 'purchase', 'open long']
        has_buy = any(kw in text for kw in buy_kw)

        if 'golden cross' in text:
            strategy.buy_signals.append({
                'type': 'golden_cross',
                'fast': 50, 'slow': 200,
                'description': '50-period SMA crosses above 200-period SMA'
            })
            strategy.indicators['SMA'] = [50, 200]
        elif ('crosses above' in text or 'crosses over' in text or 'crossover' in text) and has_buy:
            fast, slow = self._extract_crossover_periods(text)
            strategy.buy_signals.append({
                'type': 'crossover', 'direction': 'above',
                'fast_period': fast, 'slow_period': slow,
                'description': f'Fast MA({fast}) crosses above Slow MA({slow})'
            })
        elif 'rsi' in text and ('below' in text or 'oversold' in text or 'under' in text) and has_buy:
            val = self._extract_threshold(text, 30, r'below|under')
            strategy.buy_signals.append({
                'type': 'rsi_oversold', 'threshold': val,
                'description': f'RSI drops below {val}'
            })
            strategy.indicators['RSI'] = strategy.indicators.get('RSI', 14)
        elif ('price above' in text or 'close above' in text) and has_buy:
            strategy.buy_signals.append({
                'type': 'price_above_indicator',
                'description': 'Price crosses above primary indicator'
            })
        elif 'macd' in text and ('cross' in text or 'above' in text) and has_buy:
            strategy.buy_signals.append({
                'type': 'macd_cross', 'direction': 'bullish',
                'description': 'MACD crosses above signal line'
            })
        elif 'bollinger' in text and ('below' in text or 'lower' in text or 'touch' in text) and has_buy:
            strategy.buy_signals.append({
                'type': 'bollinger_lower',
                'description': 'Price touches lower Bollinger Band'
            })
        elif has_buy:
            strategy.buy_signals.append({
                'type': 'price_above_indicator',
                'description': 'Price crosses above primary indicator'
            })

    def _detect_sell_signals(self, text: str, strategy: Strategy):
        sell_kw = ['sell', 'exit', 'close', 'short', 'go short', 'close long']
        has_sell = any(kw in text for kw in sell_kw)

        if 'death cross' in text:
            strategy.sell_signals.append({
                'type': 'death_cross',
                'fast': 50, 'slow': 200,
                'description': '50-period SMA crosses below 200-period SMA'
            })
            strategy.indicators['SMA'] = [50, 200]
        elif ('crosses below' in text or 'crosses under' in text) and has_sell:
            fast, slow = self._extract_crossover_periods(text)
            strategy.sell_signals.append({
                'type': 'crossover', 'direction': 'below',
                'fast_period': fast, 'slow_period': slow,
                'description': f'Fast MA({fast}) crosses below Slow MA({slow})'
            })
        elif 'rsi' in text and ('above' in text or 'overbought' in text or 'over' in text) and has_sell:
            val = self._extract_threshold(text, 70, r'above|over')
            strategy.sell_signals.append({
                'type': 'rsi_overbought', 'threshold': val,
                'description': f'RSI rises above {val}'
            })
            strategy.indicators['RSI'] = strategy.indicators.get('RSI', 14)
        elif ('price below' in text or 'close below' in text) and has_sell:
            strategy.sell_signals.append({
                'type': 'price_below_indicator',
                'description': 'Price crosses below primary indicator'
            })
        elif 'macd' in text and ('cross' in text or 'below' in text) and has_sell:
            strategy.sell_signals.append({
                'type': 'macd_cross', 'direction': 'bearish',
                'description': 'MACD crosses below signal line'
            })
        elif 'bollinger' in text and ('above' in text or 'upper' in text) and has_sell:
            strategy.sell_signals.append({
                'type': 'bollinger_upper',
                'description': 'Price touches upper Bollinger Band'
            })
        elif has_sell:
            strategy.sell_signals.append({
                'type': 'price_below_indicator',
                'description': 'Price crosses below primary indicator'
            })

    def _extract_crossover_periods(self, text: str) -> Tuple[int, int]:
        ma_numbers = []
        for match in re.finditer(r'(\d+)\s*(?:day|period|EMA|SMA|ma|moving average)', text):
            val = int(match.group(1))
            if 2 <= val <= 500:
                ma_numbers.append(val)
        if not ma_numbers:
            for match in re.finditer(r'(\d+)', text):
                val = int(match.group(1))
                if 5 <= val <= 200:
                    ma_numbers.append(val)
        ma_numbers = sorted(set(ma_numbers))
        if len(ma_numbers) >= 2:
            return ma_numbers[0], ma_numbers[1]
        elif len(ma_numbers) == 1:
            return ma_numbers[0], ma_numbers[0] * 3
        return 20, 50

    def _extract_threshold(self, text: str, default: int, context: str = '') -> int:
        if context:
            match = re.search(rf'(?:{context})\s*(?:to\s*)?(\d+)', text)
            if match:
                val = int(match.group(1))
                if 1 <= val <= 100:
                    return val
        match = re.search(r'(\d+)\s*(?:\%)?', text)
        if match:
            val = int(match.group(1))
            if 1 <= val <= 100:
                return val
        return default

    def _detect_risk_params(self, text: str, strategy: Strategy):
        m = re.search(r'stop\s*loss\s*(?:of\s*)?(\d+\.?\d*)\s*%?', text)
        if not m:
            m = re.search(r'(\d+\.?\d*)\s*%\s*stop\s*loss', text)
        if m:
            strategy.stop_loss_pct = float(m.group(1))
            if strategy.stop_loss_pct < 1:
                strategy.stop_loss_pct *= 100

        m = re.search(r'take\s*profit\s*(?:of\s*)?(\d+\.?\d*)\s*%?', text)
        if not m:
            m = re.search(r'(\d+\.?\d*)\s*%\s*take\s*profit', text)
        if m:
            strategy.take_profit_pct = float(m.group(1))
            if strategy.take_profit_pct < 1:
                strategy.take_profit_pct *= 100

        m = re.search(r'trailing\s*stop\s*(?:of\s*)?(\d+\.?\d*)\s*%?', text)
        if not m:
            m = re.search(r'(\d+\.?\d*)\s*%\s*trailing\s*stop', text)
        if m:
            strategy.trailing_stop_pct = float(m.group(1))
            if strategy.trailing_stop_pct < 1:
                strategy.trailing_stop_pct *= 100

        m = re.search(r'risk\s*(?:per\s*trade)?\s*(?:of\s*)?(\d+\.?\d*)\s*%?', text)
        if m:
            strategy.risk_per_trade = float(m.group(1))
            if strategy.risk_per_trade > 1:
                strategy.risk_per_trade = strategy.risk_per_trade / 100

    def _detect_position_sizing(self, text: str, strategy: Strategy):
        m = re.search(r'(\d+)%\s*(?:of\s*(?:portfolio|capital|position|account))', text)
        if m:
            strategy.position_size = int(m.group(1)) / 100
        m = re.search(r'invest\s*(\d+)%', text)
        if m:
            strategy.position_size = int(m.group(1)) / 100

    def _set_suggested_dates(self, strategy: Strategy):
        end = datetime.now()
        tf = strategy.timeframe
        if tf in ('1m', '5m', '15m', '30m'):
            start = end - timedelta(days=60)
        elif tf == '1h':
            start = end - timedelta(days=365 * 2)
        elif tf == '1d':
            start = end - timedelta(days=365 * 5)
        elif tf == '1wk':
            start = end - timedelta(days=365 * 10)
        else:
            start = end - timedelta(days=365 * 5)
        strategy.suggested_start = start.strftime('%Y-%m-%d')
        strategy.suggested_end = end.strftime('%Y-%m-%d')

    def _fallback_parse(self, text: str, strategy: Strategy):
        strategy.indicators['SMA'] = strategy.indicators.get('SMA', 50)
        if not strategy.buy_signals:
            strategy.buy_signals.append({
                'type': 'price_above_indicator',
                'description': 'Price crosses above primary MA'
            })
        if not strategy.sell_signals:
            strategy.sell_signals.append({
                'type': 'price_below_indicator',
                'description': 'Price crosses below primary MA'
            })

    def _generate_name(self, strategy: Strategy) -> str:
        parts = []
        ind = strategy.indicators
        if 'SMA' in ind:
            p = ind['SMA']
            parts.append(f"SMA({','.join(map(str, p)) if isinstance(p, list) else p})")
        if 'EMA' in ind:
            parts.append(f"EMA({ind['EMA']})")
        if 'RSI' in ind:
            parts.append(f"RSI({ind['RSI']})")
        if 'MACD' in ind:
            parts.append("MACD")
        if 'BOLLINGER' in ind:
            parts.append("BB")
        if not parts:
            parts.append("Custom")
        return ' + '.join(parts)

    def _generate_assumptions(self, strategy: Strategy) -> List[str]:
        assumptions = []
        tf_labels = {'1m': '1-minute', '5m': '5-minute', '15m': '15-minute',
                      '30m': '30-minute', '1h': 'hourly', '1d': 'daily',
                      '1wk': 'weekly', '1mo': 'monthly'}
        assumptions.append(f"Timeframe: {tf_labels.get(strategy.timeframe, strategy.timeframe)} candles")
        assumptions.append(f"Direction: {'Long (buy first, sell to close)' if strategy.direction == 'long' else 'Short (sell first, buy to close)'}")
        assumptions.append(f"Position size: {int(strategy.position_size * 100)}% of capital per trade")
        assumptions.append("Entry/exit signals evaluated at close of each candle (no look-ahead bias)")
        assumptions.append("Transaction costs and slippage are modelled at 0.1% per trade")
        if strategy.stop_loss_pct:
            assumptions.append(f"Stop loss: {strategy.stop_loss_pct}% from entry")
        if strategy.take_profit_pct:
            assumptions.append(f"Take profit: {strategy.take_profit_pct}% from entry")
        if strategy.trailing_stop_pct:
            assumptions.append(f"Trailing stop: {strategy.trailing_stop_pct}% from highest close since entry")
        return assumptions

    def generate_explanation(self, strategy: Strategy) -> dict:
        if strategy.direction == 'short':
            entry_rules = [s['description'] for s in strategy.sell_signals]
            exit_rules = [s['description'] for s in strategy.buy_signals]
            if not entry_rules:
                entry_rules = ['Short on bearish signal']
            if not exit_rules:
                exit_rules = ['Cover on bullish signal']
        else:
            entry_rules = [s['description'] for s in strategy.buy_signals]
            exit_rules = [s['description'] for s in strategy.sell_signals]

        return {
            'asset': strategy.ticker,
            'direction': strategy.direction,
            'timeframe': strategy.timeframe,
            'entry_rules': entry_rules,
            'exit_rules': exit_rules,
            'risk_management': {
                'position_size': f"{int(strategy.position_size * 100)}% of capital",
                'stop_loss': f"{strategy.stop_loss_pct}%" if strategy.stop_loss_pct else "None",
                'take_profit': f"{strategy.take_profit_pct}%" if strategy.take_profit_pct else "None",
                'trailing_stop': f"{strategy.trailing_stop_pct}%" if strategy.trailing_stop_pct else "None",
            },
            'period': f"{strategy.suggested_start} to {strategy.suggested_end}",
            'assumptions': strategy.assumptions,
            'indicators_used': list(strategy.indicators.keys()),
        }

    def optimize_timeframes(self, strategy: Strategy, ticker: str, timeframes: list = None) -> list:
        if timeframes is None:
            timeframes = ['1d', '1wk']
            if strategy.timeframe not in timeframes:
                timeframes.insert(0, strategy.timeframe)
        return timeframes
