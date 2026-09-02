import numpy as np
import pandas as pd
from typing import Dict


class AIAnalyzer:
    """Post-backtest analysis engine. Provides quantitative reasoning about strategy quality."""

    def analyze(self, results: dict, strategy_dict: dict) -> dict:
        signals = []
        strengths = []
        weaknesses = []
        recommendations = []

        total_ret = results.get('total_return', 0)
        ann_ret = results.get('annualised_return', 0)
        max_dd = results.get('max_drawdown', 0)
        win_rate = results.get('win_rate', 0)
        sharpe = results.get('sharpe_ratio', 0)
        sortino = results.get('sortino_ratio', 0)
        profit_factor = results.get('profit_factor', 0)
        total_trades = results.get('completed_trades', 0)
        benchmark_ret = results.get('benchmark_return', 0)
        recovery = results.get('recovery_factor', 0)
        risk_reward = results.get('risk_reward', 0)
        volatility = results.get('volatility', 0)
        exposure = results.get('exposure_pct', 0)

        if total_ret > benchmark_ret:
            signals.append(f"Strategy returned {total_ret:.1f}% vs buy-and-hold {benchmark_ret:.1f}%. It beat the market by {total_ret - benchmark_ret:.1f} percentage points.")
            strengths.append("Outperforms passive buy-and-hold")
        else:
            signals.append(f"Strategy returned {total_ret:.1f}% vs buy-and-hold {benchmark_ret:.1f}%. It underperformed by {benchmark_ret - total_ret:.1f} percentage points.")
            weaknesses.append("Does not beat buy-and-hold")

        if sharpe > 1:
            signals.append(f"Sharpe ratio of {sharpe:.2f} indicates strong risk-adjusted returns (above 1.0 is generally considered good).")
            strengths.append("Strong risk-adjusted returns")
        elif sharpe > 0.5:
            signals.append(f"Sharpe ratio of {sharpe:.2f} is moderate. Decent but not exceptional risk-adjusted performance.")
        else:
            signals.append(f"Sharpe ratio of {sharpe:.2f} is poor. Returns do not adequately compensate for the risk taken.")
            weaknesses.append("Poor risk-adjusted returns")

        if max_dd > 30:
            signals.append(f"Maximum drawdown of {max_dd:.1f}% is severe. A {max_dd:.0f}% decline from peak means a {((1/(1-max_dd/100))-1)*100:.0f}% recovery is needed to break even again.")
            weaknesses.append("Severe drawdown risk")
            recommendations.append("Consider adding a stop-loss or reducing position size to limit drawdowns")
        elif max_dd > 20:
            signals.append(f"Maximum drawdown of {max_dd:.1f}% is significant. Expect extended recovery periods.")
            weaknesses.append("Notable drawdown exposure")
        elif max_dd < 10:
            signals.append(f"Maximum drawdown of {max_dd:.1f}% is well-controlled.")
            strengths.append("Controlled drawdowns")

        if total_trades < 10:
            signals.append(f"Only {total_trades} completed trades. This is a very small sample. Statistical significance is low and results could easily be due to luck.")
            weaknesses.append("Insufficient trade sample size")
            recommendations.append("Test over a longer period or use a shorter timeframe to generate more trades")
        elif total_trades < 30:
            signals.append(f"{total_trades} completed trades provides a limited sample. Caution is warranted when drawing conclusions.")
            weaknesses.append("Limited trade sample")
        elif total_trades > 200:
            signals.append(f"{total_trades} completed trades provides a statistically meaningful sample.")
            strengths.append("Large trade sample")

        if win_rate > 60 and risk_reward < 1:
            signals.append(f"High win rate ({win_rate:.0f}%) but low risk/reward ({risk_reward:.2f}). The strategy wins often but wins are small relative to losses. This can mask fragility.")
            weaknesses.append("Frequent small wins, larger losses")
        elif win_rate < 40 and risk_reward > 2:
            signals.append(f"Low win rate ({win_rate:.0f}%) but high risk/reward ({risk_reward:.2f}). The strategy loses more often but winners are substantially larger than losers.")
            strengths.append("Favourable win/loss ratio")

        if profit_factor > 2:
            strengths.append(f"Profit factor of {profit_factor:.2f} is strong (above 2.0)")
        elif profit_factor < 1:
            weaknesses.append(f"Profit factor of {profit_factor:.2f} is below 1.0 - the strategy loses more than it gains")
            signals.append(f"Profit factor of {profit_factor:.2f} means total losses exceed total gains. This strategy is net negative.")

        if max_dd > 0 and total_ret > 0:
            recovery_needed = (1 / (1 - max_dd / 100) - 1) * 100
            signals.append(f"After a {max_dd:.1f}% drawdown, a {recovery_needed:.1f}% gain is needed just to recover to the previous peak.")

        if volatility > 25:
            signals.append(f"Portfolio volatility of {volatility:.1f}% is high. Expect large swings in equity.")
            weaknesses.append("High volatility")
        elif volatility < 10:
            strengths.append("Low portfolio volatility")

        if exposure < 30:
            signals.append(f"Strategy is only in the market {exposure:.0f}% of the time. Capital sits idle for extended periods.")
        elif exposure > 90:
            signals.append(f"Strategy is exposed to the market {exposure:.0f}% of the time. Limited protection during downturns.")

        monthly = results.get('monthly_returns', [])
        if len(monthly) >= 6:
            pos_months = sum(1 for m in monthly if m['return'] > 0)
            neg_months = sum(1 for m in monthly if m['return'] < 0)
            consistency = pos_months / len(monthly) * 100
            signals.append(f"Positive in {pos_months}/{len(monthly)} months ({consistency:.0f}% consistency).")
            if consistency > 65:
                strengths.append("Consistent monthly performance")

        yearly = results.get('yearly_returns', [])
        if len(yearly) >= 3:
            pos_years = sum(1 for y in yearly if y['return'] > 0)
            neg_years = sum(1 for y in yearly if y['return'] < 0)
            signals.append(f"Positive in {pos_years}/{len(yearly)} years. {'Mostly profitable across different market regimes.' if pos_years > neg_years else 'Inconsistent across years - may be regime-dependent.'}")
            if pos_years <= neg_years:
                weaknesses.append("Inconsistent year-to-year performance")
                recommendations.append("The strategy may only work in specific market conditions (bull/bear). Consider adding regime filters.")

        if not weaknesses:
            weaknesses.append("No critical weaknesses identified in this backtest period")
        if not strengths:
            strengths.append("Backtest completed successfully")

        overfit_risk = self._assess_overfit_risk(results, strategy_dict)

        summary = self._generate_summary(results, strengths, weaknesses, overfit_risk)

        return {
            'summary': summary,
            'signals': signals,
            'strengths': strengths,
            'weaknesses': weaknesses,
            'recommendations': recommendations,
            'overfit_risk': overfit_risk,
            'regime_analysis': self._regime_analysis(results),
            'parameter_sensitivity_note': "Parameter sensitivity analysis available in the Robustness tab.",
        }

    def _assess_overfit_risk(self, results: dict, strategy_dict: dict) -> dict:
        risk_score = 0
        factors = []

        total_trades = results.get('completed_trades', 0)
        if total_trades < 20:
            risk_score += 30
            factors.append(f"Only {total_trades} trades - small sample increases overfitting risk significantly")

        total_ret = results.get('total_return', 0)
        max_dd = results.get('max_drawdown', 0)
        if total_ret > 100 and max_dd < 15:
            risk_score += 25
            factors.append("Unusually high returns with low drawdown - potentially overfit to specific conditions")

        if results.get('sharpe_ratio', 0) > 3:
            risk_score += 20
            factors.append("Sharpe ratio above 3.0 is rare in live trading and may indicate overfitting")

        if results.get('win_rate', 0) > 80 and total_trades > 10:
            risk_score += 15
            factors.append("Win rate above 80% is unusual - verify there is no look-ahead bias")

        indicators = strategy_dict.get('indicators', {})
        num_params = sum(1 for v in indicators.values() if not isinstance(v, list)) + sum(len(v) for v in indicators.values() if isinstance(v, list))
        if num_params > 5:
            risk_score += 15
            factors.append(f"Strategy has {num_params} parameters - more parameters increase overfitting risk")

        if total_trades > 100:
            risk_score -= 10
            factors.append("Large trade sample helps reduce overfitting concern")

        risk_score = max(0, min(100, risk_score))

        level = 'Low'
        if risk_score > 60:
            level = 'High'
        elif risk_score > 30:
            level = 'Moderate'

        return {
            'score': risk_score,
            'level': level,
            'factors': factors,
            'advice': self._overfit_advice(level),
        }

    def _overfit_advice(self, level: str) -> str:
        if level == 'High':
            return "This strategy shows significant overfitting risk. Before trading real money: (1) test on out-of-sample data, (2) run walk-forward analysis, (3) reduce parameters, (4) verify across different market regimes."
        elif level == 'Moderate':
            return "Moderate overfitting risk. Recommended: test on a holdout period not used in strategy design, and verify the strategy works across different years."
        return "Low overfitting risk based on available metrics, but always validate with out-of-sample testing before live trading."

    def _regime_analysis(self, results: dict) -> dict:
        yearly = results.get('yearly_returns', [])
        if not yearly:
            return {'available': False}

        returns = [y['return'] for y in yearly]
        avg = np.mean(returns) if returns else 0
        std = np.std(returns) if len(returns) > 1 else 0
        best_year = max(returns) if returns else 0
        worst_year = min(returns) if returns else 0

        return {
            'available': True,
            'avg_yearly_return': round(float(avg), 2),
            'yearly_std': round(float(std), 2),
            'best_year': round(float(best_year), 2),
            'worst_year': round(float(worst_year), 2),
            'years_analysed': len(yearly),
            'positive_years': sum(1 for r in returns if r > 0),
            'negative_years': sum(1 for r in returns if r <= 0),
        }

    def _generate_summary(self, results, strengths, weaknesses, overfit):
        total_ret = results.get('total_return', 0)
        sharpe = results.get('sharpe_ratio', 0)
        max_dd = results.get('max_drawdown', 0)

        if total_ret > 0 and sharpe > 0.5 and max_dd < 25:
            verdict = "This strategy shows promise with positive risk-adjusted returns."
        elif total_ret > 0 and sharpe > 0:
            verdict = "This strategy is profitable but risk management could be improved."
        elif total_ret > 0:
            verdict = "This strategy makes money but takes excessive risk to do so."
        else:
            verdict = "This strategy is unprofitable in this test period."

        if overfit['level'] == 'High':
            verdict += " However, overfitting risk is HIGH - results may not hold in live trading."

        return verdict

    def compare_strategies(self, results_a: dict, results_b: dict) -> dict:
        metrics = ['total_return', 'annualised_return', 'max_drawdown', 'sharpe_ratio',
                    'win_rate', 'profit_factor', 'completed_trades', 'sortino_ratio']
        comparison = {}
        for m in metrics:
            va = results_a.get(m, 0)
            vb = results_b.get(m, 0)
            comparison[m] = {'strategy_a': round(float(va), 2), 'strategy_b': round(float(vb), 2),
                             'winner': 'A' if va > vb else ('B' if vb > va else 'Tie')}

        name_a = results_a.get('strategy_name', 'Strategy A')
        name_b = results_b.get('strategy_name', 'Strategy B')

        a_wins = sum(1 for v in comparison.values() if v['winner'] == 'A')
        b_wins = sum(1 for v in comparison.values() if v['winner'] == 'B')

        explanation = f"{name_a} wins on {a_wins} metrics, {name_b} wins on {b_wins}. "

        if results_a.get('sharpe_ratio', 0) > results_b.get('sharpe_ratio', 0):
            explanation += f"{name_a} has better risk-adjusted returns. "
        if results_a.get('max_drawdown', 0) < results_b.get('max_drawdown', 0):
            explanation += f"{name_a} has smaller drawdowns. "

        return {
            'comparison': comparison,
            'summary': explanation,
            'overall_winner': name_a if a_wins > b_wins else (name_b if b_wins > a_wins else 'Tie'),
        }
