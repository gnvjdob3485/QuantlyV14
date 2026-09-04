"""
Research platform API blueprint.

Provides the asset research dashboard, markets overview, watchlist and AI chat
endpoints for the new AI finance intelligence platform. Mounted onto the main
Flask app alongside the existing Quant Lab strategy endpoints.
"""

import traceback
import time
from flask import Blueprint, request, jsonify
from research_data import DataIntelligence
from ai_research import AIResearchEngine
from watchlist import Watchlist
from asset_catalog import search as catalog_search, all_assets as catalog_all
from chat_nlu import ChatSession
from functools import lru_cache

research_bp = Blueprint('research', __name__, url_prefix='/api')
watchlist = Watchlist()

# Per-ticker chat conversation state (persists across chat turns)
_chat_sessions = {}

# Simple in-memory cache to avoid hammering the data provider
_cache = {}


def cached(key, ttl=300, func=None):
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    result = func()
    _cache[key] = (now, result)
    return result


@research_bp.route('/asset/<ticker>', methods=['GET'])
def asset_research(ticker):
    ticker = ticker.strip().upper()

    # Fast pre-check: reject clearly invalid tickers before running the heavy
    # research pipeline (avoids long hangs / many failed upstream calls).
    # If the provider is unreachable/rate-limited, is_valid returns False just
    # like an invalid ticker — so we fall through to the heavier build() which
    # will surface a proper transient (502) error rather than blaming spelling.
    if DataIntelligence.is_valid(ticker) is False:
        def _sanity_check():
            try:
                q = DataIntelligence.get_quote(ticker)
                if isinstance(q, dict) and q.get('price') is None and q.get('name', '') == ticker:
                    raise ValueError("No market data available for this ticker.")
                return q
            except ValueError:
                raise
            except Exception:
                raise RuntimeError("transient")

        try:
            q = _sanity_check()
            # quote succeeded but is_valid said no - proceed with the full build
            quote_hint = q
        except ValueError:
            return jsonify({'error': 'No market data available for this ticker.',
                            'invalid_ticker': True}), 404
        except Exception:
            return jsonify({'error': 'Data temporarily unavailable. Please try again.',
                            'transient': True}), 502
    else:
        quote_hint = None

    try:
        data = cached(f'asset_{ticker}', ttl=180, func=lambda: _build_asset(ticker))
        # refresh watchlist flag live
        data = dict(data)
        data['in_watchlist'] = watchlist.has(ticker)
        return jsonify(data)
    except ValueError as e:
        # Genuinely no data for this ticker (invalid or provider blocking)
        return jsonify({'error': str(e), 'invalid_ticker': True}), 404
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': 'Data temporarily unavailable. Please try again.', 'transient': True}), 502


