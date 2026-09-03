"""
Conversational AI research chat engine.

Provides natural-language understanding for the asset research chat:
  * Topic / intent detection with broad synonym coverage
  * Conversation memory (history + current topic) for follow-up questions
  * Pronoun / referent resolution ("what about it?", "and the valuation?")
  * Typo / informal phrasing normalisation
  * Honest answers grounded strictly in the REAL data on the page

This is a deterministic NLU engine (no external LLM). It never fabricates
numbers: where data is absent it says so explicitly rather than guessing.
"""

import re

FILLERS = [
    'please', 'pls', 'plz', 'hey', 'hi', 'hello', 'thanks', 'thank you', 'thx',
    'can you', 'could you', 'can u', 'would you', 'do you', 'will you',
    'i want to know', 'i would like to know', 'i wanna know', 'tell me',
    'what about', 'how about', 'about', 'um', 'uh', 'like', 'basically',
    'just', 'actually', 'so', 'now', 'tell', 'show me', 'give me', 'maybe',
]

# simple typo map (common informal / misspelled finance terms)
SPELLING = {
    'socre': 'score', 'scor': 'score', 'scroe': 'score',
    'priz': 'price', 'pric': 'price', 'pricce': 'price',
    'valution': 'valuation', 'valu': 'valuation', 'valua': 'valuation',
    'risc': 'risk', 'riskss': 'risk',
    'competitiors': 'competitors', 'competeter': 'competitor',
    'teknikal': 'technical', 'tecnical': 'technical',
    'revnue': 'revenue', 'neews': 'news', 'nues': 'news',
    'dvidend': 'dividend', 'divident': 'dividend',
    'geomomentum': 'momentum', 'momemtum': 'momentum', 'momentium': 'momentum',
    'exposures': 'exposure', 'expore': 'exposure',
    'want': '', 'wanna': '', 'gimme': '', 'giv': '', 'telll': 'tell',
}

TYPO_MAP = {
    'stock': 'stock', 'stocks': 'stock', 'stoc': 'stock', 'stok': 'stock',
    'share': 'stock', 'shares': 'stock', 'eq': 'stock',
    'price': 'price', 'pric': 'price', 'proce': 'price', 'cost': 'price',
    'valuation': 'valuation', 'valu': 'valuation', 'overvalued': 'valuation',
    'undervalued': 'valuation', 'expensive': 'valuation', 'cheap': 'valuation',
    'risks': 'risk', 'risk': 'risk', 'risc': 'risk', 'downside': 'risk',
    'bull': 'bull', 'bear': 'bear', 'positive': 'bull', 'negatives': 'bear',
    'negative': 'bear', 'upside': 'bull',
    'score': 'score', 'scored': 'score', 'rating': 'score', 'socre': 'score',
    'chart': 'chart', 'graph': 'chart', 'price history': 'chart',
    'news': 'news', 'headlines': 'news', 'recent': 'news',
    'political': 'politics', 'politcs': 'politics', 'geopolitical': 'politics',
    'geopolitics': 'politics', 'government': 'politics', 'regulation': 'politics',
    'regulations': 'politics', 'politics': 'politics',
    'revenue': 'financials', 'revenues': 'financials', 'earnings': 'financials',
    'profit': 'financials', 'profits': 'financials', 'margin': 'financials',
    'growth': 'financials', 'sales': 'financials', 'finances': 'financials',
    'funda': 'financials', 'fundamentals': 'financials',
    'technicals': 'technical', 'technical': 'technical', 'momentum': 'technical',
    'rsi': 'technical', 'moving average': 'technical',
    'competitors': 'competitors', 'competitor': 'competitors', 'peers': 'competitors',
    'compare': 'competitors', 'vs': 'competitors', 'against': 'competitors',
    'scenario': 'scenario', 'scenarios': 'scenario', 'what if': 'scenario',
    'target': 'target', 'price target': 'target', 'forecast': 'target',
    'dividend': 'dividend', 'divident': 'dividend', 'payout': 'dividend',
    'cash flow': 'cashflow', 'debt': 'debt', 'balance sheet': 'debt',
    'short': 'short', 'short interest': 'short',
    'catalyst': 'catalyst', 'catalysts': 'catalyst',
    'hold': 'holders', 'holders': 'holders', 'ownership': 'holders',
    'volume': 'volume', 'liquidity': 'volume',
    'pe': 'pe', 'p/e': 'pe', 'earnings multiple': 'pe', 'multiple': 'pe',
}

