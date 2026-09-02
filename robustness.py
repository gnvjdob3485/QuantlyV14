import numpy as np
import pandas as pd
from typing import Dict, List
from backtester import Backtester
from data_provider import DataProvider


class RobustnessEngine:
    """Walk-forward analysis, Monte Carlo, parameter sensitivity, in-sample/out-of-sample split."""

    def walk_forward(self, ticker, strategy, start, end, initial_capital=10000,
                     n_splits=3) -> dict:
        df = DataProvider.fetch(ticker, start, end, strategy.timeframe)
        if df.empty or len(df) < 100:
            raise ValueError("Insufficient data for walk-forward analysis")

        total_len = len(df)
        is_size = int(total_len * 0.6 / n_splits)
        oos_size = int(total_len * 0.4 / n_splits)
        chunk = is_size + oos_size

        results = []
        for i in range(n_splits):
            start_idx = i * chunk
            end_idx = min(start_idx + chunk, total_len)
            if end_idx - start_idx < 20:
                break

            is_start = df.index[start_idx]
            is_end = df.index[start_idx + is_size] if start_idx + is_size < total_len else df.index[-1]
            oos_start = is_end
            oos_end = df.index[min(end_idx, total_len - 1)]

            oos_df = df.loc[oos_start:oos_end].copy()
            if len(oos_df) < 5:
                continue

            bt = Backtester(ticker, start, end, initial_capital, strategy)
            oos_result = bt.run(df_override=oos_df)
            oos_result['split'] = i + 1
            oos_result['period'] = f"{oos_start.strftime('%Y-%m-%d')} to {oos_end.strftime('%Y-%m-%d')}"
            results.append(oos_result)

        avg_return = np.mean([r.get('total_return', 0) for r in results]) if results else 0
        avg_sharpe = np.mean([r.get('sharpe_ratio', 0) for r in results]) if results else 0
        avg_dd = np.mean([r.get('max_drawdown', 0) for r in results]) if results else 0
        positive_splits = sum(1 for r in results if r.get('total_return', 0) > 0)

        return {
            'splits': results,
            'avg_return': round(float(avg_return), 2),
            'avg_sharpe': round(float(avg_sharpe), 2),
            'avg_drawdown': round(float(avg_dd), 2),
            'positive_splits': positive_splits,
            'total_splits': len(results),
            'verdict': self._wf_verdict(avg_return, avg_sharpe, positive_splits, len(results)),
        }

    def _wf_verdict(self, avg_ret, avg_sharpe, pos_splits, total):
        if total == 0:
            return "Insufficient data for walk-forward analysis"
        consistency = pos_splits / total
        if avg_sharpe > 0.5 and consistency > 0.6:
            return f"Strategy performs consistently across walk-forward periods. {pos_splits}/{total} periods profitable with avg Sharpe {avg_sharpe:.2f}."
        elif avg_sharpe > 0:
            return f"Marginal walk-forward performance. {pos_splits}/{total} periods profitable. Results may be timeframe-dependent."
        else:
            return f"Walk-forward analysis shows negative average performance. Strategy likely does not generalise well."

    def monte_carlo(self, results: dict, n_simulations=1000) -> dict:
        trades = results.get('trades', [])
        sell_trades = [t for t in trades if t.get('pnl_pct') is not None]
        if len(sell_trades) < 5:
            return {'error': 'Need at least 5 completed trades for Monte Carlo analysis'}

        pnls = [t['pnl_pct'] for t in sell_trades]
        initial = results.get('initial_capital', 10000)

        final_values = []
        max_dds = []
        for _ in range(n_simulations):
            shuffled = np.random.choice(pnls, size=len(pnls), replace=True)
            equity = [initial]
            for p in shuffled:
                equity.append(equity[-1] * (1 + p / 100))
            final_values.append(equity[-1])
            peak = equity[0]
            max_dd = 0
            for v in equity:
                peak = max(peak, v)
                dd = (peak - v) / peak * 100
                max_dd = max(max_dd, dd)
            max_dds.append(max_dd)

        fv = np.array(final_values)
        md = np.array(max_dds)

        percentiles = [5, 10, 25, 50, 75, 90, 95]
        return_dist = {f'p{p}': round(float(np.percentile(fv, p)), 2) for p in percentiles}
        dd_dist = {f'p{p}': round(float(np.percentile(md, p)), 2) for p in percentiles}

        prob_profit = round(float(np.mean(fv > initial) * 100), 1)
        prob_double = round(float(np.mean(fv >= initial * 2) * 100), 1)
        prob_ruin = round(float(np.mean(fv < initial * 0.5) * 100), 1)

        return {
            'simulations': n_simulations,
            'trades_resampled': len(pnls),
            'return_distribution': return_dist,
            'drawdown_distribution': dd_dist,
            'probability_profit': prob_profit,
            'probability_double': prob_double,
            'probability_ruin': prob_ruin,
            'median_final_value': return_dist['p50'],
            'worst_case_5pct': return_dist['p5'],
            'best_case_95pct': return_dist['p95'],
            'worst_drawdown_5pct': dd_dist['p95'],
        }

    def parameter_sensitivity(self, ticker, strategy_template, start, end, initial_capital,
                              param_name, param_values: list) -> dict:
        results = []
        for val in param_values:
            import copy
            st = copy.deepcopy(strategy_template)
            if param_name == 'stop_loss':
                st.stop_loss_pct = val
            elif param_name == 'take_profit':
                st.take_profit_pct = val
            elif param_name == 'rsi_threshold_buy':
                for sig in st.buy_signals:
                    if sig['type'] == 'rsi_oversold':
                        sig['threshold'] = val
            elif param_name == 'rsi_threshold_sell':
                for sig in st.sell_signals:
                    if sig['type'] == 'rsi_overbought':
                        sig['threshold'] = val

            bt = Backtester(ticker, start, end, initial_capital, st)
            try:
                r = bt.run()
                results.append({
                    'param_value': val,
                    'total_return': r['total_return'],
                    'sharpe_ratio': r['sharpe_ratio'],
                    'max_drawdown': r['max_drawdown'],
                    'win_rate': r['win_rate'],
                })
            except Exception:
                results.append({
                    'param_value': val, 'total_return': 0,
                    'sharpe_ratio': 0, 'max_drawdown': 0, 'win_rate': 0,
                })

        returns = [r['total_return'] for r in results]
        sensitivity = np.std(returns) if len(returns) > 1 else 0

        return {
            'param_name': param_name,
            'results': results,
            'sensitivity_score': round(float(sensitivity), 2),
            'interpretation': self._sensitivity_interpretation(sensitivity, param_name),
        }

    def _sensitivity_interpretation(self, sensitivity, param):
        if sensitivity > 20:
            return f"Strategy is highly sensitive to {param} (std dev: {sensitivity:.1f}%). Results may not be robust."
        elif sensitivity > 10:
            return f"Moderate sensitivity to {param}. Some robustness concern."
        return f"Strategy is relatively stable across different {param} values."