@research_bp.route('/asset/<ticker>/price', methods=['GET'])
def asset_price(ticker):
    ticker = ticker.strip().upper()
    timeframe = request.args.get('range', '1Y')
    try:
        data = cached(f'price_{ticker}_{timeframe}', ttl=120,
                      func=lambda: DataIntelligence.get_price_history(ticker, timeframe))
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@research_bp.route('/asset/<ticker>/competitors', methods=['GET'])
def asset_competitors(ticker):
    ticker = ticker.strip().upper()
    try:
        data = cached(f'comp_{ticker}', ttl=600,
                      func=lambda: DataIntelligence.get_competitors(ticker))
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@research_bp.route('/asset/<ticker>/holdings', methods=['GET'])
def asset_holdings(ticker):
    ticker = ticker.strip().upper()
    try:
        data = cached(f'holds_{ticker}', ttl=600,
                      func=lambda: DataIntelligence.get_holders(ticker))
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@research_bp.route('/asset/<ticker>/chat', methods=['POST'])
def asset_chat(ticker):
    ticker = ticker.strip().upper()
    body = request.get_json() or {}
    question = (body.get('question') or '').strip()
    if not question:
        return jsonify({'error': 'Question is required'}), 400

    try:
        # Reuse the dashboard's cached data (same 180s TTL cache as the asset
        # endpoint) to avoid refetching 7+ provider calls and rerunning 4 heavy
        # AI analyses on every single chat message.
        def _build_engine_from_cached():
            asset = cached(f'asset_{ticker}', ttl=180,
                           func=lambda: _build_asset(ticker))
            quote = asset.get('quote', {})
            ai = asset.get('ai', {})
            engine = AIResearchEngine(
                quote=quote,
                stats=asset.get('statistics', {}),
                technicals=asset.get('technicals', {}),
                valuation=asset.get('valuation', {}),
                news=asset.get('news', []),
            )
            return engine, ai

        try:
            engine, ai = _build_engine_from_cached()
        except Exception:
            # Cold start / cache miss: build from scratch (one-off cost)
            engine, ai = _build_engine_fresh(ticker)

        # Competitors and holders are not part of the dashboard response
        # but the NLU needs them. These are individually cached at 600s.
        engine._last_competitors = cached(
            f'comp_{ticker}', ttl=600,
            func=lambda: DataIntelligence.get_competitors(ticker))
        engine._last_holders = cached(
            f'holds_{ticker}', ttl=600,
            func=lambda: DataIntelligence.get_holders(ticker))

        # Reuse or create conversation session
        session = _chat_sessions.get(ticker)
        if session is None:
            session = ChatSession(ticker, engine.quote.get('name') or ticker)
            _chat_sessions[ticker] = session

        answer = engine.answer_chat(
            question,
            ai.get('score'),
            ai.get('overview'),
            ai.get('political'),
            ai.get('scenarios'),
            session=session,
        )
        return jsonify({'answer': answer})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def _build_asset(ticker):
    """Shared asset builder used by the asset endpoint and chat reuse."""
    warnings = []

    def safe(fn, label):
        try:
            return fn()
        except Exception as e:
            warnings.append(f"{label} temporarily unavailable.")
            return {'error': str(e)}

    quote = safe(lambda: DataIntelligence.get_quote(ticker), 'Quote')
    # If even the base quote failed, we have nothing to show.
    # An 'error' in the quote (price None + name None) means the provider
    # is down/rate-limited -> surface a transient error, not 'misspelled'.
    if isinstance(quote, dict):
        if quote.get('error') and quote.get('price') is None:
            raise RuntimeError("provider unavailable")
        if quote.get('price') is None and (quote.get('name') or '') == ticker:
            raise ValueError("No market data available for this ticker.")

    stats = safe(lambda: DataIntelligence.get_statistics(ticker), 'Fundamentals')
    financials = safe(lambda: DataIntelligence.get_financials(ticker), 'Financials')
    technicals = safe(lambda: DataIntelligence.get_technicals(ticker), 'Technicals')
    valuation = safe(lambda: DataIntelligence.get_valuation(ticker), 'Valuation')
    news = safe(lambda: DataIntelligence.get_news(ticker), 'News')
    analysts = safe(lambda: DataIntelligence.get_analyst_sentiment(ticker), 'Analyst data')

    engine = AIResearchEngine(
        quote=quote, stats=stats, technicals=technicals,
        valuation=valuation, news=news, financials=financials,
    )
    score = engine.compute_score()
    overview = engine.build_overview(score)
    political = engine.build_global_political_impact()
    scenarios = engine.build_scenarios()
    connections = engine.build_event_connections()

    return {
        'quote': quote,
        'statistics': stats,
        'financials': financials,
        'technicals': technicals,
        'valuation': valuation,
        'analyst_sentiment': analysts,
        'news': news,
        'warnings': warnings,
        'ai': {
            'score': score,
            'overview': overview,
            'political': political,
            'scenarios': scenarios,
            'event_connections': connections,
        },
        'in_watchlist': watchlist.has(ticker),
        'fetched_at': time.time(),
    }