# question word hooks that indicate a lookup even without the topic word
LOOKUP_HOOKS = {
    'price': ['price', 'cost', 'how much', 'quote', 'trading at', 'worth'],
    'score': ['score', 'rating', 'how does it score', 'what is the score', 'rank'],
    'risk': ['risk', 'risks', 'downside', 'danger'],
    'financials': ['revenue', 'earnings', 'profit', 'margin', 'eps', 'financial', 'fundamentals'],
    'valuation': ['valuation', 'expensive', 'cheap', 'overvalued', 'undervalued', 'p/e', 'pe'],
    'news': ['news', 'headlines', 'what happened', 'recent'],
    'politics': ['political', 'geopolitical', 'government', 'regulation', 'china', 'trade'],
    'bull': ['bull', 'positive', 'upside', 'good'],
    'bear': ['bear', 'negative', 'risks', 'downside', 'bad'],
    'technical': ['technical', 'momentum', 'rsi', 'moving average', 'trend'],
    'chart': ['chart', 'graph', 'price history'],
    'scenario': ['scenario', 'what if', 'if'],
    'competitors': ['competitor', 'competition', 'peers', 'compare', 'vs', 'similar'],
    'holders': ['holder', 'ownership', 'own', 'owns', 'owned', 'shareholder',
            'hold', 'holds', 'holding', 'institution', 'fund', 'funds', 'major holders', 'institutional'],

    'overview': ['overview', 'summary', 'should i buy', 'buy', 'invest', 'how is it doing'],
}


class ChatSession:
    """Per-asset conversation state."""

    def __init__(self, ticker, asset_name):
        self.ticker = ticker
        self.asset_name = asset_name
        self.history = []          # list of {role, text}
        self.topic = None           # last detected intent
        self.last_answer = None     # last returned answer text

    def push(self, role, text):
        self.history.append({'role': role, 'text': text})
        if len(self.history) > 20:
            self.history = self.history[-20:]


class ChatNLU:
    """Normalises input and detects intents robustly."""

    def __init__(self):
        self._stopwords = set(FILLERS)

    def normalize(self, text: str) -> str:
        t = (text or '').lower()
        # strip punctuation (keep letters, digits, spaces, %, /, .)
        t = re.sub(r"[^a-z0-9\s%/.\-=]", ' ', t)
        t = re.sub(r"\s+", ' ', t).strip()
        # fix common misspellings / informal contractions
        for wrong, right in SPELLING.items():
            t = t.replace(' ' + wrong + ' ', ' ' + right + ' ')
            t = re.sub(r'(?<![a-z])' + re.escape(wrong) + r'(?![a-z])', right, t)
        t = re.sub(r"\s+", ' ', t).strip()
        return t

    def detect_intent(self, raw: str) -> str:
        """Return the best-matching intent, or None."""
        n = self.normalize(raw)
        scores = []
        for intent, words in LOOKUP_HOOKS.items():
            s = 0
            for w in words:
                if self._contains(n, w):
                    s += 1
            if s:
                scores.append((s, intent))
        if not scores:
            return None
        # Prefer more specific multi-word matches on ties
        scores.sort(key=lambda x: (-x[0], -len(x[1])))
        return scores[0][1]

    @staticmethod
    def _contains(text, word):
        """Word-boundary aware substring test.

        Tokens <= 5 chars match as whole words only, so that short words like
        'buy', 'own', 'fund', 'news' cannot falsely match inside longer words
        (e.g. "down*own*side", "*fund*amentals"). Longer finance terms keep
        forgiving substring matching.
        """
        word = word.strip()
        if len(word) <= 5:  # short token -> whole word only to avoid collisions
            return bool(re.search(r'(?<![a-z0-9])' + re.escape(word) + r'(?![a-z0-9])', text))
        return word in text


