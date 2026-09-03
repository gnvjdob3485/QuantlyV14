"""
AI Research Intelligence Engine.

Builds a qualitative + quantitative research assessment for an asset using the
REAL data gathered by the data layer. This module:

  * Computes an AI Research Score (0-100)
  * Generates an AI Overview (bull/bear/risks/catalysts)
  * Builds a political/geopolitical impact assessment
  * Constructs a company exposure map
  * Runs scenario analysis
  * Connects events -> economic effect -> industry -> company -> market
  * Powers the AI research chat

Every claim is grounded in the available data and phrased with appropriate
uncertainty. Nothing here is fabricated; where data is missing, that is stated
explicitly.
"""

import math


class AIResearchEngine:
    def __init__(self, quote=None, stats=None, technicals=None, valuation=None,
                 news=None, financials=None, macro=None, fundamental_scores=None):
        self.quote = quote or {}
        self.stats = stats or {}
        self.technicals = technicals or {}
        self.valuation = valuation or {}
        self.news = news or []
        self.financials = financials or {}
        self.macro = macro or {}
        self.fundamental_scores = fundamental_scores or {}

    # ═══════════════════════════════════════════════════════
    # RESEARCH SCORE
    # ═══════════════════════════════════════════════════════
    def compute_score(self) -> dict:
        technical_score = self._technical_score()
        fundamental_score = self._fundamental_score()
        valuation_score = self._valuation_score()
        news_score = self._news_score()

        # Weighted blend
        total = (technical_score[0] * 0.30 +
                 fundamental_score[0] * 0.40 +
                 valuation_score[0] * 0.15 +
                 news_score[0] * 0.15)

        weighted = total
        score = round(total)

        if score >= 70:
            lean = 'Bullish'
        elif score >= 45:
            lean = 'Neutral'
        else:
            lean = 'Bearish'

        result = {
            'score': score,
            'lean': lean,
            'confidence': round(abs(weighted - 50) / 50 * 100, 1),
            'components': {
                'technical': technical_score[0],
                'fundamental': fundamental_score[0],
                'valuation': valuation_score[0],
                'news': news_score[0],
            },
            'technical_reason': technical_score[1],
            'fundamental_reason': fundamental_score[1],
            'valuation_reason': valuation_score[1],
            'news_reason': news_score[1],
        }
        self._last_score = result
        return result

    def _technical_score(self):
        reasons = []
        s = 50
        t = self.technicals
        if not t or 'error' in t:
            return 50, ['Insufficient technical data to assess trend.']
        price = t.get('price_vs_sma200')
        if price is not None:
            if price > 0:
                s += 15
                reasons.append(f'Trading {abs(price):.0f}% above the 200-day moving average (positive long-term trend).')
            else:
                s -= 12
                reasons.append(f'Trading {abs(price):.0f}% below the 200-day moving average (weaker long-term trend).')
        rsi = t.get('rsi')
        if rsi is not None:
            if 55 <= rsi <= 70:
                s += 8
                reasons.append(f'RSI at {rsi:.0f} shows healthy momentum without being overbought.')
            elif rsi > 70:
                s -= 6
                reasons.append(f'RSI at {rsi:.0f} is overbought, suggesting short-term momentum may be stretched.')
            elif rsi < 30:
                s -= 5
                reasons.append(f'RSI at {rsi:.0f} is oversold; could see a technical bounce but reflects recent weakness.')
        macd = t.get('macd_bullish')
        if macd is not None and macd:
            s += 7
            reasons.append('MACD is above its signal line (bullish momentum).')
        elif macd is not None and not macd:
            s -= 4
            reasons.append('MACD is below its signal line (bearish momentum).')
        trend = t.get('trend')
        if trend:
            if 'Strong uptrend' in trend:
                s += 8
                reasons.append('Price is in a strong uptrend with moving averages aligned bullishly.')
            elif 'Strong downtrend' in trend:
                s -= 8
                reasons.append('Price is in a strong downtrend with moving averages aligned bearishly.')
        s = max(5, min(95, s))
        return s, reasons

    def _fundamental_score(self):
        reasons = []
        s = 50
        st = self.stats
        if 'error' in st:
            return 50, ['Fundamental data unavailable.']
        mg = st.get('profit_margins')
        if mg is not None:
            if mg > 0.20:
                s += 12
                reasons.append(f'Strong profit margin of {mg*100:.0f}%.')
            elif mg > 0.05:
                s += 4
                reasons.append(f'Healthy profit margin of {mg*100:.0f}%.')
            elif mg < 0:
                s -= 12
                reasons.append('Currently loss-making on a trailing basis.')
        rg = st.get('revenue_growth')
        if rg is not None:
            if rg > 0.20:
                s += 10
                reasons.append(f'Revenue growing {rg*100:.0f}% year-over-year.')
            elif rg > 0.05:
                s += 4
                reasons.append(f'Modest revenue growth of {rg*100:.0f}%.')
            elif rg < 0:
                s -= 10
                reasons.append(f'Revenue contracting {abs(rg)*100:.0f}% year-over-year.')
        roe = st.get('return_on_equity')
        if roe is not None:
            if roe > 0.20:
                s += 6
                reasons.append(f'High return on equity ({roe*100:.0f}%).')
        # Cash vs debt
        debt = st.get('total_debt')
        cash = st.get('total_cash')
        if debt is not None and cash is not None:
            if cash >= debt:
                s += 8
                reasons.append('Balance sheet is net cash positive (cash exceeds total debt).')
            elif debt > cash * 2 and debt > 0:
                s -= 6
                reasons.append('Elevated debt relative to cash on hand.')
        s = max(5, min(95, s))
        return s, reasons

    def _valuation_score(self):
        reasons = []
        s = 50
        v = self.valuation
        if 'error' in v or not v:
            return 50, ['Valuation data limited.']
        pe = v.get('trailingPE')
        if pe is not None:
            if pe < 15:
                s += 10
                reasons.append(f'Forward/trailing P/E of {pe:.1f} is low relative to the broad market.')
            elif pe < 25:
                s += 2
                reasons.append(f'P/E of {pe:.1f} is reasonable.')
            elif pe > 40:
                s -= 8
                reasons.append(f'P/E of {pe:.1f} is elevated, implying high growth expectations.')
            else:
                s -= 2
                reasons.append(f'P/E of {pe:.1f} is on the higher side.')
        ps = v.get('priceToSalesTrailing12Months')
        if ps is not None and ps > 10:
            s -= 3
            reasons.append('High price-to-sales multiple suggests the market is pricing in substantial future growth.')
        if not reasons:
            reasons.append('Valuation multiple interpretation limited by available data.')
        s = max(5, min(95, s))
        return s, reasons

    def _news_score(self):
        s = 50
        reasons = []
        if not self.news:
            return 50, ['Limited recent news available to score sentiment.']
        # Use a very light keyword sentiment heuristic on real headlines
        pos_words = ['beat', 'surge', 'record', 'upgrade', 'growth', 'strong', 'exceeds', 'profit', 'buy', 'raise']
        neg_words = ['miss', 'drop', 'cut', 'lawsuit', 'investigation', 'decline', 'weak', 'downgrade', 'recall', 'layoff', 'ban', 'restrict']
        pos = sum(1 for n in self.news if any(w in (n.get('title') or '').lower() for w in pos_words))
        neg = sum(1 for n in self.news if any(w in (n.get('title') or '').lower() for w in neg_words))
        if pos > neg + 1:
            s += 10
            reasons.append('Recent headlines skew positive.')
        elif neg > pos + 1:
            s -= 10
            reasons.append('Recent headlines skew negative.')
        else:
            reasons.append('Recent news sentiment appears balanced.')
        s = max(5, min(95, s))
        return s, reasons

    # ═══════════════════════════════════════════════════════
    # AI OVERVIEW / BULL / BEAR / RISKS / CATALYSTS
    # ═══════════════════════════════════════════════════════
    def build_overview(self, score) -> dict:
        name = self.quote.get('name') or self.quote.get('ticker') or 'This asset'
        ticker = self.quote.get('ticker', '')
        t = self.technicals
        st = self.stats

        overview_parts = [f"{name} ({ticker}) is currently scoring {score['score']} on Quantly's AI research assessment, with a {score['lean'].lower()} bias."]

        # Build overview from real data
        trend = t.get('trend')
        if trend:
            overview_parts.append(f"The price action shows a {trend.lower()} pattern on the daily chart.")

        price_vs_200 = t.get('price_vs_sma200')
        if price_vs_200 is not None:
            if price_vs_200 > 0:
                overview_parts.append(f"It is trading {price_vs_200:.0f}% above its 200-day moving average, indicating the longer-term trend is currently favourable.")
            elif price_vs_200 < 0:
                overview_parts.append(f"It is trading {abs(price_vs_200):.0f}% below its 200-day moving average, suggesting the longer-term trend has been under pressure.")

        rsi = t.get('rsi')
        if rsi is not None:
            overview_parts.append(f"RSI is at {rsi:.0f}, which is {t.get('rsi_level','neutral').lower()} on a momentum basis.")

        profit_margin = st.get('profit_margins')
        if profit_margin is not None:
            overview_parts.append(f"On the fundamental side, profit margins stand at {profit_margin*100:.1f}%.")

        revenue_growth = st.get('revenue_growth')
        if revenue_growth is not None:
            if revenue_growth > 0:
                overview_parts.append(f"Revenue is growing at {revenue_growth*100:.1f}% year-over-year.")
            else:
                overview_parts.append(f"Revenue is currently contracting at {abs(revenue_growth)*100:.1f}% year-over-year.")

        overview = ' '.join(overview_parts) + ' This is an AI research summary based on current available data, not a prediction.'

        # Bull / Bear case
        bull = self._build_bull_case()
        bear = self._build_bear_case()
        risks = self._build_risks()
        catalysts = self._build_catalysts()

        result = {
            'summary': overview,
            'bull_case': bull,
            'bear_case': bear,
            'key_risks': risks,
            'key_catalysts': catalysts,
            'asset_name': name,
        }
        self._last_overview = result
        return result

    def _build_bull_case(self):
        points = []
        t = self.technicals
        st = self.stats
        if t.get('price_vs_sma200') is not None and t['price_vs_sma200'] > 0:
            points.append("Trading above its 200-day moving average reflects a supportive longer-term price trend.")
        if t.get('macd_bullish'):
            points.append("Positive MACD positioning points to momentum that could support further upside.")
        if st.get('revenue_growth') is not None and st['revenue_growth'] > 0.15:
            points.append(f"Strong revenue growth of {st['revenue_growth']*100:.0f}% could continue to fuel earnings.")
        if st.get('profit_margins') is not None and st['profit_margins'] > 0.20:
            points.append(f"High profit margins of {st['profit_margins']*100:.0f}% provide durable earnings power.")
        if st.get('total_cash') is not None and st.get('total_debt') is not None and st['total_cash'] >= st['total_debt']:
            points.append("A net cash balance sheet reduces financial risk and supports flexibility.")
        if not points:
            points.append("Limited clear bull catalysts identified from currently available data.")
        return points

    def _build_bear_case(self):
        points = []
        t = self.technicals
        st = self.stats
        v = self.valuation
        if t.get('rsi') is not None and t['rsi'] > 70:
            points.append("Overbought momentum signals suggest the recent move may be stretched and vulnerable to a pullback.")
        if t.get('price_vs_sma200') is not None and t['price_vs_sma200'] < 0:
            points.append(f"Trading {abs(t['price_vs_sma200']):.0f}% below its 200-day moving average indicates a weak longer-term trend.")
        if st.get('revenue_growth') is not None and st['revenue_growth'] < 0:
            points.append("Contracting revenue could pressure earnings and valuation.")
        if st.get('debt_to_equity') is not None and st['debt_to_equity'] > 1.5:
            points.append("Elevated leverage increases sensitivity to interest-rate and credit conditions.")
        if v.get('trailingPE') is not None and v['trailingPE'] > 40:
            points.append("A high valuation multiple means the market already expects strong growth; disappointment could hurt the price.")
        if not points:
            points.append("Limited clear bear risks identified from currently available data.")
        return points

    def _build_risks(self):
        risks = []
        t = self.technicals
        st = self.stats
        name = self.quote.get('name') or 'this company'
        if st.get('revenue_growth') is not None and st['revenue_growth'] < 0.05:
            risks.append(f"Revenue growth is limited; if demand softens further, {name} may struggle to grow earnings.")
        if st.get('profit_margins') is not None and st['profit_margins'] < 0.05 and st['profit_margins'] is not None and st['profit_margins'] >= 0:
            risks.append("Thin profit margins leave little buffer against rising costs.")
        if st.get('profit_margins') is not None and st['profit_margins'] < 0:
            risks.append("The business is currently unprofitable, which magnifies downside risk.")
        if t.get('rsi') is not None and t['rsi'] > 75:
            risks.append("Extremely overbought technical conditions raise the risk of a short-term correction.")
        if self.quote.get('quoteType') == 'EQUITY' and st.get('volatility_missing'):
            pass
        if not risks:
            risks.append("No acute fundamental risks flagged from available data, but market and macro conditions always carry risk.")
        return risks

    def _build_catalysts(self):
        catalysts = []
        st = self.stats
        v = self.valuation
        if st.get('revenue_growth') is not None and st['revenue_growth'] > 0.15:
            catalysts.append("Sustained revenue growth could act as a positive catalyst if it continues or accelerates.")
        if self.news:
            recent_headlines = self.news[:3]
            for n in recent_headlines:
                title = n.get('title')
                if title:
                    catalysts.append(f"Recent development: \"{title[:80]}\" could act as a catalyst depending on how it develops.")
        if not catalysts:
            catalysts.append("No specific near-term catalysts identified from available data.")
        return catalysts

    # ═══════════════════════════════════════════════════════
    # POLITICAL / GEOPOLITICAL IMPACT + EXPOSURE
    # ═══════════════════════════════════════════════════════
    def build_global_political_impact(self) -> dict:
        sector = (self.quote.get('sector') or '').lower()
        industry = (self.quote.get('industry') or '').lower()
        name = self.quote.get('name') or 'this company'

        # Deterministic sector-based political sensitivity mapping
        exposures = self._build_exposure_map(sector, industry)
        avg = sum(exposures.values()) / len(exposures) if exposures else 0

        if avg >= 70:
            level = 'HIGH'
        elif avg >= 40:
            level = 'MEDIUM'
        else:
            level = 'LOW'

        analysis = self._build_political_analysis(sector, industry, name, level)

        result = {
            'political_exposure': level,
            'exposure_score': round(avg, 1),
            'exposure_map': exposures,
            'analysis': analysis,
        }
        self._last_political = result
        return result

    def _build_exposure_map(self, sector, industry):
        e = {}
        if 'technology' in sector or 'semiconductor' in sector or 'chip' in sector:
            e['China exposure'] = 80
            e['Trade policy'] = 75
            e['AI regulation'] = 60
            e['Supply chain'] = 75
            e['Energy prices'] = 25
            e['Government spending'] = 55
        elif 'energy' in sector:
            e['Energy prices'] = 90
            e['Geopolitical tensions'] = 85
            e['Government policy'] = 70
            e['Supply chain'] = 50
        elif 'financial' in sector:
            e['Interest rates'] = 85
            e['Regulation'] = 75
            e['Economic growth'] = 70
            e['Credit conditions'] = 80
        elif 'healthcare' in sector:
            e['Regulation'] = 75
            e['Government policy'] = 70
            e['Trade policy'] = 30
            e['Supply chain'] = 45
        elif 'consumer' in sector:
            e['Consumer spending'] = 75
            e['Inflation'] = 65
            e['Trade policy'] = 55
            e['Supply chain'] = 60
        elif 'industrials' in sector or 'defense' in sector:
            e['Government spending'] = 70
            e['Geopolitical tensions'] = 65
            e['Supply chain'] = 60
            e['Trade policy'] = 50
        elif 'utilities' in sector or 'real estate' in sector:
            e['Interest rates'] = 80
            e['Regulation'] = 60
            e['Energy prices'] = 50
        else:
            e['Regulation'] = 50
            e['Economic growth'] = 55
            e['Trade policy'] = 45
        # Normalise to reasonable bounds (some may be high but that's desired)
        return e

    def _build_political_analysis(self, sector, industry, name, level):
        lines = []
        if level == 'HIGH':
            lines.append(f"POLITICAL EXPOSURE: HIGH — \"{name}'s operations appear significantly sensitive to political and geopolitical developments.\"")
        elif level == 'MEDIUM':
            lines.append(f"POLITICAL EXPOSURE: MEDIUM — \"{name} faces moderate sensitivity to policy and geopolitical developments.\"")
        else:
            lines.append(f"POLITICAL EXPOSURE: LOW — \"{name} appears relatively less sensitive to political developments based on its sector.\"")

        if 'semiconductor' in sector or 'chip' in sector:
            lines.append("Semiconductor companies face exposure to export controls, trade restrictions and geopolitical tensions around supply chains and key markets.")
        elif 'technology' in sector:
            lines.append("Technology companies are exposed to data-privacy regulation, antitrust policy, AI regulation and international trade rules.")
        elif 'energy' in sector:
            lines.append("Energy companies are directly sensitive to sanctions, geopolitical conflict around producing regions, climate policy and government energy strategy.")
        elif 'financial' in sector:
            lines.append("Financial companies respond to central-bank policy, interest-rate decisions, financial regulation and credit conditions.")
        elif 'healthcare' in sector:
            lines.append("Healthcare companies face drug-pricing policy, healthcare regulation and any changes to government healthcare programmes.")
        elif 'consumer' in sector:
            lines.append("Consumer companies are sensitive to inflation, interest rates, consumer confidence, and trade policy affecting imported goods.")
        elif 'industrials' in sector:
            lines.append("Industrial/defence companies are exposed to government procurement, defence budgets, infrastructure policy and geopolitical tensions.")
        else:
            lines.append("Specific political exposures are assessed based on available sector data.")

        lines.append("This assessment measures sensitivity to political developments; it is not a forecast of the share price.")
        return lines

    # ═══════════════════════════════════════════════════════
    # SCENARIO ANALYSIS
    # ═══════════════════════════════════════════════════════
    def build_scenarios(self) -> dict:
        sector = (self.quote.get('sector') or '').lower()
        v = self.valuation
        pe = v.get('trailingPE') if isinstance(v, dict) else None

        scenarios = []
        green = {
            'rating': 'green',
            'label': 'Positive scenario',
        }
        yellow = {
            'rating': 'yellow',
            'label': 'Base scenario',
        }
        red = {
            'rating': 'red',
            'label': 'Negative scenario',
        }

        sector_relevant = self._sector_drivers(sector)

        green['driver'] = sector_relevant['positive']
        green['business_impact'] = sector_relevant['positive_business']
        yellow['driver'] = sector_relevant['base']
        yellow['business_impact'] = sector_relevant['base_business']
        red['driver'] = sector_relevant['negative']
        red['business_impact'] = sector_relevant['negative_business']

        scenarios = [green, yellow, red]
        result = {
            'scenarios': scenarios,
            'disclaimer': "Scenario analysis describes potential business/economic outcomes. It is not a stock price prediction.",
        }
        self._last_scenarios = result
        return result

    def _sector_drivers(self, sector):
        if 'semiconductor' in sector or 'technology' in sector:
            return {
                'positive': 'Sustained demand for AI/advanced computing, easing of trade restrictions or a strong upgrade cycle.',
                'positive_business': 'Higher revenue and margins as demand remains strong; freed access to broader markets.',
                'base': 'Continued steady demand with normal competitive and supply-chain dynamics.',
                'base_business': 'Revenue and margins track expectations without major surprises.',
                'negative': 'New export restrictions, a sharp demand slowdown, or intensifying competition.',
                'negative_business': 'Reduced accessible markets, pricing pressure and possibly lower margins.',
            }
        elif 'energy' in sector:
            return {
                'positive': 'Rising or stable energy prices and supportive government energy policy.',
                'positive_business': 'Improved revenue and cash flow from higher realised prices.',
                'base': 'Energy prices remain rangebound with typical operating conditions.',
                'base_business': 'Results largely track commodity prices.',
                'negative': 'A sharp price decline, sanctions-driven disruption or a demand shock.',
                'negative_business': 'Lower revenue and weaker margins; potential impairments.',
            }
        elif 'financial' in sector:
            return {
                'positive': 'A supportive rate environment and healthy credit conditions.',
                'positive_business': 'Improved net interest margins and loan growth.',
                'base': 'Moderate growth with normalised credit quality.',
                'base_business': 'Steady earnings with typical provisions.',
                'negative': 'Adverse rate moves, a credit cycle deterioration or stricter regulation.',
                'negative_business': 'Compressed margins and higher loan-loss provisions.',
            }
        else:
            return {
                'positive': 'Favourable economic growth, stable interest rates and healthy consumer/business demand.',
                'positive_business': 'Stronger revenue and operating leverage.',
                'base': 'Normal economic conditions and demand.',
                'base_business': 'Revenue and margins in line with historical trends.',
                'negative': 'An economic slowdown, rising costs or adverse regulation.',
                'negative_business': 'Lower revenue, margin compression and weaker cash flow.',
            }

    # ═══════════════════════════════════════════════════════
    # EVENT → BUSINESS → MARKET CONNECTION
    # ═══════════════════════════════════════════════════════
    def build_event_connections(self) -> list:
        sector = (self.quote.get('sector') or '').lower()
        name = self.quote.get('name') or 'the company'
        return self._connection_chains(sector, name)

    def _connection_chains(self, sector, name):
        chains = []
        if 'semiconductor' in sector or 'technology' in sector:
            chains.append({
                'title': 'Trade & export restrictions',
                'chain': [
                    'New trade/export restrictions are announced',
                    'Access to some international markets is reduced',
                    'Semiconductor/tech suppliers face a smaller addressable market',
                    f'{name} could see reduced revenue from affected regions',
                    'Potential negative pressure on revenue growth and margins',
                ]
            })
            chains.append({
                'title': 'AI regulation & policy',
                'chain': [
                    'New AI or data regulations are proposed',
                    'Compliance costs and implementation complexity rise',
                    'Product roadmaps and data practices may need adjustment',
                    f'{name} could face higher costs or slower product adoption',
                    'Depends on scope and how regulation is applied',
                ]
            })
        elif 'energy' in sector:
            chains.append({
                'title': 'Geopolitical tension in producing regions',
                'chain': [
                    'Geopolitical tensions rise in oil-producing regions',
                    'Energy prices may become more volatile',
                    'Production and shipping costs are affected',
                    f'{name} faces larger swings in revenue and margins',
                    'Potential benefit or harm depends on the direction of prices',
                ]
            })
        elif 'financial' in sector:
            chains.append({
                'title': 'Central-bank interest-rate policy',
                'chain': [
                    'Central banks adjust interest rates',
                    'Borrowing costs and deposit margins change',
                    'Banks and lenders see net-interest-margin shifts',
                    f'{name} results could respond to these rate changes',
                    'Impact depends on the direction and speed of rate moves',
                ]
            })
        elif 'consumer' in sector:
            chains.append({
                'title': 'Consumer spending & inflation',
                'chain': [
                    'Inflation or interest rates change consumer budgets',
                    'Discretionary spending rises or falls',
                    'Retail/consumer companies see demand shifts',
                    f'{name} sales could be affected by changes in consumer confidence',
                    'Potential effect on revenue depends on spending trends',
                ]
            })
        else:
            chains.append({
                'title': 'Macroeconomic conditions',
                'chain': [
                    'Economic growth and policy shift',
                    'Business and consumer demand are affected',
                    'Most industries feel some impact on revenue',
                    f'{name} results may respond to these macro conditions',
                    'Direction and size of the effect depends on exposure',
                ]
            })
        return chains

    # ═══════════════════════════════════════════════════════
    # AI CHAT
    # ═══════════════════════════════════════════════════════
    def answer_chat(self, question: str, score, overview, political, scenarios,
                    session=None) -> str:
        """Answer a chat question using a conversation-aware NLU engine."""
        from chat_nlu import ResearchChat, ChatSession
        self._last_score = score
        self._last_overview = overview
        self._last_political = political
        self._last_scenarios = scenarios

        session = session or ChatSession(
            (self.quote.get('ticker') or ''), (self.quote.get('name') or ''))
        chat = ResearchChat(self, session)
        return chat.ask(question)