def _build_engine_fresh(ticker):
    """One-off full build for chat on cold start (no cached data yet)."""
    def safe(fn, label):
        try:
            return fn()
        except Exception:
            return {}

    quote = safe(lambda: DataIntelligence.get_quote(ticker), 'Quote')
    stats = safe(lambda: DataIntelligence.get_statistics(ticker), 'Stats')
    technicals = safe(lambda: DataIntelligence.get_technicals(ticker), 'Technicals')
    valuation = safe(lambda: DataIntelligence.get_valuation(ticker), 'Valuation')
    news = safe(lambda: DataIntelligence.get_news(ticker), 'News')

    engine = AIResearchEngine(
        quote=quote, stats=stats, technicals=technicals,
        valuation=valuation, news=news,
    )
    score = engine.compute_score()
    overview = engine.build_overview(score)
    political = engine.build_global_political_impact()
    scenarios = engine.build_scenarios()

    return engine, {
        'score': score, 'overview': overview,
        'political': political, 'scenarios': scenarios,
    }


@research_bp.route('/markets', methods=['GET'])
def markets():
    try:
        data = cached('markets', ttl=120, func=DataIntelligence.get_macro_snapshot)

        # Build a short "market today" text from the real data
        movers = sorted([v for v in data.values() if v.get('change') is not None],
                        key=lambda x: abs(x['change']), reverse=True)[:5]
        market_today = []
        if movers:
            top = movers[0]
            market_today.append(f"{top['name']} is the biggest mover, {'up' if top['change']>=0 else 'down'} {abs(top['change']):.2f}%.")
            up = [v for v in data.values() if v.get('change') is not None and v['change'] > 0]
            dn = [v for v in data.values() if v.get('change') is not None and v['change'] < 0]
            if up or dn:
                market_today.append(f"Across tracked markets, {len(up)} are higher and {len(dn)} are lower.")
        if not market_today:
            market_today.append("Market data is currently limited; check back shortly.")

        return jsonify({'assets': data, 'movers': movers, 'market_today': market_today})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@research_bp.route('/search', methods=['GET'])
def search():
    query = (request.args.get('q') or '').strip().upper()
    if len(query) < 1:
        return jsonify([])
    # 1) Fast catalog matches (stocks, crypto, ETFs, indices, forex) — no API budget used
    catalog_hits = catalog_search(query, limit=12)
    if catalog_hits:
        return jsonify(catalog_hits)
    # 2) If it's an exact plausible ticker not in the catalog, validate against the price feed
    if len(query) <= 12 and query.isalnum() or any(c in query for c in '^-$.'):
        result = DataIntelligence.get_quote(query)
        valid = result.get('price') is not None or result.get('name') != query
        if valid:
            return jsonify([{'ticker': query, 'name': result.get('name', query),
                              'price': result.get('price'), 'change_pct': result.get('change_pct'),
                              'category': 'Other'}])
    return jsonify([])


@research_bp.route('/browse', methods=['GET'])
def browse():
    """Return the curated catalog grouped by category for the Browse Assets view."""
    return jsonify({'categories': catalog_all()})


# ═════════ WATCHLIST ═════════
@research_bp.route('/watchlist', methods=['GET'])
def get_watchlist():
    return jsonify(watchlist.get_all())


@research_bp.route('/watchlist', methods=['POST'])
def add_watchlist():
    body = request.get_json() or {}
    ticker = (body.get('ticker') or '').strip().upper()
    if not ticker:
        return jsonify({'error': 'Ticker is required'}), 400
    quote = DataIntelligence.get_quote(ticker)
    ai_score = None
    try:
        technicals = DataIntelligence.get_technicals(ticker)
        valuation = DataIntelligence.get_valuation(ticker)
        engine = AIResearchEngine(quote=quote, technicals=technicals, valuation=valuation)
        ai_score = engine.compute_score()['score']
    except Exception:
        pass
    entry = watchlist.add(ticker, name=quote.get('name'), ai_score=ai_score,
                           price=quote.get('price'), change_pct=quote.get('change_pct'))
    return jsonify(entry)


@research_bp.route('/watchlist/<ticker>', methods=['DELETE'])
def remove_watchlist(ticker):
    if watchlist.remove(ticker):
        return jsonify({'ok': True})
    return jsonify({'error': 'Not found'}), 404