class ResearchChat:
    """
    High-level chat orchestrator. Binds an AIResearchEngine's live data with
    conversation memory and NLU to answer research questions.
    """

    def __init__(self, engine, session: ChatSession):
        self.engine = engine
        self.session = session

    # ── data accessors (honest: never fabricate) ───────────────
    def _name(self):
        return self.engine.quote.get('name') or self.session.asset_name or self.session.ticker or 'this asset'

    def _ticker(self):
        return self.engine.quote.get('ticker') or self.session.ticker or ''

    def ask(self, raw_question: str) -> str:
        # remember the conversation
        self.session.push('user', raw_question)
        resp = self._respond(raw_question)
        self.session.push('assistant', resp)
        self.session.last_answer = resp
        return resp

    def _is_followup(self, n: str, intent) -> bool:
        """True if the question is a short referent to a prior topic."""
        follow_words = ['it', 'that', 'this', 'what about', 'how about', 'and', 'for it',
                        'for this', 'that too', 'same', 'the stock', 'your view']
        if any(w in n for w in follow_words):
            return True
        # bare intent word (e.g. "valuation?", "news?") after a prior turn
        if len(n) <= 40 and intent and self.session.topic:
            # single topic keyword with no verb -> treat as request for more on same
            if self.session.topic == intent:
                return True
        return False

    def _respond(self, raw: str) -> str:
        nlu = ChatNLU()
        n = nlu.normalize(raw)
        intent = nlu.detect_intent(raw)

        # promises / greetings
        if re.search(r'\b(hi|hello|hey|thanks|thank you)\b', n) and len(n) < 20:
            return f"Hi! I'm happy to help. This is the current research page for {self._name()} ({self._ticker()}). Ask me about its research score, valuation, risks, financials, news, political exposure, or competitors."

        # follow-up reference resolution
        if intent is None:
            if self.session.topic:
                intent = self.session.topic
            else:
                return self._help()

        if self._is_followup(n, intent):
            # refer to previous topic if ambiguous
            intent = intent or self.session.topic or 'overview'

        self.session.topic = intent
        return self._answer_intent(intent, n)

    def _help(self):
        return (f"I can look up these topics for {self._name()} ({self._ticker()}): "
                "research score, price, valuation (expensive/cheap), key risks, "
                "bull/bear case, financials (revenue/margins/earnings), technicals, "
                "recent news, political exposure, scenario analysis, holders or "
                "competitors. Try one of those and I'll use the live data on this page.")

    def _answer_intent(self, intent, n):
        handlers = {
            'overview': self._overview,
            'score': self._score,
            'price': self._price,
            'valuation': self._valuation,
            'risk': self._risk,
            'bull': self._bull,
            'bear': self._bear,
            'financials': self._financials,
            'technical': self._technical,
            'news': self._news,
            'politics': self._politics,
            'scenario': self._scenario,
            'competitors': self._competitors,
            'holders': self._holders,
            'chart': self._chart,
            'pe': self._pe,
        }
        handler = handlers.get(intent)
        if not handler:
            return self._help()
        return handler()

    # ── individual answers ─────────────────────────────────────
    def _overview(self):
        return (f"Here's an overview for {self._name()} ({self._ticker()}): " +
                self._summary_line() + " Ask a follow-up like “what are the risks?” or “is it expensive?” for more detail.")

    def _summary_line(self):
        score = self._score_obj()
        parts = []
        if self.engine.quote.get('price') is not None:
            parts.append(f"last price {self._money(self.engine.quote['price'])}")
        if score:
            parts.append(f"Quantly AI research score {score['score']}/100 ({score['lean'].lower()})")
        if self.engine.technicals.get('trend'):
            parts.append(f"daily trend: {self.engine.technicals['trend'].lower()}")
        return (' and '.join(parts) + '.') if parts else 'available data is limited right now.'

    def _score_obj(self):
        return getattr(self.engine, '_last_score', None)

    def _score(self):
        score = self._score_obj()
        name = self._name()
        if not score:
            return f"Score data isn't available for {name} right now."
        comp = score.get('components', {})
        reasons = []
        r = score.get('technical_reason') or []
        if r: reasons.append("Technical: " + " ".join(r))
        return (f"The Quantly AI Research Score for {name} ({self._ticker()}) is "
                f"{score['score']}/100 with a {score['lean'].lower()} bias (confidence "
                f"{score['confidence']}%). It blends technical momentum "
                f"({comp.get('technical',0):.0f}), fundamentals ({comp.get('fundamental',0):.0f}), "
                f"valuation ({comp.get('valuation',0):.0f}) and news sentiment "
                f"({comp.get('news',0):.0f}).\n" + "\n".join(reasons) if reasons else
                "Score components detail is currently limited.")

    def _price(self):
        q = self.engine.quote
        price = q.get('price')
        if price is None:
            return f"Recent price data isn't available for {self._name()} from the connected provider right now."
        change = q.get('change_pct')
        parts = [f"{self._name()} ({self._ticker()}) is trading at {self._money(price)}."]
        if change is not None:
            direction = "up" if change >= 0 else "down"
            parts.append(f"That's {direction} {abs(change):.2f}% on the latest session.")
        high = q.get('day_high') or q.get('dayHigh')
        low = q.get('day_low') or q.get('dayLow')
        if high and low:
            parts.append(f"Today's range is {self._money(low)} – {self._money(high)}.")
        return " ".join(parts)

    def _valuation(self):
        v = self.engine.valuation
        name = self._name()
        pe = v.get('trailingPE') if isinstance(v, dict) else None
        if pe is None:
            return (f"Valuation data for {name} is currently limited from the connected provider, "
                    "so I can't reliably state whether it looks expensive or cheap right now.")
        if pe < 15:
            return f"{name} trades at a trailing P/E of {pe:.1f}, low relative to the broad market — it may look comparatively reasonable on earnings, though this depends on growth expectations."
        if pe > 40:
            return f"{name} trades at a trailing P/E of {pe:.1f}, elevated — the market appears to be pricing in strong future growth, which makes it sensitive to delivery on expectations."
        return f"{name} trades at a trailing P/E of {pe:.1f}, broadly in a moderate range. Whether it's cheap or expensive depends on expected growth."

    def _pe(self):
        return self._valuation()

    def _risk(self):
        risks = self._overview_data().get('key_risks', [])
        name = self._name()
        if not risks:
            return f"No specific risks were identified from the currently available data for {name}."
        return f"Based on available data, the main risks for {name} are:\n" + "\n".join(f"• {r}" for r in risks)

    def _bull(self):
        bulls = self._overview_data().get('bull_case', [])
        name = self._name()
        if not bulls:
            return f"Limited clear bull factors identified for {name} from available data."
        return f"Potential positives for {name}:\n" + "\n".join(f"• {p}" for p in bulls)

    def _bear(self):
        bears = self._overview_data().get('bear_case', [])
        name = self._name()
        if not bears:
            return f"Limited clear bear factors identified for {name} from available data."
        return f"Potential negatives for {name}:\n" + "\n".join(f"• {p}" for p in bears)

    def _financials(self):
        st = self.engine.stats
        name = self._name()
        lines = [f"Financial snapshot for {name} ({self._ticker()}):"]
        if st.get('revenue_growth') is not None:
            lines.append(f"• Revenue growth (YoY): {st['revenue_growth']*100:.1f}%")
        if st.get('profit_margins') is not None:
            lines.append(f"• Profit margin: {st['profit_margins']*100:.1f}%")
        if st.get('revenue') is not None:
            lines.append(f"• Revenue (TTM): {self._big_money(st['revenue'])}")
        if st.get('debt_to_equity') is not None:
            lines.append(f"• Debt/equity: {st['debt_to_equity']:.2f}")
        if st.get('total_cash') is not None and st.get('total_debt') is not None:
            net = st['total_cash'] - st['total_debt']
            lines.append(f"• Net cash (excess of cash over debt): {self._big_money(net)}")
        if len(lines) == 1:
            return f"Financial detail for {name} is currently limited from the connected provider."
        return "\n".join(lines)

    def _technical(self):
        t = self.engine.technicals
        name = self._name()
        if not t or 'error' in t:
            return f"Technical data isn't available for {name} from the connected provider right now."
        lines = [f"Technical view for {name} ({self._ticker()}):"]
        if t.get('trend'):
            lines.append(f"• Daily trend: {t['trend']}")
        if t.get('price_vs_sma200') is not None:
            lines.append(f"• vs 200-day moving average: {t['price_vs_sma200']:+.1f}%")
        if t.get('rsi') is not None:
            lines.append(f"• RSI(14): {t['rsi']:.0f} ({t.get('rsi_level','neutral')})")
        if t.get('macd_bullish') is not None:
            lines.append("• MACD: above signal (bullish)" if t['macd_bullish'] else "• MACD: below signal (bearish)")
        return "\n".join(lines)

    def _news(self):
        news = self.engine.news or []
        name = self._name()
        if not news:
            return f"Recent news isn't currently available for {name} from the connected data provider."
        titles = [n.get('title') for n in news[:4] if n.get('title')]
        if not titles:
            return f"News headlines aren't available for {name} right now."
        return f"Recent developments for {name}:\n" + "\n".join(f"• {t}" for t in titles) + "\n(These are headlines from the data provider, not editorial analysis.)"

    def _politics(self):
        name = self._name()
        pol = getattr(self.engine, '_last_political', None) or {}
        level = pol.get('political_exposure', 'N/A')
        analysis = pol.get('analysis', [])
        lines = [f"Political exposure for {name}: {str(level).upper()}."]
        lines += [f"• {a}" for a in analysis]
        exp = pol.get('exposure_map')
        if exp:
            lines.append("Exposure map:")
            lines += [f"  - {k}: {v}/100" for k, v in exp.items()]
        return "\n".join(lines)

    def _scenario(self):
        name = self._name()
        sc = getattr(self.engine, '_last_scenarios', None) or {}
        scenarios = sc.get('scenarios', [])
        if not scenarios:
            return f"Scenario detail isn't available for {name} right now."
        lines = [f"Scenario analysis for {name}: (illustrative, not a price forecast)"]
        for s in scenarios:
            lines.append(f"• {s.get('label')}: {s.get('driver')} -> {s.get('business_impact')}")
        return "\n".join(lines)

    def _competitors(self):
        name = self._name()
        comps = self._competitor_data()
        if isinstance(comps, dict):
            # some providers return {"competitors":[...], "comparison":{}} 
            comps = comps.get('competitors') or comps.get('peers') or []
        if not comps:
            return (f"Peer comparison data for {name} isn't currently available from the connected "
                    "provider. You can still search a specific peer's own research page for a direct view.")
        lines = [f"Comparable companies / peers for {name}:"]
        for c in comps[:6]:
            if isinstance(c, str):
                sym = c
                cname = c
            else:
                sym = c.get('symbol') or c.get('ticker')
                cname = c.get('name') or sym
            if cname:
                lines.append(f"• {cname} ({sym})")
        return "\n".join(lines) + "\n(Peers come from the data provider; click a ticker on the page to view its own research.)"

    def _holders(self):
        name = self._name()
        h = self._holders_data()
        if isinstance(h, dict):
            # provider may return {"holders":[...]} or {"top_institutional":[...]} etc.
            top = (h.get('holders') or h.get('top_institutional') or h.get('institutional')
                   or h.get('top') or [])
            h = top
        if not h:
            return f"Holder/ownership detail for {name} isn't currently available from the connected provider."
        items = []
        for k in h[:8]:
            if isinstance(k, dict):
                # prefer a readable name symbol
                kn = k.get('name') or k.get('holder') or k.get('organization') or k.get('symbol')
                if kn:
                    items.append(str(kn))
            elif k:
                items.append(str(k))
        if not items:
            return f"Holder/ownership detail for {name} isn't currently available from the connected provider."
        return (f"Institutional/ownership view for {name}:\n" + "\n".join(f"• {k}" for k in items))

    def _chart(self):
        name = self._name()
        return (f"The price chart for {name} ({self._ticker()}) is shown on this page above. "
                "Use the timeframe buttons (e.g. 1M, 3M, 1Y) to change the window, and hover over the chart for exact prices. "
                "I don't invent chart data — the chart reflects what the provider returns.")

    # ── access cached data with safe defaults ──────────────────
    def _overview_data(self):
        return getattr(self.engine, '_last_overview', None) or {}

    def _competitor_data(self):
        return getattr(self.engine, '_last_competitors', None) or []

    def _holders_data(self):
        return getattr(self.engine, '_last_holders', None) or []

    def _money(self, x):
        try:
            return "$" + f"{float(x):,.2f}"
        except Exception:
            return "n/a"

    def _big_money(self, x):
        try:
            x = float(x)
            if abs(x) >= 1e12:
                return f"${x/1e12:,.2f}T"
            if abs(x) >= 1e9:
                return f"${x/1e9:,.2f}B"
            if abs(x) >= 1e6:
                return f"${x/1e6:,.1f}M"
            return f"${x:,.0f}"
        except Exception:
            return "n/a"
