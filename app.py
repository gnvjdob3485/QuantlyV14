import json
import os
import traceback
import numpy as np
from flask import Flask, render_template, request, jsonify
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
from strategy_parser import StrategyParser
from backtester import Backtester
from ai_analyzer import AIAnalyzer
from robustness import RobustnessEngine
from strategy_library import StrategyLibrary
from data_provider import DataProvider
from research_api import research_bp


class NumpyJSONProvider(DefaultJSONProvider):
    """JSON encoder that safely converts numpy types (np.float64, np.bool_,
    np.integer, np.ndarray, pandas Series/DataFrame) before serialisation."""
    @staticmethod
    def _convert(obj):
        if isinstance(obj, np.generic):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if hasattr(obj, 'to_dict'):  # pandas Series
            return obj.to_dict()
        return obj

    def default(self, o):
        converted = self._convert(o)
        if converted is not o:
            return self._clean(converted)
        return super().default(o)

    @classmethod
    def _clean(cls, o):
        if isinstance(o, dict):
            return {k: cls._clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [cls._clean(v) for v in o]
        if isinstance(o, np.generic) or isinstance(o, np.ndarray):
            return cls._convert(o)
        return o


app = Flask(__name__)
app.json = NumpyJSONProvider(app)
CORS(app)
app.register_blueprint(research_bp)

library = StrategyLibrary()

# ─── CONFIG from environment (for deployment) ───
app.config['JSON_SORT_KEYS'] = False
PORT = int(os.environ.get('PORT', 5000))
HOST = os.environ.get('HOST', '0.0.0.0')
DEBUG = os.environ.get('FLASK_DEBUG', '0') == '1'


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/parse-strategy', methods=['POST'])
def parse_strategy():
    try:
        data = request.get_json()
        text = data.get('strategy', '').strip()
        ticker = data.get('ticker', '').strip().upper()
        if not text:
            return jsonify({'error': 'Strategy text is required'}), 400

        parser = StrategyParser()
        strategy = parser.parse(text, ticker_override=ticker if ticker else None)
        explanation = parser.generate_explanation(strategy)

        return jsonify({
            'strategy': strategy.to_dict(),
            'explanation': explanation,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/backtest', methods=['POST'])
def run_backtest():
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').strip().upper()
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        strategy_data = data.get('strategy')
        initial_capital = data.get('initial_capital', 10000)
        transaction_cost = data.get('transaction_cost', 0.1)
        slippage = data.get('slippage', 0.05)

        if not ticker or not strategy_data:
            return jsonify({'error': 'Ticker and strategy are required'}), 400

        parser = StrategyParser()
        strategy = parser.parse(strategy_data.get('raw_text', ''), ticker_override=ticker)
        strategy.stop_loss_pct = strategy_data.get('stop_loss_pct', strategy.stop_loss_pct)
        strategy.take_profit_pct = strategy_data.get('take_profit_pct', strategy.take_profit_pct)
        strategy.trailing_stop_pct = strategy_data.get('trailing_stop_pct', strategy.trailing_stop_pct)
        strategy.position_size = strategy_data.get('position_size', strategy.position_size)

        if start_date:
            strategy.suggested_start = start_date
        if end_date:
            strategy.suggested_end = end_date

        bt = Backtester(
            ticker=ticker,
            start_date=strategy.suggested_start,
            end_date=strategy.suggested_end,
            initial_capital=initial_capital,
            strategy=strategy,
            transaction_cost_pct=transaction_cost,
            slippage_pct=slippage,
        )
        results = bt.run()

        analyzer = AIAnalyzer()
        analysis = analyzer.analyze(results, strategy.to_dict())
        results['ai_analysis'] = analysis

        strategy.last_tested = strategy.suggested_end
        library.save_strategy(strategy.to_dict(), results)

        return jsonify(results)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/timeframe-optimise', methods=['POST'])
def timeframe_optimise():
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').strip().upper()
        strategy_data = data.get('strategy')
        initial_capital = data.get('initial_capital', 10000)

        parser = StrategyParser()
        strategy = parser.parse(strategy_data.get('raw_text', ''), ticker_override=ticker)

        candidate_tfs = ['1d', '1wk']
        if strategy.timeframe not in candidate_tfs:
            candidate_tfs.insert(0, strategy.timeframe)

        tf_results = []
        for tf in candidate_tfs:
            import copy
            s = copy.deepcopy(strategy)
            s.timeframe = tf
            parser._set_suggested_dates(s)
            bt = Backtester(ticker, s.suggested_start, s.suggested_end, initial_capital, s)
            try:
                r = bt.run()
                tf_results.append({
                    'timeframe': tf,
                    'total_return': r['total_return'],
                    'sharpe_ratio': r['sharpe_ratio'],
                    'max_drawdown': r['max_drawdown'],
                    'completed_trades': r['completed_trades'],
                    'win_rate': r['win_rate'],
                })
            except Exception:
                pass

        best = max(tf_results, key=lambda x: x['sharpe_ratio']) if tf_results else None

        return jsonify({
            'results': tf_results,
            'recommended': best,
            'explanation': f"Based on risk-adjusted returns, the {best['timeframe']} timeframe is recommended." if best else "Could not determine optimal timeframe.",
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/robustness/walk-forward', methods=['POST'])
def walk_forward():
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').strip().upper()
        strategy_data = data.get('strategy')
        initial_capital = data.get('initial_capital', 10000)

        parser = StrategyParser()
        strategy = parser.parse(strategy_data.get('raw_text', ''), ticker_override=ticker)

        engine = RobustnessEngine()
        result = engine.walk_forward(ticker, strategy, strategy.suggested_start,
                                      strategy.suggested_end, initial_capital)
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/robustness/monte-carlo', methods=['POST'])
def monte_carlo():
    try:
        data = request.get_json()
        results = data.get('results')
        n_sims = data.get('simulations', 1000)
        if not results:
            return jsonify({'error': 'Backtest results are required'}), 400
        engine = RobustnessEngine()
        result = engine.monte_carlo(results, n_simulations=n_sims)
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/robustness/parameter-sensitivity', methods=['POST'])
def parameter_sensitivity():
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').strip().upper()
        strategy_data = data.get('strategy')
        param_name = data.get('param_name')
        param_values = data.get('param_values', [])
        initial_capital = data.get('initial_capital', 10000)

        parser = StrategyParser()
        strategy = parser.parse(strategy_data.get('raw_text', ''), ticker_override=ticker)

        engine = RobustnessEngine()
        result = engine.parameter_sensitivity(
            ticker, strategy, strategy.suggested_start, strategy.suggested_end,
            initial_capital, param_name, param_values
        )
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/compare', methods=['POST'])
def compare_strategies():
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').strip().upper()
        strategy_a_text = data.get('strategy_a')
        strategy_b_text = data.get('strategy_b')
        start = data.get('start_date')
        end = data.get('end_date')
        capital = data.get('initial_capital', 10000)

        parser = StrategyParser()
        sa = parser.parse(strategy_a_text, ticker_override=ticker)
        sb = parser.parse(strategy_b_text, ticker_override=ticker)

        if start:
            sa.suggested_start = start
            sb.suggested_start = start
        if end:
            sa.suggested_end = end
            sb.suggested_end = end

        bt_a = Backtester(ticker, sa.suggested_start, sa.suggested_end, capital, sa)
        bt_b = Backtester(ticker, sb.suggested_start, sb.suggested_end, capital, sb)
        results_a = bt_a.run()
        results_b = bt_b.run()

        analyzer = AIAnalyzer()
        comparison = analyzer.compare_strategies(results_a, results_b)

        return jsonify({
            'strategy_a': results_a,
            'strategy_b': results_b,
            'comparison': comparison,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/library', methods=['GET'])
def get_library():
    return jsonify(library.get_all())


@app.route('/api/library/<strategy_id>', methods=['GET'])
def get_strategy(strategy_id):
    s = library.get_by_id(strategy_id)
    if s:
        return jsonify(s)
    return jsonify({'error': 'Not found'}), 404


@app.route('/api/library', methods=['POST'])
def save_to_library():
    data = request.get_json()
    entry = library.save_strategy(data.get('strategy', {}), data.get('results'))
    return jsonify(entry)


@app.route('/api/library/<strategy_id>', methods=['DELETE'])
def delete_from_library(strategy_id):
    if library.delete(strategy_id):
        return jsonify({'ok': True})
    return jsonify({'error': 'Not found'}), 404


@app.route('/api/library/<strategy_id>/duplicate', methods=['POST'])
def duplicate_strategy(strategy_id):
    dup = library.duplicate(strategy_id)
    if dup:
        return jsonify(dup)
    return jsonify({'error': 'Not found'}), 404


@app.route('/api/library/recent', methods=['GET'])
def recent_strategies():
    return jsonify(library.get_recent(10))


@app.route('/api/library/best', methods=['GET'])
def best_strategies():
    return jsonify(library.get_best(5))


@app.route('/api/validate-ticker', methods=['POST'])
def validate_ticker():
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').strip().upper()
        result = DataProvider.validate_ticker(ticker)
        return jsonify(result)
    except Exception:
        return jsonify({'valid': False})


@app.route('/api/market-overview', methods=['GET'])
def market_overview():
    try:
        return jsonify(DataProvider.get_market_overview())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host=HOST, port=PORT, debug=DEBUG)
