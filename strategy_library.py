import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional


class StrategyLibrary:
    """JSON-based persistence for strategies and their backtest results."""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        self.data_dir = data_dir
        self.strategies_file = os.path.join(data_dir, 'strategies.json')
        self._ensure_dir()
        self._load()

    def _ensure_dir(self):
        os.makedirs(self.data_dir, exist_ok=True)

    def _load(self):
        if os.path.exists(self.strategies_file):
            with open(self.strategies_file, 'r') as f:
                self.strategies = json.load(f)
        else:
            self.strategies = []

    def _save(self):
        with open(self.strategies_file, 'w') as f:
            json.dump(self.strategies, f, indent=2, default=str)

    def save_strategy(self, strategy_dict: dict, results: dict = None) -> dict:
        entry = {
            'id': strategy_dict.get('id', str(uuid.uuid4())[:8]),
            'name': strategy_dict.get('name', 'Unnamed'),
            'description': strategy_dict.get('description', ''),
            'raw_text': strategy_dict.get('raw_text', ''),
            'ticker': strategy_dict.get('ticker', ''),
            'direction': strategy_dict.get('direction', 'long'),
            'timeframe': strategy_dict.get('timeframe', '1d'),
            'indicators': strategy_dict.get('indicators', {}),
            'buy_signals': strategy_dict.get('buy_signals', []),
            'sell_signals': strategy_dict.get('sell_signals', []),
            'stop_loss_pct': strategy_dict.get('stop_loss_pct'),
            'take_profit_pct': strategy_dict.get('take_profit_pct'),
            'trailing_stop_pct': strategy_dict.get('trailing_stop_pct'),
            'position_size': strategy_dict.get('position_size', 1.0),
            'risk_per_trade': strategy_dict.get('risk_per_trade', 1.0),
            'created_at': strategy_dict.get('created_at', datetime.now().isoformat()),
            'last_tested': datetime.now().isoformat() if results else strategy_dict.get('last_tested'),
            'last_results': results,
        }

        existing = next((i for i, s in enumerate(self.strategies) if s['id'] == entry['id']), None)
        if existing is not None:
            self.strategies[existing] = entry
        else:
            self.strategies.append(entry)

        self._save()
        return entry

    def get_all(self) -> List[dict]:
        return self.strategies

    def get_by_id(self, strategy_id: str) -> Optional[dict]:
        return next((s for s in self.strategies if s['id'] == strategy_id), None)

    def delete(self, strategy_id: str) -> bool:
        before = len(self.strategies)
        self.strategies = [s for s in self.strategies if s['id'] != strategy_id]
        if len(self.strategies) < before:
            self._save()
            return True
        return False

    def duplicate(self, strategy_id: str) -> Optional[dict]:
        original = self.get_by_id(strategy_id)
        if not original:
            return None
        dup = dict(original)
        dup['id'] = str(uuid.uuid4())[:8]
        dup['name'] = f"{original['name']} (Copy)"
        dup['created_at'] = datetime.now().isoformat()
        dup['last_results'] = None
        self.strategies.append(dup)
        self._save()
        return dup

    def get_recent(self, limit=10) -> List[dict]:
        sorted_strats = sorted(self.strategies, key=lambda s: s.get('created_at', ''), reverse=True)
        return sorted_strats[:limit]

    def get_best(self, limit=5) -> List[dict]:
        with_results = [s for s in self.strategies if s.get('last_results')]
        sorted_strats = sorted(with_results,
                                key=lambda s: s['last_results'].get('sharpe_ratio', 0), reverse=True)
        return sorted_strats[:limit]
