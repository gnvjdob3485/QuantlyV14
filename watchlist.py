"""
Watchlist persistence (JSON-based, no DB dependency).
Users save assets and see them on the homepage/ nav.
"""

import json
import os
from datetime import datetime


class Watchlist:
    def __init__(self, data_dir=None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        self.data_dir = data_dir
        self.file = os.path.join(data_dir, 'watchlist.json')
        self.entries = []
        self._ensure()
        self._load()

    def _ensure(self):
        os.makedirs(self.data_dir, exist_ok=True)

    def _load(self):
        if os.path.exists(self.file):
            try:
                with open(self.file, 'r') as f:
                    self.entries = json.load(f)
            except Exception:
                self.entries = []

    def _save(self):
        with open(self.file, 'w') as f:
            json.dump(self.entries, f, indent=2)

    def add(self, ticker: str, name: str = None, ai_score: int = None,
            catalyst: str = None, price: float = None, change_pct: float = None):
        ticker = (ticker or '').strip().upper()
        if not ticker:
            return None
        existing = next((e for e in self.entries if e['ticker'] == ticker), None)
        if existing:
            existing.update({
                'name': name or existing.get('name'),
                'ai_score': ai_score if ai_score is not None else existing.get('ai_score'),
                'catalyst': catalyst or existing.get('catalyst'),
                'price': price if price is not None else existing.get('price'),
                'change_pct': change_pct if change_pct is not None else existing.get('change_pct'),
                'updated': datetime.now().isoformat(),
            })
        else:
            self.entries.append({
                'ticker': ticker, 'name': name, 'ai_score': ai_score,
                'catalyst': catalyst, 'price': price, 'change_pct': change_pct,
                'added': datetime.now().isoformat(), 'updated': datetime.now().isoformat(),
            })
        self._save()
        return existing or self.entries[-1]

    def remove(self, ticker: str):
        before = len(self.entries)
        self.entries = [e for e in self.entries if e['ticker'] != ticker.upper()]
        if len(self.entries) < before:
            self._save()
            return True
        return False

    def get_all(self) -> list:
        return self.entries

    def has(self, ticker: str) -> bool:
        return any(e['ticker'] == ticker.upper() for e in self.entries)
