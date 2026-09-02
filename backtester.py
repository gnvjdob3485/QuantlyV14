import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from data_provider import DataProvider


class Backtester:
    """Production-grade backtester with stop loss, take profit, trailing stops,
    transaction costs, slippage, short strategies, and compounding."""

    def __init__(self, ticker, start_date, end_date, initial_capital, strategy,
                 transaction_cost_pct=0.1, slippage_pct=0.05):
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.strategy = strategy
        self.transaction_cost_pct = transaction_cost_pct / 100
        self.slippage_pct = slippage_pct / 100

    def run(self, df_override: pd.DataFrame = None) -> dict:
        if df_override is not None:
            df = df_override
        else:
            df = DataProvider.fetch(self.ticker, self.start_date, self.end_date,
                                     self.strategy.timeframe)

        if df.empty or len(df) < 10:
            raise ValueError(f"Insufficient data for {self.ticker} with {self.strategy.timeframe} timeframe")

        df = self._compute_indicators(df)
        trades, equity_curve, drawdown_curve, dates = self._simulate(df)
        metrics = self._compute_metrics(df, trades, equity_curve, dates)
        monthly_returns = self._compute_monthly_returns(equity_curve, dates)
        yearly_returns = self._compute_yearly_returns(equity_curve, dates)
        trade_dist = self._compute_trade_distribution(trades)

        result = {
            'ticker': self.ticker,
            'strategy_name': self.strategy.name,
            'strategy_description': self.strategy.description,
            'timeframe': self.strategy.timeframe,
            'direction': self.strategy.direction,
            'period_years': metrics['period_years'],
            'start_date': self.start_date,
            'end_date': self.end_date,
            'initial_capital': self.initial_capital,
            'final_value': metrics['final_value'],
            'total_return': metrics['total_return'],
            'annualised_return': metrics['annualised_return'],
            'max_drawdown': metrics['max_drawdown'],
            'win_rate': metrics['win_rate'],
            'total_trades': metrics['total_trades'],
            'completed_trades': metrics['completed_trades'],
            'winning_trades': metrics['winning_trades'],
            'losing_trades': metrics['losing_trades'],
            'avg_trade': metrics['avg_trade'],
            'avg_win': metrics['avg_win'],
            'avg_loss': metrics['avg_loss'],
            'profit_factor': metrics['profit_factor'],
            'sharpe_ratio': metrics['sharpe_ratio'],
            'sortino_ratio': metrics['sortino_ratio'],
            'recovery_factor': metrics['recovery_factor'],
            'best_trade': metrics['best_trade'],
            'worst_trade': metrics['worst_trade'],
            'risk_reward': metrics['risk_reward'],
            'exposure_pct': metrics['exposure_pct'],
            'volatility': metrics['volatility'],
            'benchmark_return': metrics['benchmark_return'],
            'benchmark_sharpe': metrics['benchmark_sharpe'],
            'trades': trades,
            'monthly_returns': monthly_returns,
            'yearly_returns': yearly_returns,
            'trade_distribution': trade_dist,
            'chart_data': {
                'dates': [d.strftime('%Y-%m-%d') for d in dates],
                'equity': [round(float(v), 2) for v in equity_curve],
                'benchmark': [round(float(v), 2) for v in self._get_benchmark(df)],
                'drawdown': [round(float(v), 2) for v in drawdown_curve],
            },
        }
        return result

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        ind = self.strategy.indicators
        close = df['Close']

        if 'SMA' in ind:
            periods = ind['SMA']
            if isinstance(periods, list):
                for p in periods:
                    df[f'SMA_{p}'] = close.rolling(window=p).mean()
            else:
                df[f'SMA_{periods}'] = close.rolling(window=periods).mean()

        if 'EMA' in ind:
            periods = ind['EMA']
            if isinstance(periods, list):
                for p in periods:
                    df[f'EMA_{p}'] = close.ewm(span=p, adjust=False).mean()
            else:
                df[f'EMA_{periods}'] = close.ewm(span=periods, adjust=False).mean()

        if 'RSI' in ind:
            period = ind['RSI']
            delta = close.diff()
            gain = delta.where(delta > 0, 0.0).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
            rs = gain / loss.replace(0, np.nan)
            df['RSI'] = 100 - (100 / (1 + rs))

        if 'MACD' in ind:
            macd_p = ind['MACD']
            fast, slow, sig = (macd_p[0], macd_p[1], macd_p[2]) if isinstance(macd_p, list) else (12, 26, 9)
            ema_f = close.ewm(span=fast, adjust=False).mean()
            ema_s = close.ewm(span=slow, adjust=False).mean()
            df['MACD'] = ema_f - ema_s
            df['MACD_Signal'] = df['MACD'].ewm(span=sig, adjust=False).mean()
            df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

        if 'BOLLINGER' in ind:
            period = ind['BOLLINGER']
            df['BB_Mid'] = close.rolling(window=period).mean()
            std = close.rolling(window=period).std()
            df['BB_Upper'] = df['BB_Mid'] + (std * 2)
            df['BB_Lower'] = df['BB_Mid'] - (std * 2)
            df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Mid']

        if 'ATR' in ind:
            period = ind['ATR']
            hl = df['High'] - df['Low']
            hc = (df['High'] - close.shift()).abs()
            lc = (df['Low'] - close.shift()).abs()
            tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
            df['ATR'] = tr.rolling(window=period).mean()

        if 'STOCHASTIC' in ind:
            period = ind.get('STOCHASTIC', 14)
            lo = df['Low'].rolling(window=period).min()
            hi = df['High'].rolling(window=period).max()
            df['STOCH_K'] = 100 * (close - lo) / (hi - lo).replace(0, np.nan)
            df['STOCH_D'] = df['STOCH_K'].rolling(window=3).mean()

        if 'VOLUME' in ind:
            period = ind.get('VOLUME', 20)
            df['Vol_SMA'] = df['Volume'].rolling(window=period).mean()
            df['Vol_Ratio'] = df['Volume'] / df['Vol_SMA']

        if 'ADX' in ind:
            period = ind.get('ADX', 14)
            plus_dm = df['High'].diff()
            minus_dm = -df['Low'].diff()
            plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
            minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
            hl = df['High'] - df['Low']
            hc = (df['High'] - close.shift()).abs()
            lc = (df['Low'] - close.shift()).abs()
            tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean()
            plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr.replace(0, np.nan))
            minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr.replace(0, np.nan))
            dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
            df['ADX'] = dx.rolling(window=period).mean()

        return df.dropna().copy()

    def _get_primary_indicator_col(self, df: pd.DataFrame) -> str:
        ind = self.strategy.indicators
        if 'EMA' in ind:
            p = ind['EMA']
            periods = p if isinstance(p, list) else [p]
            col = f'EMA_{periods[0]}'
            if col in df.columns:
                return col
        if 'SMA' in ind:
            p = ind['SMA']
            periods = p if isinstance(p, list) else [p]
            col = f'SMA_{periods[0]}'
            if col in df.columns:
                return col
        if 'BOLLINGER' in ind:
            return 'BB_Mid'
        return None

    def _get_fast_slow_cols(self, df: pd.DataFrame, signal: dict) -> tuple:
        fast_p = signal.get('fast_period', 20)
        slow_p = signal.get('slow_period', 50)
        for prefix in ['EMA', 'SMA']:
            fc = f'{prefix}_{fast_p}'
            sc = f'{prefix}_{slow_p}'
            if fc in df.columns and sc in df.columns:
                return fc, sc
        return None, None

    def _simulate(self, df: pd.DataFrame):
        cash = self.initial_capital
        shares = 0
        position = 0  # 0=flat, 1=long, -1=short
        trades = []
        equity_curve = []
        drawdown_curve = []
        dates = []
        entry_price = 0
        highest_since_entry = 0
        lowest_since_entry = float('inf')
        bars_in_trade = 0

        for i in range(1, len(df)):
            row = df.iloc[i]
            prev = df.iloc[i - 1]
            date = df.index[i]
            signal = self._check_signal(df, i)

            if position == 1:
                highest_since_entry = max(highest_since_entry, row['Close'])
                bars_in_trade += 1
                exit_signal = False
                exit_price = row['Close']
                exit_reason = ''

                if self.strategy.trailing_stop_pct and highest_since_entry > 0:
                    trail_stop = highest_since_entry * (1 - self.strategy.trailing_stop_pct / 100)
                    if row['Low'] <= trail_stop:
                        exit_signal = True
                        exit_price = trail_stop
                        exit_reason = 'trailing_stop'

                if self.strategy.stop_loss_pct and not exit_signal:
                    sl_price = entry_price * (1 - self.strategy.stop_loss_pct / 100)
                    if row['Low'] <= sl_price:
                        exit_signal = True
                        exit_price = sl_price
                        exit_reason = 'stop_loss'

                if self.strategy.take_profit_pct and not exit_signal:
                    tp_price = entry_price * (1 + self.strategy.take_profit_pct / 100)
                    if row['High'] >= tp_price:
                        exit_signal = True
                        exit_price = tp_price
                        exit_reason = 'take_profit'

                if signal == 'sell' and not exit_signal:
                    exit_signal = True
                    exit_reason = 'signal'

                if exit_signal:
                    exit_price_adj = exit_price * (1 - self.slippage_pct)
                    revenue = shares * exit_price_adj
                    cost = revenue * self.transaction_cost_pct
                    cash += revenue - cost
                    pnl = (exit_price_adj - entry_price) * shares - cost
                    pnl_pct = ((exit_price_adj - entry_price) / entry_price) * 100
                    trades.append({
                        'entry_date': trades[-1]['date'] if trades and trades[-1]['action'] == 'BUY' else date.strftime('%Y-%m-%d'),
                        'date': date.strftime('%Y-%m-%d'),
                        'action': 'SELL', 'price': round(float(exit_price_adj), 2),
                        'shares': int(shares), 'value': round(float(revenue), 2),
                        'pnl': round(float(pnl), 2), 'pnl_pct': round(float(pnl_pct), 2),
                        'exit_reason': exit_reason, 'bars_held': bars_in_trade,
                    })
                    shares = 0
                    position = 0
                    entry_price = 0
                    bars_in_trade = 0

            elif position == -1:
                lowest_since_entry = min(lowest_since_entry, row['Close'])
                bars_in_trade += 1
                exit_signal = False
                exit_price = row['Close']
                exit_reason = ''

                if self.strategy.trailing_stop_pct:
                    trail_stop = lowest_since_entry * (1 + self.strategy.trailing_stop_pct / 100)
                    if row['High'] >= trail_stop:
                        exit_signal = True
                        exit_price = trail_stop
                        exit_reason = 'trailing_stop'

                if self.strategy.stop_loss_pct and not exit_signal:
                    sl_price = entry_price * (1 + self.strategy.stop_loss_pct / 100)
                    if row['High'] >= sl_price:
                        exit_signal = True
                        exit_price = sl_price
                        exit_reason = 'stop_loss'

                if self.strategy.take_profit_pct and not exit_signal:
                    tp_price = entry_price * (1 - self.strategy.take_profit_pct / 100)
                    if row['Low'] <= tp_price:
                        exit_signal = True
                        exit_price = tp_price
                        exit_reason = 'take_profit'

                if signal == 'cover' and not exit_signal:
                    exit_signal = True
                    exit_reason = 'signal'

                if exit_signal:
                    exit_price_adj = exit_price * (1 + self.slippage_pct)
                    cost_to_cover = shares * exit_price_adj
                    fee = cost_to_cover * self.transaction_cost_pct
                    cash += (entry_price * shares) - cost_to_cover - fee + (entry_price * shares - cost_to_cover)
                    pnl = (entry_price - exit_price_adj) * shares - fee
                    pnl_pct = ((entry_price - exit_price_adj) / entry_price) * 100
                    trades.append({
                        'entry_date': date.strftime('%Y-%m-%d'),
                        'date': date.strftime('%Y-%m-%d'),
                        'action': 'COVER', 'price': round(float(exit_price_adj), 2),
                        'shares': int(shares), 'value': round(float(cost_to_cover), 2),
                        'pnl': round(float(pnl), 2), 'pnl_pct': round(float(pnl_pct), 2),
                        'exit_reason': exit_reason, 'bars_held': bars_in_trade,
                    })
                    shares = 0
                    position = 0
                    entry_price = 0
                    bars_in_trade = 0

            if position == 0:
                if signal == 'buy' and self.strategy.direction == 'long':
                    invest = cash * self.strategy.position_size
                    price_adj = row['Close'] * (1 + self.slippage_pct)
                    shares = int(invest / price_adj)
                    if shares > 0:
                        cost = shares * price_adj
                        fee = cost * self.transaction_cost_pct
                        cash -= cost + fee
                        position = 1
                        entry_price = price_adj
                        highest_since_entry = price_adj
                        trades.append({
                            'date': date.strftime('%Y-%m-%d'), 'action': 'BUY',
                            'price': round(float(price_adj), 2), 'shares': int(shares),
                            'value': round(float(cost), 2),
                        })

                elif signal == 'short' and self.strategy.direction == 'short':
                    invest = cash * self.strategy.position_size
                    price_adj = row['Close'] * (1 - self.slippage_pct)
                    shares = int(invest / price_adj)
                    if shares > 0:
                        proceeds = shares * price_adj
                        fee = proceeds * self.transaction_cost_pct
                        cash += proceeds - fee
                        position = -1
                        entry_price = price_adj
                        lowest_since_entry = price_adj
                        trades.append({
                            'date': date.strftime('%Y-%m-%d'), 'action': 'SHORT',
                            'price': round(float(price_adj), 2), 'shares': int(shares),
                            'value': round(float(proceeds), 2),
                        })

            if position == 1:
                portfolio_val = cash + shares * row['Close']
            elif position == -1:
                portfolio_val = cash + shares * (2 * entry_price - row['Close'])
            else:
                portfolio_val = cash

            equity_curve.append(portfolio_val)
            dates.append(date)

        peak = equity_curve[0] if equity_curve else self.initial_capital
        for val in equity_curve:
            peak = max(peak, val)
            dd = ((peak - val) / peak) * 100 if peak > 0 else 0
            drawdown_curve.append(-dd)

        return trades, equity_curve, drawdown_curve, dates

    def _check_signal(self, df: pd.DataFrame, i: int):
        has_buy = any(self._evaluate_signal(df, i, s) for s in self.strategy.buy_signals)
        has_sell = any(self._evaluate_signal(df, i, s) for s in self.strategy.sell_signals)

        if self.strategy.direction == 'long':
            if has_sell:
                return 'sell'
            if has_buy:
                return 'buy'
        else:
            if has_buy:
                return 'cover'
            if has_sell:
                return 'short'
        return None

    def _evaluate_signal(self, df: pd.DataFrame, i: int, signal: dict) -> bool:
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        sig_type = signal.get('type', '')

        if sig_type == 'golden_cross':
            f50 = df['SMA_50'].iloc[i] if 'SMA_50' in df.columns else row['Close']
            f50_p = df['SMA_50'].iloc[i-1] if 'SMA_50' in df.columns else prev['Close']
            s200 = df['SMA_200'].iloc[i] if 'SMA_200' in df.columns else row['Close']
            s200_p = df['SMA_200'].iloc[i-1] if 'SMA_200' in df.columns else prev['Close']
            return f50_p <= s200_p and f50 > s200

        if sig_type == 'death_cross':
            f50 = df['SMA_50'].iloc[i] if 'SMA_50' in df.columns else row['Close']
            f50_p = df['SMA_50'].iloc[i-1] if 'SMA_50' in df.columns else prev['Close']
            s200 = df['SMA_200'].iloc[i] if 'SMA_200' in df.columns else row['Close']
            s200_p = df['SMA_200'].iloc[i-1] if 'SMA_200' in df.columns else prev['Close']
            return f50_p >= s200_p and f50 < s200

        if sig_type == 'crossover':
            fc, sc = self._get_fast_slow_cols(df, signal)
            if not fc or not sc:
                return False
            direction = signal.get('direction', 'above')
            if direction == 'above':
                return prev[fc] <= prev[sc] and row[fc] > row[sc]
            else:
                return prev[fc] >= prev[sc] and row[fc] < row[sc]

        if sig_type == 'rsi_oversold':
            threshold = signal.get('threshold', 30)
            return row.get('RSI', 50) < threshold

        if sig_type == 'rsi_overbought':
            threshold = signal.get('threshold', 70)
            return row.get('RSI', 50) > threshold

        if sig_type == 'price_above_indicator':
            col = self._get_primary_indicator_col(df)
            if col and col in df.columns:
                return prev['Close'] <= prev[col] and row['Close'] > row[col]
            return prev['Close'] <= prev['Close'] and False

        if sig_type == 'price_below_indicator':
            col = self._get_primary_indicator_col(df)
            if col and col in df.columns:
                return prev['Close'] >= prev[col] and row['Close'] < row[col]
            return prev['Close'] >= prev['Close'] and False

        if sig_type == 'macd_cross':
            direction = signal.get('direction', 'bullish')
            if direction == 'bullish':
                return prev.get('MACD', 0) <= prev.get('MACD_Signal', 0) and row.get('MACD', 0) > row.get('MACD_Signal', 0)
            else:
                return prev.get('MACD', 0) >= prev.get('MACD_Signal', 0) and row.get('MACD', 0) < row.get('MACD_Signal', 0)

        if sig_type == 'bollinger_lower':
            return row['Close'] <= row.get('BB_Lower', row['Close'])

        if sig_type == 'bollinger_upper':
            return row['Close'] >= row.get('BB_Upper', row['Close'])

        return False

    def _get_benchmark(self, df: pd.DataFrame):
        initial_price = df['Close'].iloc[0]
        return (df['Close'] / initial_price) * self.initial_capital

    def _compute_metrics(self, df, trades, equity_curve, dates):
        if not equity_curve:
            return self._empty_metrics()

        final_val = equity_curve[-1]
        total_ret = ((final_val - self.initial_capital) / self.initial_capital) * 100
        days = (dates[-1] - dates[0]).days if len(dates) > 1 else 1
        years = max(days / 365.25, 0.01)
        ann_ret = ((final_val / self.initial_capital) ** (1 / years) - 1) * 100

        bench = self._get_benchmark(df)
        bench_ret = ((bench.iloc[-1] / self.initial_capital) - 1) * 100

        peak = equity_curve[0]
        max_dd = 0
        for v in equity_curve:
            peak = max(peak, v)
            dd = ((peak - v) / peak) * 100 if peak > 0 else 0
            max_dd = max(max_dd, dd)

        eq_series = pd.Series(equity_curve)
        returns = eq_series.pct_change().dropna()

        sharpe = 0
        if len(returns) > 1 and returns.std() > 0:
            sharpe = (returns.mean() / returns.std()) * np.sqrt(252)

        neg_returns = returns[returns < 0]
        sortino = 0
        if len(neg_returns) > 1 and neg_returns.std() > 0:
            sortino = (returns.mean() / neg_returns.std()) * np.sqrt(252)

        volatility = returns.std() * np.sqrt(252) * 100 if len(returns) > 1 else 0

        bench_returns = bench.pct_change().dropna()
        bench_sharpe = 0
        if len(bench_returns) > 1 and bench_returns.std() > 0:
            bench_sharpe = (bench_returns.mean() / bench_returns.std()) * np.sqrt(252)

        sell_trades = [t for t in trades if t['action'] in ('SELL', 'COVER')]
        winning = [t for t in sell_trades if t.get('pnl', 0) > 0]
        losing = [t for t in sell_trades if t.get('pnl', 0) <= 0]
        win_rate = (len(winning) / len(sell_trades) * 100) if sell_trades else 0

        total_wins = sum(t.get('pnl', 0) for t in winning)
        total_losses = abs(sum(t.get('pnl', 0) for t in losing))
        profit_factor = (total_wins / total_losses) if total_losses > 0 else (999 if total_wins > 0 else 0)

        avg_win = (total_wins / len(winning)) if winning else 0
        avg_loss = (-total_losses / len(losing)) if losing else 0
        avg_trade_val = sum(t.get('pnl', 0) for t in sell_trades) / len(sell_trades) if sell_trades else 0
        risk_reward = (avg_win / abs(avg_loss)) if avg_loss != 0 else 0

        best = max((t.get('pnl_pct', 0) for t in sell_trades), default=0)
        worst = min((t.get('pnl_pct', 0) for t in sell_trades), default=0)

        exposure_bars = sum(t.get('bars_held', 0) for t in sell_trades)
        total_bars = len(equity_curve)
        exposure = (exposure_bars / total_bars * 100) if total_bars > 0 else 0

        recovery = (total_ret / max_dd) if max_dd > 0 else 0

        return {
            'final_value': round(float(final_val), 2),
            'total_return': round(float(total_ret), 2),
            'annualised_return': round(float(ann_ret), 2),
            'max_drawdown': round(float(max_dd), 2),
            'win_rate': round(float(win_rate), 2),
            'total_trades': len(trades),
            'completed_trades': len(sell_trades),
            'winning_trades': len(winning),
            'losing_trades': len(losing),
            'avg_trade': round(float(avg_trade_val), 2),
            'avg_win': round(float(avg_win), 2),
            'avg_loss': round(float(avg_loss), 2),
            'profit_factor': round(float(profit_factor), 2),
            'sharpe_ratio': round(float(sharpe), 2),
            'sortino_ratio': round(float(sortino), 2),
            'recovery_factor': round(float(recovery), 2),
            'best_trade': round(float(best), 2),
            'worst_trade': round(float(worst), 2),
            'risk_reward': round(float(risk_reward), 2),
            'exposure_pct': round(float(exposure), 2),
            'volatility': round(float(volatility), 2),
            'benchmark_return': round(float(bench_ret), 2),
            'benchmark_sharpe': round(float(bench_sharpe), 2),
            'period_years': round(float(years), 2),
        }

    def _empty_metrics(self):
        return {k: 0 for k in [
            'final_value', 'total_return', 'annualised_return', 'max_drawdown',
            'win_rate', 'total_trades', 'completed_trades', 'winning_trades',
            'losing_trades', 'avg_trade', 'avg_win', 'avg_loss', 'profit_factor',
            'sharpe_ratio', 'sortino_ratio', 'recovery_factor', 'best_trade',
            'worst_trade', 'risk_reward', 'exposure_pct', 'volatility',
            'benchmark_return', 'benchmark_sharpe', 'period_years',
        ]}

    def _compute_monthly_returns(self, equity_curve, dates):
        if not dates or not equity_curve:
            return []
        df = pd.DataFrame({'equity': equity_curve}, index=pd.DatetimeIndex(dates))
        monthly = df.resample('ME').last()
        monthly['return'] = monthly['equity'].pct_change() * 100
        return [{'month': d.strftime('%Y-%m'), 'return': round(float(r), 2)}
                for d, r in zip(monthly.index, monthly['return']) if not np.isnan(r)]

    def _compute_yearly_returns(self, equity_curve, dates):
        if not dates or not equity_curve:
            return []
        df = pd.DataFrame({'equity': equity_curve}, index=pd.DatetimeIndex(dates))
        yearly = df.resample('YE').last()
        yearly['return'] = yearly['equity'].pct_change() * 100
        return [{'year': d.year, 'return': round(float(r), 2)}
                for d, r in zip(yearly.index, yearly['return']) if not np.isnan(r)]

    def _compute_trade_distribution(self, trades):
        sell_trades = [t for t in trades if t['action'] in ('SELL', 'COVER')]
        pnls = [t.get('pnl_pct', 0) for t in sell_trades]
        if not pnls:
            return []
        bins = [-20, -10, -5, -2, 0, 2, 5, 10, 20, 50]
        hist, edges = np.histogram(pnls, bins=bins)
        return [{'range': f'{edges[i]:.0f}% to {edges[i+1]:.0f}%', 'count': int(c)}
                for i, c in enumerate(hist)]
