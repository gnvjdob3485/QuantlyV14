/* ═══════════════════════════════════════════════════════════
   QUANTLY — AI Market Intelligence Platform (SPA)
   ═══════════════════════════════════════════════════════════ */

let charts = {};
let currentView = 'home';
let researchData = null;
let researchTicker = null;
let watchlistCache = [];

/* ─── helpers ─── */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const fmtPct = (v) => (v !== null && v !== undefined) ? (v >= 0 ? '+' : '') + v.toFixed(2) + '%' : '—';
const fmtNum = (v) => (v === null || v === undefined) ? '—' : Number(v).toLocaleString('en-US', {maximumFractionDigits: 2});
const fmtMoney = (v) => (v === null || v === undefined) ? '—' : '$' + Number(v).toLocaleString('en-US', {maximumFractionDigits: 0});
const clamp = (n, a, b) => Math.max(a, Math.min(b, n));

function showLoading(text = 'Loading...') {
    $('#loadingText').textContent = text;
    $('#loadingOverlay').classList.add('active');
}
function hideLoading() { $('#loadingOverlay').classList.remove('active'); }

async function api(url, body = null, method = null) {
    const opts = { headers: { 'Content-Type': 'application/json' } };
    if (body && !method) { opts.method = 'POST'; opts.body = JSON.stringify(body); }
    else if (method) { opts.method = method; if (body) opts.body = JSON.stringify(body); }
    const r = await fetch(url, opts);
    const data = await r.json().catch(() => ({ error: 'Invalid server response (' + r.status + ')' }));
    data.__status = r.status;
    if (!r.ok && data.error) throw new Error(data.error);
    return data;
}

/* ─── router ─── */
function buildHash(view, param) {
    if (view === 'research' && param) return '#research/' + param.toUpperCase();
    if (view === 'home') return '#/';
    if (view === 'research') return '#research';
    if (view === 'markets') return '#markets';
    if (view === 'browse') return '#browse';
    if (view === 'quantlab') return '#quantlab';
    if (view === 'watchlist') return '#watchlist';
    return '#/';
}
function go(view, param) {
    // Update the URL hash for shareable links (without clobbering back/forward too aggressively)
    try { location.hash = buildHash(view, param); } catch (e) {}
    render(view, param);
}
function render(view, param) {
    currentView = view;
    window.scrollTo(0, 0);
    $('#appRoot').innerHTML = '';
    // update nav active
    $$('.nav-link').forEach(n => n.classList.toggle('active', n.dataset.page === view));
    const navMap = {'home':'Home','research':'Research','markets':'Markets','quantlab':'Quant Lab','watchlist':'Watch'};
    $$('.mobile-nav-item').forEach(n => {
        const label = navMap[view] || '';
        n.classList.toggle('active', n.textContent.trim().toLowerCase() === label.toLowerCase());
    });
    switch (view) {
        case 'home': renderHome(); break;
        case 'markets': renderMarkets(); break;
        case 'research': renderResearch(param); break;
        case 'watchlist': renderWatchlist(); break;
        case 'quantlab': renderQuantLab(); break;
        case 'browse': renderBrowse(); break;
    }
}
function parseHash() {
    const h = (location.hash || '').replace(/^#\/?/, '');
    if (h.startsWith('research/')) return { view: 'research', param: decodeURIComponent(h.slice('research/'.length) || '') };
    if (h.startsWith('research')) return { view: 'research', param: '' };
    if (h.startsWith('markets')) return { view: 'markets', param: null };
    if (h.startsWith('browse')) return { view: 'browse', param: null };
    if (h.startsWith('quantlab')) return { view: 'quantlab', param: null };
    if (h.startsWith('watchlist')) return { view: 'watchlist', param: null };
    return { view: 'home', param: null };
}

/* ═══════════════════════════ HOME ═══════════════════════════ */
async function renderHome() {
    const root = $('#appRoot');
    root.innerHTML = `
      <div class="view">
        <div class="hero">
          <div class="hero-badge">✦ AI Market Intelligence · Educational</div>
          <h1>Ask what's happening with<br><span class="grad-text">any asset</span> — in seconds</h1>
          <p class="hero-sub">Combine live market data, fundamentals, technicals, news, politics and macro into a single AI research dashboard.</p>
          <div class="hero-search">
            <input id="homeSearch" type="text" placeholder="Enter a ticker or search all assets, e.g. NVDA, BTCUSD, SPY..." onkeydown="homeSearchKey(event)" oninput="homeSearchAutocomplete()">
            <button class="btn btn-primary" onclick="goResearchFromHome()">Research</button>
          </div>
          <div id="homeSearchDropdown" class="search-dropdown"></div>
          <div class="hero-trending">
            <span>Popular:</span>
            ${['NVDA','AAPL','TSLA','BTCUSD','SPY','EURUSD'].map(t => `<span class="chip" onclick="go('research','${t}')">${t}</span>`).join('')}
            <span class="chip" onclick="go('browse')" style="border-color:var(--purple);color:var(--purple-2);">Browse all assets →</span>
          </div>
        </div>

        <div class="section-head" style="margin-top:30px;"><h2>Markets at a glance</h2><p>Live snapshot</p></div>
        <div id="homeMarkets" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:14px;">
          <div style="grid-column:1/-1;text-align:center;color:var(--text-dim);padding:30px;">Loading markets...</div>
        </div>

        <div class="section-head" style="margin-top:34px;"><h2>Explore Quantly</h2></div>
        <div class="grid-3">
          <div class="feature-card" onclick="go('markets')" style="cursor:pointer;">
            <div class="fc-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2"><path d="M18 20V10"/><path d="M12 20V4"/><path d="M6 20v-6"/></svg></div>
            <h3>Markets</h3><p>Live global indices, crypto, commodities, FX, rates and volatility at a glance.</p>
          </div>
          <div class="feature-card" onclick="go('watchlist')" style="cursor:pointer;">
            <div class="fc-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#f472b6" stroke-width="2"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg></div>
            <h3>Watchlist</h3><p>Save assets and monitor AI scores and catalysts in one place.</p>
          </div>
          <div class="feature-card" onclick="go('quantlab')" style="cursor:pointer;">
            <div class="fc-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg></div>
            <h3>Quant Lab</h3><p>Describe a strategy in plain English and backtest it with AI robustness analysis.</p>
          </div>
        </div>
        <div class="disclaimer">Quantly provides educational market intelligence. Research assessments are AI-generated from public data and are not financial advice or guaranteed predictions.</div>
      </div>`;

    loadHomeMarkets();
}

function goResearchFromHome() {
    const t = $('#homeSearch').value.trim().toUpperCase();
    if (t) go('research', t);
}

let homeSearchDebounce;
function homeSearchAutocomplete() {
    clearTimeout(homeSearchDebounce);
    const input = $('#homeSearch');
    const dd = $('#homeSearchDropdown');
    const q = input.value.trim();
    if (!q) { dd.classList.remove('show'); return; }
    homeSearchDebounce = setTimeout(async () => {
        try {
            const r = await api(`/api/search?q=${encodeURIComponent(q)}`);
            if (r.length) {
                dd.innerHTML = r.map(it => `<div class="search-item" onclick="go('research','${it.ticker}');input.value='';dd.classList.remove('show');">
                    <span><span class="si-ticker">${it.ticker}</span> <span class="si-name">${it.name||''}</span></span><span class="si-label">${it.category||''}</span></div>`).join('');
            } else dd.innerHTML = '<div class="search-empty">No matches — try a ticker like NVDA</div>';
            dd.classList.add('show');
        } catch { dd.classList.remove('show'); }
    }, 350);
}

function homeSearchKey(e) {
    if (e.key === 'Enter') goResearchFromHome();
    else homeSearchAutocomplete();
}

async function loadHomeMarkets() {
    try {
        const m = await api('/api/markets');
        const el = $('#homeMarkets');
        const order = ['^GSPC','^IXIC','^DJI','^GDAXI','^FTSE','^N225','BTC-USD','GC=F','CL=F','DX-Y.NYB','^TNX','^VIX'];
        let html = '';
        order.forEach(sym => {
            const a = m.assets[sym];
            if (!a) return;
            const cls = (a.change || 0) >= 0 ? 'pos' : 'neg';
            const sign = (a.change || 0) >= 0 ? '▲' : '▼';
            html += `<div class="market-row" style="background:var(--panel);border:1px solid var(--border);border-radius:12px;flex-direction:column;align-items:flex-start;gap:6px;">
              <div class="m-name">${a.name}</div>
              <div class="m-val ${cls}">${sign} ${fmtNum(a.price)}</div>
              <div style="font-family:var(--mono);font-size:12px;color:${cls==='pos'?'var(--green)':'var(--red)'};">${fmtPct(a.change)}</div>
            </div>`;
        });
        el.innerHTML = html || '<div style="grid-column:1/-1;text-align:center;color:var(--text-dim);">Market data temporarily unavailable.</div>';
    } catch {
        $('#homeMarkets').innerHTML = '<div style="grid-column:1/-1;text-align:center;color:var(--text-dim);">Market data temporarily unavailable.</div>';
    }
}

/* ═══════════════════════════ MARKETS ═══════════════════════════ */
async function renderMarkets() {
    $('#appRoot').innerHTML = `<div class="view">
      <div class="section-head"><h2>Markets</h2><p>Live global snapshot</p></div>
      <div id="marketBody"><div style="text-align:center;color:var(--text-dim);padding:60px;">Loading markets...</div></div>
    </div>`;
    try {
        const m = await api('/api/markets');
        const grp = {
            'Indices': ['^GSPC','^IXIC','^DJI','^GDAXI','^FTSE','^N225','^VIX'],
            'Crypto & Commodities': ['BTC-USD','GC=F','CL=F'],
            'Currencies': ['EURUSD=X','GBPUSD=X','DX-Y.NYB'],
            'Rates': ['^TNX'],
        };
        let html = '';
        const mkTable = (syms) => syms.map(sym => {
            const a = m.assets[sym]; if (!a) return '';
            const cls = (a.change || 0) >= 0 ? 'pos' : 'neg';
            const sign = (a.change || 0) >= 0 ? '▲' : '▼';
            return `<div class="market-row"><div class="m-name">${a.name}</div>
              <div style="display:flex;align-items:center;gap:24px;">
                <span class="${cls}" style="font-family:var(--mono);font-size:13px;">${sign} ${fmtPct(a.change)}</span>
                <span class="m-val ${cls}">${fmtNum(a.price)}</span>
              </div></div>`;
        }).join('');
        for (const [name, syms] of Object.entries(grp)) {
            html += `<div class="card" style="margin-bottom:20px;"><div class="card-title">${name}</div>${mkTable(syms) || '<div style="color:var(--text-dim);font-size:13px;">Data unavailable</div>'}</div>`;
        }
        if (m.market_today && m.market_today.length) {
            html = `<div class="card panel-glow" style="margin-bottom:20px;"><div class="card-title">Market today</div>
              ${m.market_today.map(x => `<p style="font-size:14px;color:var(--text-muted);margin-bottom:8px;">${x}</p>`).join('')}
            </div>` + html;
        }
        $('#marketBody').innerHTML = html;
    } catch (e) {
        $('#marketBody').innerHTML = `<div class="error-box">Could not load market data: ${e.message}</div>`;
    }
}

/* ═══════════════════════════ RESEARCH ═══════════════════════════ */
async function renderResearch(ticker) {
    if (!ticker) {
        // Show a dedicated research landing with search
        const root = $('#appRoot');
        root.innerHTML = `
          <div class="view">
            <div class="section-head"><h2>Asset Research</h2><p>Enter a ticker to view the AI research dashboard</p></div>
            <div class="card panel-glow" style="max-width:560px;margin:0 auto 30px;">
              <div class="card-title">Search an asset</div>
              <div style="display:flex;gap:10px;">
                <input class="input" id="researchLandingInput" type="text" placeholder="e.g. NVDA, AAPL, TSLA..." onkeydown="if(event.key==='Enter'){const t=this.value.trim().toUpperCase();if(t)go('research',t);}">
                <button class="btn btn-primary" onclick="const t=document.getElementById('researchLandingInput').value.trim().toUpperCase();if(t)go('research',t);">Research</button>
              </div>
            </div>
            <div class="section-head"><div class="card-title" style="margin:0;">Try these</div></div>
            <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:12px;">
              ${['NVDA','AAPL','TSLA','MSFT','JPM','XOM'].map(t => `<span class="chip" onclick="go('research','${t}')">${t}</span>`).join('')}
              ${['BTCUSD','ETHUSD','SOLUSD'].map(t => `<span class="chip" style="border-color:var(--yellow-soft);color:var(--yellow);" onclick="go('research','${t}')">${t}</span>`).join('')}
              ${['SPY','QQQ','GLD'].map(t => `<span class="chip" style="border-color:var(--green-soft);color:var(--green);" onclick="go('research','${t}')">${t}</span>`).join('')}
              ${['^GSPC','^VIX'].map(t => `<span class="chip" style="border-color:var(--pink-soft,var(--accent-2));color:var(--pink-2);" onclick="go('research','${t}')">${t}</span>`).join('')}
              <span class="chip" onclick="go('browse')" style="border-color:var(--purple);color:var(--purple-2);">Browse all assets →</span>
            </div>
          </div>`;
        document.getElementById('researchLandingInput').focus();
        return;
    }
    const root = $('#appRoot');
    showLoading(`Researching ${ticker.toUpperCase()}...`);
    root.innerHTML = `<div class="view"><div class="section-head" style="grid-column:1/-1;"><h2>Asset Research</h2><p>${ticker.toUpperCase()}</p></div>
      <div style="text-align:center;color:var(--text-dim);padding:60px;">Loading research dashboard...</div></div>`;
    try {
        researchTicker = ticker.toUpperCase();
        researchData = await api(`/api/asset/${researchTicker}`);
        if (researchData.error) throw new Error(researchData.error);
        renderResearchDashboard(researchData);
    } catch (e) {
        hideLoading();
        const msg = String(e.message || '');
        const isInvalid = msg.includes('invalid_ticker') || msg.includes('No market data available') || msg.includes('404') || msg.includes('No market');
        const title = isInvalid
            ? `No data found for <strong>${ticker.toUpperCase()}</strong>.`
            : `Data temporarily unavailable for <strong>${ticker.toUpperCase()}</strong>.`;
        const sub = isInvalid
            ? 'The ticker symbol could not be found. Check the spelling (e.g. NVDA, AAPL, MSFT) and try again.'
            : 'The market data provider was unreachable or rate-limited. This is usually temporary — please retry.';
        const retry = !isInvalid
            ? `<button class="btn btn-primary" style="margin-right:8px;" onclick="go('research','${ticker.toUpperCase()}')">Retry</button>`
            : '';
        root.innerHTML = `<div class="view"><div class="empty-state"><div class="icon">${isInvalid?'🔍':'⚠️'}</div>
          <h3 style="margin-bottom:10px;">${title}</h3><p style="color:var(--text-muted);margin-bottom:20px;">${sub}</p>
          <div>${retry}<button class="btn btn-secondary" onclick="go('home')">Back to home</button></div></div></div>`;
    }
}

function renderResearchDashboard(d) {
    hideLoading();
    const root = $('#appRoot');
    const q = d.quote, sc = d.ai.score, ov = d.ai.overview, pol = d.ai.political;
    const tech = d.technicals, st = d.statistics, val = d.valuation;
    // Defensive: guarantee arrays/objects exist so a partial data payload never
    // blanks the whole page. Real provider data is complete, but this hardens
    // against provider outages.
    const arr = (x) => Array.isArray(x) ? x : [];
    ov.bull_case = arr(ov.bull_case);
    ov.bear_case = arr(ov.bear_case);
    ov.key_risks = arr(ov.key_risks);
    ov.key_catalysts = arr(ov.key_catalysts);
    pol.exposure_map = (pol.exposure_map && typeof pol.exposure_map === 'object') ? pol.exposure_map : {};
    sc.components = sc.components || {};
    sc.news_reason = arr(sc.news_reason);
    sc.technical_reason = arr(sc.technical_reason);
    d.news = arr(d.news);
    d.ai.event_connections = arr(d.ai.event_connections);
    d.ai.scenarios.scenarios = arr(d.ai.scenarios.scenarios);
    d.warnings = arr(d.warnings);
    const leanTag = sc.lean === 'Bullish' ? 'tag-green' : sc.lean === 'Bearish' ? 'tag-red' : 'tag-yellow';
    const changeCls = (q.change_pct || 0) >= 0 ? 'pos' : 'neg';
    const watchBtn = d.in_watchlist
        ? `<button class="btn btn-secondary btn-sm" onclick="toggleWatch('${q.ticker}', true)">✓ Watchlisted</button>`
        : `<button class="btn btn-primary btn-sm" onclick="toggleWatch('${q.ticker}', false)">＋ Watchlist</button>`;

    root.innerHTML = `
    <div class="view">
      ${d.warnings && d.warnings.length ? `<div class="warn-box" style="margin-bottom:18px;display:flex;align-items:flex-start;gap:8px;">
        <span>⚠️</span><div>${d.warnings.join(' ')} Some sections below may show fewer details.</div></div>` : ''}
      <div class="research-header">
        <div>
          <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
            <span class="ticker-name">${q.name || q.ticker}</span>
            <span class="ticker-sym">${q.ticker}</span>
            <span class="tag ${leanTag}" style="margin-left:4px;">${sc.lean} · ${sc.score}/100</span>
            <span class="pill ${pol.political_exposure==='HIGH'?'high':pol.political_exposure==='MEDIUM'?'medium':'low'}"><span class="pill-dot"></span>Political: ${pol.political_exposure}</span>
          </div>
          <div style="margin-top:14px;display:flex;align-items:baseline;gap:14px;">
            <span class="ticker-price ${changeCls}">${fmtMoney(q.price)}</span>
            <span class="ticker-change ${changeCls}">${fmtPct(q.change_pct)}</span>
            <span style="color:var(--text-dim);font-size:13px;">${q.exchange || ''} · ${q.currency || ''}</span>
          </div>
          <div style="margin-top:10px;display:flex;gap:10px;align-items:center;">
            ${watchBtn}
            <button class="btn btn-secondary btn-sm" onclick="document.getElementById('chatPanel').scrollIntoView({behavior:'smooth'})">💬 Ask AI</button>
          </div>
        </div>
        <div class="score-ring">
          <svg width="130" height="130">
            <circle cx="65" cy="65" r="54" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="10"/>
            <circle cx="65" cy="65" r="54" fill="none" stroke="url(#scoreGrad)" stroke-width="10" stroke-linecap="round"
              stroke-dasharray="${(sc.score/100)*339}" stroke-dashoffset="${(1-sc.score/100)*0}" pathLength="339" style="transform:rotate(-90deg);transform-origin:65px 65px;"/>
            <defs><linearGradient id="scoreGrad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stop-color="#8b5cf6"/><stop offset="1" stop-color="#ec4899"/></linearGradient></defs>
          </svg>
          <div class="score-num"><div class="n">${sc.score}</div><div class="l">/ 100</div></div>
        </div>
      </div>

      <div class="grid-2" style="margin-bottom:20px;">
        <div class="ai-analysis">
          <div class="ai-banner"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2"><path d="M12 2a10 10 0 0 1 10 10c0 5.52-4.48 10-10 10S2 17.52 2 12 6.48 2 12 2z"/><path d="M12 8v4"/><path d="M12 16h.01"/></svg> AI Research Overview</div>
          <div style="font-size:14px;color:var(--text);line-height:1.7;">${ov.summary}</div>
        </div>
        <div>
          <div class="card" style="height:100%;">
            <div class="card-title">Key stats <span class="sub">· confidence ${sc.confidence}%</span></div>
            <div class="stat-2col">
              <div class="stat-item"><span class="k">Market cap</span><span class="v">${fmtMoney(q.market_cap)}</span></div>
              <div class="stat-item"><span class="k">52-wk position</span><span class="v">${tech['52w_position'] !== null && tech['52w_position'] !== undefined ? tech['52w_position'].toFixed(0)+'%' : '—'}</span></div>
              <div class="stat-item"><span class="k">P/E (trailing)</span><span class="v">${val.trailingPE ? val.trailingPE.toFixed(1) : '—'}</span></div>
              <div class="stat-item"><span class="k">Revenue growth</span><span class="v ${(st.revenue_growth||0)>=0?'pos':'neg'}">${st.revenue_growth !== null && st.revenue_growth !== undefined ? (st.revenue_growth*100).toFixed(1)+'%' : '—'}</span></div>
              <div class="stat-item"><span class="k">Profit margin</span><span class="v">${st.profit_margins !== null && st.profit_margins !== undefined ? (st.profit_margins*100).toFixed(1)+'%' : '—'}</span></div>
              <div class="stat-item"><span class="k">RSI</span><span class="v">${tech.rsi ? tech.rsi.toFixed(1) : '—'}</span></div>
              <div class="stat-item"><span class="k">Volatility (1Y)</span><span class="v">${tech.volatility_1y ? tech.volatility_1y.toFixed(1)+'%' : '—'}</span></div>
              <div class="stat-item"><span class="k">Trend</span><span class="v">${tech.trend || '—'}</span></div>
            </div>
          </div>
        </div>
      </div>

      <div class="card" style="margin-bottom:20px;">
        <div class="chart-header">
          <div class="chart-title">Price action</div>
          <div class="range-tabs" id="priceRangeTabs">
            ${['1D','1W','1M','6M','1Y','5Y','MAX'].map(r => `<button class="range-btn ${r==='1Y'?'active':''}" data-range="${r}" onclick="loadPriceChart('${r}')">${r}</button>`).join('')}
          </div>
        </div>
        <div class="chart-card-body">
          <canvas id="priceChart"></canvas>
        </div>
      </div>

      <div class="grid-2" style="margin-bottom:20px;">
        <div class="card">
          <div class="card-title" style="color:var(--green);">Bull case</div>
          <ul class="assumptions-list">${ov.bull_case.map(b => `<li style="color:var(--text-muted);">${b}</li>`).join('')}</ul>
        </div>
        <div class="card">
          <div class="card-title" style="color:var(--red);">Bear case</div>
          <ul class="assumptions-list">${ov.bear_case.map(b => `<li style="color:var(--text-muted);">${b}</li>`).join('')}</ul>
        </div>
      </div>

      <div class="grid-2" style="margin-bottom:20px;">
        <div class="card">
          <div class="card-title">Key risks</div>
          <ul class="assumptions-list">${ov.key_risks.map(r => `<li style="color:var(--text-muted);">${r}</li>`).join('')}</ul>
        </div>
        <div class="card">
          <div class="card-title">Key catalysts</div>
          <ul class="assumptions-list">${ov.key_catalysts.map(c => `<li style="color:var(--text-muted);">${c}</li>`).join('')}</ul>
        </div>
      </div>

      <div class="card" style="margin-bottom:20px;">
        <div class="section-head" style="margin-bottom:16px;"><div class="card-title" style="margin:0;">Scenario analysis</div><span class="tag tag-dim">Not a price forecast</span></div>
        <div class="grid-3">
          ${d.ai.scenarios.scenarios.map(s => `
            <div class="scenario ${s.rating}">
              <div class="sc-icon">${s.rating==='green'?'🟢':s.rating==='yellow'?'🟡':'🔴'}</div>
              <div class="sc-label">${s.label}</div>
              <div class="sc-driver">${s.driver}</div>
              <div class="sc-business">${s.business_impact}</div>
            </div>`).join('')}
        </div>
      </div>

      <div class="grid-2" style="margin-bottom:20px;">
        <div class="card">
          <div class="card-title">Political / geopolitical exposure <span class="pill ${pol.political_exposure==='HIGH'?'high':pol.political_exposure==='MEDIUM'?'medium':'low'}" style="margin-left:8px;"><span class="pill-dot"></span>${pol.political_exposure}</span></div>
          ${pol.analysis.map(a => `<p style="font-size:13px;color:var(--text-muted);margin-bottom:10px;">${a}</p>`).join('')}
          <div style="margin-top:12px;">
            <div class="card-title" style="font-size:14px;margin-bottom:12px;">Exposure map</div>
            ${Object.entries(pol.exposure_map).map(([k,v]) => `
              <div class="bar-row"><div class="bar-head"><span class="bar-label">${k}</span><span class="bar-val">${v}</span></div>
              <div class="bar-track"><div class="bar-fill" data-w="${v}" style="width:0%"></div></div></div>`).join('')}
          </div>
        </div>
        <div class="card">
          <div class="card-title">Event → Business → Market</div>
          ${d.ai.event_connections.map(ec => `
            <div style="margin-bottom:18px;">
              <div style="font-weight:700;font-size:14px;margin-bottom:8px;">${ec.title}</div>
              ${ec.chain.map((step, i) => `<div class="chain-item"><span class="step-label">Step ${i+1}:</span> ${step}</div>`).join('')}
            </div>`).join('')}
        </div>
      </div>

      <div class="grid-2" style="margin-bottom:20px;">
        <div class="card">
          <div class="card-title">Recent news & market intelligence</div>
          ${renderNews(d.news)}
        </div>
        <div class="card">
          <div class="card-title">News sentiment</div>
          <div style="display:flex;align-items:center;gap:16px;margin-bottom:10px;">
            <div class="score-ring" style="width:90px;height:90px;">
              <svg width="90" height="90"><circle cx="45" cy="45" r="36" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="8"/>
                <circle cx="45" cy="45" r="36" fill="none" stroke="${sc.components.news>=55?'#34d399':'#f87171'}" stroke-width="8" stroke-linecap="round" stroke-dasharray="${(sc.components.news/100)*226}" stroke-dashoffset="0" pathLength="226"/></svg>
              <div class="score-num"><div class="n" style="font-size:20px;">${sc.components.news}</div><div class="l">/100</div></div>
            </div>
            <div style="font-size:13px;color:var(--text-muted);flex:1;">${(sc.news_reason||[]).join(' ')}</div>
          </div>
          <div class="card-title" style="font-size:14px;margin-top:16px;">Composite AI score breakdown</div>
          ${Object.entries(sc.components).map(([k,v]) => `
            <div class="bar-row"><div class="bar-head"><span class="bar-label" style="text-transform:capitalize;">${k}</span><span class="bar-val">${v}</span></div>
            <div class="bar-track"><div class="bar-fill" data-w="${v}" style="width:0%;background:${v>=55?'#34d399':v>=45?'#fbbf24':'#f87171'};"></div></div></div>`).join('')}
        </div>
      </div>

      <div class="card panel-glow" id="chatPanel" style="margin-bottom:20px;">
        <div class="card-title">AI Research Chat <span class="sub">ask about ${q.ticker}</span></div>
        <div class="chat-panel">
          <div class="chat-log" id="chatLog">
            <div class="chat-msg bot">Hi! I can answer questions about ${q.name || q.ticker} using the live research data. Try asking about the score, valuation, key risks, political exposure or recent news.</div>
          </div>
          <div class="chat-input-row">
            <input id="chatInput" type="text" placeholder="Ask about this asset..." onkeydown="if(event.key==='Enter')sendChat()">
            <button class="btn btn-primary" onclick="sendChat()">Send</button>
          </div>
        </div>
      </div>
      <div class="disclaimer">AI research overviews, scores, scenarios and political assessments are generated from publicly available data and are educational only. They are not financial advice, guarantees or predictions. Past performance does not indicate future results.</div>
    </div>`;

    loadPriceChart('1Y');
    // animate bars
    requestAnimationFrame(() => setTimeout(() => {
        $$('.bar-fill').forEach(b => b.style.width = (b.dataset.w || 0) + '%');
    }, 100));
    // social proof / headers
}

function renderNews(news) {
    if (!news || news.length === 0) return '<div style="color:var(--text-dim);font-size:13px;">No recent news available from the data provider.</div>';
    return news.slice(0, 5).map(n => `
      <div class="news-card" onclick="if(n.link)window.open('${n.link||''}','_blank')">
        <div style="flex:1;">
          <div class="news-meta"><span class="news-source">${n.source || 'News'}</span><span class="news-date">${n.date || ''}</span></div>
          <div class="news-title">${n.title || ''}</div>
          ${n.summary ? `<div class="news-summary">${n.summary}</div>` : ''}
        </div>
      </div>`).join('');
}

async function loadPriceChart(range) {
    $$('#priceRangeTabs .range-btn').forEach(b => b.classList.toggle('active', b.dataset.range === range));
    try {
        const p = await api(`/api/asset/${researchTicker}/price?range=${range}`);
        if (p.error || !p.prices) return;
        if (charts.price) charts.price.destroy();
        const ctx = $('#priceChart').getContext('2d');
        const cH = ctx.canvas.clientHeight || 280;
        const grad = ctx.createLinearGradient(0, 0, 0, cH);
        grad.addColorStop(0, 'rgba(139,92,246,0.25)');
        grad.addColorStop(1, 'rgba(236,72,153,0)');
        const first = p.prices[0];
        const up = p.prices[p.prices.length-1] >= first;
        const color = up ? '#34d399' : '#f87171';
        charts.price = new Chart(ctx, {
            type: 'line',
            data: { labels: p.dates, datasets: [{ label: 'Price', data: p.prices, borderColor: color,
                backgroundColor: up ? 'rgba(52,211,153,0.15)' : 'rgba(248,113,113,0.15)', fill: true, tension: 0.3, pointRadius: 0, borderWidth: 2 }]},
            options: {
                responsive: true, maintainAspectRatio: false,
                interaction: { intersect: false, mode: 'index' },
                plugins: { legend: { display: false },
                    tooltip: { backgroundColor: '#111120', borderColor: 'rgba(139,92,246,0.25)', borderWidth: 1, titleColor: '#f0f0f5', bodyColor: '#a0a0b8', padding: 12,
                        callbacks: { label: c => '$' + c.parsed.y.toLocaleString(undefined, {minimumFractionDigits:2}) } } },
                scales: { x: { grid: { color: 'rgba(139,92,246,0.06)' }, ticks: { color: '#5f5f7a', maxTicksLimit: 8, font: { size: 11 } } },
                    y: { grid: { color: 'rgba(139,92,246,0.06)' }, ticks: { color: '#5f5f7a', font: { size: 11 }, callback: v => '$' + v.toLocaleString() } } }
            }
        });
    } catch {}
}

let chatSending = false;
async function sendChat() {
    const input = $('#chatInput'); const q = input.value.trim();
    if (!q || chatSending) return;
    const log = $('#chatLog');
    log.innerHTML += `<div class="chat-msg user">${escapeHtml(q)}</div>`;
    input.value = '';
    log.scrollTop = log.scrollHeight;
    chatSending = true;
    log.innerHTML += `<div class="chat-msg bot" id="chatThinking"><em style="opacity:.6;">Thinking...</em></div>`;
    log.scrollTop = log.scrollHeight;
    try {
        const r = await api(`/api/asset/${researchTicker}/chat`, { question: q });
        $('#chatThinking').outerHTML = `<div class="chat-msg bot">${escapeHtml(r.answer).replace(/\n/g,'<br>')}</div>`;
    } catch (e) {
        $('#chatThinking').outerHTML = `<div class="chat-msg bot">Sorry, I had trouble answering: ${escapeHtml(e.message)}</div>`;
    }
    chatSending = false;
    log.scrollTop = log.scrollHeight;
}
function escapeHtml(s) { return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

async function toggleWatch(ticker, isWatched) {
    try {
        if (isWatched) {
            await api(`/api/watchlist/${ticker}`, null, 'DELETE');
        } else {
            await api('/api/watchlist', { ticker });
        }
        renderResearch(ticker);
    } catch (e) { alert(e.message); }
}

/* ═══════════════════════════ WATCHLIST ═══════════════════════════ */
async function renderWatchlist() {
    const root = $('#appRoot');
    root.innerHTML = `<div class="view">
      <div class="section-head"><h2>Watchlist</h2><p>Your tracked assets</p></div>
      <div id="wlBody"><div style="text-align:center;color:var(--text-dim);padding:60px;">Loading watchlist...</div></div>
    </div>`;
    try {
        const items = await api('/api/watchlist');
        watchlistCache = items;
        const body = $('#wlBody');
        if (!items || items.length === 0) {
            body.innerHTML = `<div class="empty-state"><div class="icon">⭐</div>
              <h3 style="margin-bottom:8px;">Your watchlist is empty</h3>
              <p style="color:var(--text-muted);margin-bottom:20px;">Research any asset and add it to track AI scores and price moves.</p>
              <button class="btn btn-primary" onclick="go('home')">Explore assets</button></div>`;
            return;
        }
        body.innerHTML = `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px;">
          ${items.map(it => `
            <div class="wl-item" onclick="go('research','${it.ticker}')">
              <button class="wl-remove" onclick="event.stopPropagation();removeWatch('${it.ticker}')" title="Remove">×</button>
              <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
                <span style="font-weight:800;font-size:16px;">${it.ticker}</span>
                <span class="tag ${(it.ai_score||0)>=70?'tag-green':(it.ai_score||0)>=45?'tag-yellow':'tag-red'}">${it.ai_score != null ? it.ai_score+'/100' : '—'}</span>
              </div>
              <div style="font-size:12px;color:var(--text-dim);margin-bottom:12px;">${it.name || '—'}</div>
              <div style="display:flex;justify-content:space-between;">
                <span style="font-family:var(--mono);font-weight:600;">${it.price != null ? '$'+Number(it.price).toLocaleString(undefined,{minimumFractionDigits:2}) : '—'}</span>
                <span style="font-family:var(--mono);font-weight:600;" class="${(it.change_pct||0)>=0?'pos':'neg'}">${fmtPct(it.change_pct)}</span>
              </div>
              ${it.catalyst ? `<div style="margin-top:12px;padding-top:10px;border-top:1px solid var(--border);font-size:11px;color:var(--text-dim);">${it.catalyst}</div>` : ''}
            </div>`).join('')}
        </div>`;
    } catch (e) {
        $('#wlBody').innerHTML = `<div class="error-box">Could not load watchlist: ${e.message}</div>`;
    }
}
async function removeWatch(ticker) {
    await api(`/api/watchlist/${ticker}`, null, 'DELETE');
    renderWatchlist();
}

/* ═══════════════════════════ QUANT LAB ═══════════════════════════ */
let lastResults = null;
let currentQLTab = 'builder';

function renderQuantLab() {
    const root = $('#appRoot');
    root.innerHTML = `
    <div class="view">
      <div class="section-head">
        <div><h2>Quant Lab</h2><p>Describe a strategy in plain English → backtest with AI</p></div>
        <span class="tag tag-pink">Sub-feature of Quantly</span>
      </div>
      <div class="tabs" style="margin-bottom:22px;">
        <button class="tab active" data-qt="builder" onclick="switchQLTab(this,'builder')">Builder</button>
        <button class="tab" data-qt="compare" onclick="switchQLTab(this,'compare')">Compare</button>
        <button class="tab" data-qt="library" onclick="switchQLTab(this,'library')">Library</button>
      </div>
      <div id="ql-content">
        <div class="tab-content active" id="qt-builder">${qlBuilderHtml()}</div>
        <div class="tab-content" id="qt-compare">${qlCompareHtml()}</div>
        <div class="tab-content" id="qt-library"><div id="qlLibraryGrid"></div></div>
      </div>
      <div id="resultsArea" style="margin-top:28px;display:none;"></div>
      <div class="disclaimer" id="qlDisclaimer">Quant Lab results are simulated backtests of user-described strategies on historical data. They do not represent live trading, and past or simulated performance does not guarantee future results. Not investment advice.</div>
    </div>`;
    loadLibrary();
    initQLDefaults();
}
function switchQLTab(btn, name) {
    currentQLTab = name;
    $$('.tabs .tab').forEach(t => t.classList.toggle('active', t.dataset.qt === name));
    $$('#ql-content .tab-content').forEach(c => c.classList.remove('active'));
    $('#qt-' + name).classList.add('active');
    if (name === 'library') loadLibrary();
}

function qlBuilderHtml() {
    return `
    <div class="card panel-glow" style="margin-bottom:22px;">
      <div class="card-title">Strategy Builder</div>
      <div class="grid-2" style="align-items:start;gap:28px;">
        <div>
          <div class="field"><label>Ticker</label>
            <input class="input" id="ticker" placeholder="e.g. AAPL" oninput="debounce(validateTicker,600)()">
            <div id="tickerInfo" style="font-size:12px;margin-top:6px;min-height:18px;"></div>
          </div>
          <div class="field"><label>Describe your strategy in plain English</label>
            <textarea class="input" id="strategyInput" placeholder="e.g. Buy when the 50-day moving average crosses above the 200-day and RSI is above 55. Sell after 5 days." oninput="debounce(parseStrategyPreview,800)()"></textarea>
          </div>
          <div class="hints" style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;">
            ${['Buy when price crosses above the 20-day MA','Buy when RSI drops below 30','Buy on 50-day MA crossover','Buy when MACD is bullish and RSI above 50'].map(h => `<span class="chip" onclick="useHint(this)">${h}</span>`).join('')}
          </div>
          <div class="form-row">
            <div class="field"><label>Start date</label><input class="input" type="date" id="startDate"></div>
            <div class="field"><label>End date</label><input class="input" type="date" id="endDate"></div>
          </div>
          <div class="form-row">
            <div class="field"><label>Start capital ($)</label><input class="input" type="number" id="capital" value="10000"></div>
            <div class="field"><label>Transaction cost (%)</label><input class="input" type="number" id="txCost" value="0.1" step="0.1"></div>
          </div>
          <div class="form-row">
            <div class="field"><label>Stop loss (%)</label><input class="input" type="number" id="stopLoss" placeholder="Optional"></div>
            <div class="field"><label>Take profit (%)</label><input class="input" type="number" id="takeProfit" placeholder="Optional"></div>
          </div>
          <div class="field"><label>Trailing stop (%)</label><input class="input" type="number" id="trailingStop" placeholder="Optional"></div>
          <div id="builderError" style="display:none;" class="error-box"></div>
          <button class="btn btn-primary" style="width:100%;margin-top:6px;" onclick="runBacktest()">Run Backtest</button>
        </div>
        <div>
          <div id="explanationContainer" style="display:none;"></div>
          <div style="color:var(--text-dim);font-size:12px;padding:12px;" class="ai-banner" id="explanationEmpty">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
            Start typing a strategy to see the AI interpretation live.
          </div>
        </div>
      </div>
    </div>`;
}

function qlCompareHtml() {
    return `
    <div class="card panel-glow">
      <div class="card-title">Compare Two Strategies</div>
      <div class="form-row">
        <div class="field"><label>Ticker</label><input class="input" id="compareTicker" placeholder="e.g. AAPL"></div>
        <div class="field"><label>Date range</label>
          <div class="form-row"><input class="input" type="date" id="compareStart"><input class="input" type="date" id="compareEnd"></div>
        </div>
      </div>
      <div class="form-row">
        <div class="field"><label>Strategy A</label><textarea class="input" id="compareStratA" style="min-height:70px;" placeholder="e.g. Buy when RSI below 30, sell after 3 days"></textarea></div>
        <div class="field"><label>Strategy B</label><textarea class="input" id="compareStratB" style="min-height:70px;" placeholder="e.g. Buy when price above 50-day MA, sell when below"></textarea></div>
      </div>
      <div id="compareError" style="display:none;" class="error-box"></div>
      <button class="btn btn-primary" onclick="runCompare()">Compare Strategies</button>
      <div id="compareResults" style="margin-top:24px;"></div>
    </div>`;
}

function initQLDefaults() {
    const today = new Date().toISOString().split('T')[0];
    const yearAgo = new Date(Date.now() - 365*24*3600*1000).toISOString().split('T')[0];
    if ($('#endDate')) $('#endDate').value = today;
    if ($('#startDate')) $('#startDate').value = yearAgo;
    if ($('#compareEnd')) $('#compareEnd').value = today;
    if ($('#compareStart')) $('#compareStart').value = yearAgo;
}

function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

async function validateTicker() {
    const ticker = $('#ticker') && $('#ticker').value.trim().toUpperCase();
    const info = $('#tickerInfo'); if (!info) return;
    if (!ticker) { info.textContent = ''; return; }
    try {
        const r = await api('/api/validate-ticker', { ticker });
        info.innerHTML = r.valid
            ? `<span style="color:var(--green);">● ${r.name}</span> <span style="color:var(--text-dim);">${r.type||''}</span>`
            : `<span style="color:var(--red);">● Not found</span>`;
    } catch {}
}
async function parseStrategyPreview() {
    const text = $('#strategyInput') && $('#strategyInput').value.trim();
    const ticker = $('#ticker') && $('#ticker').value.trim().toUpperCase();
    if (!text || text.length < 10) return;
    try {
        const r = await api('/api/parse-strategy', { strategy: text, ticker });
        showExplanation(r.explanation);
    } catch {}
}
function useHint(btn) {
    $('#strategyInput').value = btn.textContent;
    $('#strategyInput').focus();
}

function showExplanation(exp) {
    if (!$('#explanationContainer')) return;
    const c = $('#explanationContainer');
    c.style.display = 'block';
    if ($('#explanationEmpty')) $('#explanationEmpty').style.display = 'none';
    const tf = {'1m':'1-Minute','5m':'5-Minute','15m':'15-Minute','30m':'30-Minute','1h':'Hourly','1d':'Daily','1wk':'Weekly','1mo':'Monthly'}[exp.timeframe] || exp.timeframe;
    let rulesHtml = '';
    exp.entry_rules.forEach(r => { rulesHtml += `<div class="explanation-item"><span class="explanation-key">Entry</span><span class="explanation-val">${r}</span></div>`; });
    exp.exit_rules.forEach(r => { rulesHtml += `<div class="explanation-item"><span class="explanation-key">Exit</span><span class="explanation-val">${r}</span></div>`; });
    c.innerHTML = `
      <div class="explanation-box">
        <div class="explanation-title" style="display:flex;align-items:center;gap:8px;font-weight:700;font-size:15px;margin-bottom:14px;">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg> Strategy Interpretation
        </div>
        <div class="explanation-grid">
          <div class="explanation-item"><span class="explanation-key">Asset</span><span class="explanation-val">${exp.asset}</span></div>
          <div class="explanation-item"><span class="explanation-key">Direction</span><span class="explanation-val">${exp.direction==='long'?'Long':'Short'}</span></div>
          <div class="explanation-item"><span class="explanation-key">Timeframe</span><span class="explanation-val">${tf}</span></div>
          <div class="explanation-item"><span class="explanation-key">Period</span><span class="explanation-val">${exp.period}</span></div>
          <div class="explanation-item"><span class="explanation-key">Indicators</span><span class="explanation-val">${exp.indicators_used.join(', ')||'Price-based'}</span></div>
          <div class="explanation-item"><span class="explanation-key">Position size</span><span class="explanation-val">${exp.risk_management.position_size}</span></div>
        </div>
        <div style="margin-top:14px;display:grid;grid-template-columns:1fr 1fr;gap:10px;">${rulesHtml}</div>
        <ul class="assumptions-list">${exp.assumptions.map(a => `<li>${a}</li>`).join('')}</ul>
      </div>`;
}

async function runBacktest() {
    const ticker = $('#ticker').value.trim().toUpperCase();
    const strategy = $('#strategyInput').value.trim();
    const start = $('#startDate').value, end = $('#endDate').value;
    const capital = parseFloat($('#capital').value);
    const txCost = parseFloat($('#txCost').value);
    const sl = parseFloat($('#stopLoss').value) || null;
    const tp = parseFloat($('#takeProfit').value) || null;
    const ts = parseFloat($('#trailingStop').value) || null;
    if (!ticker) return showErr('builderError','Please enter a ticker.');
    if (!strategy) return showErr('builderError','Please describe your strategy.');
    if (!start || !end) return showErr('builderError','Please select a date range.');
    if (start >= end) return showErr('builderError','Start must be before end.');
    hideErr('builderError');
    $('#resultsArea').style.display = 'none';
    showLoading('Running backtest...');
    try {
        const r = await api('/api/backtest', {
            ticker, start_date: start, end_date: end, initial_capital: capital,
            transaction_cost: txCost, slippage: 0.05,
            strategy: { raw_text: strategy, name: '', indicators: {},
                stop_loss_pct: sl, take_profit_pct: tp, trailing_stop_pct: ts, position_size: 1.0 }
        });
        if (r.error) throw new Error(r.error);
        lastResults = r;
        displayResults(r);
    } catch (e) { showErr('builderError', e.message); }
    finally { hideLoading(); }
}

function displayResults(r) {
    const area = $('#resultsArea'); area.style.display = 'block';
    const cls = v => v >= 0 ? 'pos' : 'neg';
    const fmt = v => (v >= 0 ? '+' : '') + v.toFixed(2);
    const fmtC = v => '$' + v.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2});
    let metricsHtml = `
      <div class="grid-4" style="margin-bottom:16px;">
        <div class="metric-card highlight"><div class="metric-label">Total Return</div><div class="metric-value ${cls(r.total_return)}">${fmt(r.total_return)}%</div></div>
        <div class="metric-card highlight"><div class="metric-label">Annualised</div><div class="metric-value ${cls(r.annualised_return)}">${fmt(r.annualised_return)}%</div></div>
        <div class="metric-card"><div class="metric-label">Sharpe</div><div class="metric-value ${cls(r.sharpe_ratio)}">${r.sharpe_ratio.toFixed(2)}</div></div>
        <div class="metric-card"><div class="metric-label">Max Drawdown</div><div class="metric-value neg">-${r.max_drawdown.toFixed(2)}%</div></div>
      </div>
      <div class="grid-4" style="margin-bottom:16px;">
        <div class="metric-card"><div class="metric-label">Win Rate</div><div class="metric-value">${r.win_rate.toFixed(1)}%</div></div>
        <div class="metric-card"><div class="metric-label">Trades</div><div class="metric-value">${r.completed_trades}</div></div>
        <div class="metric-card"><div class="metric-label">Profit Factor</div><div class="metric-value ${r.profit_factor>=1?'pos':'neg'}">${r.profit_factor.toFixed(2)}</div></div>
        <div class="metric-card"><div class="metric-label">Sortino</div><div class="metric-value ${cls(r.sortino_ratio)}">${r.sortino_ratio.toFixed(2)}</div></div>
      </div>
      <div class="tabs">
        <button class="tab active" onclick="switchResultTab(this,'equity')">Equity</button>
        <button class="tab" onclick="switchResultTab(this,'drawdown')">Drawdown</button>
        <button class="tab" onclick="switchResultTab(this,'monthly')">Monthly</button>
        <button class="tab" onclick="switchResultTab(this,'trades')">Trades</button>
        <button class="tab" onclick="switchResultTab(this,'analysis')">AI Analysis</button>
        <button class="tab" onclick="switchResultTab(this,'robustness')">Robustness</button>
      </div>
      <div class="tab-content active" id="rt-equity"><div class="chart-container" style="height:340px;"><canvas id="equityChart"></canvas></div></div>
      <div class="tab-content" id="rt-drawdown"><div class="chart-container" style="height:300px;"><canvas id="drawdownChart"></canvas></div></div>
      <div class="tab-content" id="rt-monthly"><div class="card" id="monthlyContent" style="margin-top:14px;"></div></div>
      <div class="tab-content" id="rt-trades"><div class="card" style="margin-top:14px;padding:0;overflow:hidden;"><div style="max-height:460px;overflow-y:auto;" id="tradesContent"></div></div></div>
      <div class="tab-content" id="rt-analysis"><div style="margin-top:14px;" id="aiAnalysisContent"></div></div>
      <div class="tab-content" id="rt-robustness"><div style="margin-top:14px;" id="robustnessContent"><button class="btn btn-primary" onclick="runRobustness()">Run Robustness Analysis</button></div></div>`;
    area.innerHTML = `<div class="card panel-glow">${metricsHtml}</div>`;
    renderEquityChart(r.chart_data);
    renderDrawdownChart(r.chart_data);
    renderMonthlyReturns(r.monthly_returns, r.yearly_returns);
    renderTrades(r.trades);
    renderAIAnalysis(r.ai_analysis);
}

function switchResultTab(btn, tab) {
    btn.parentElement.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    btn.parentElement.parentElement.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    $('#rt-' + tab).classList.add('active');
}

function chartBase() {
    return { responsive: true, maintainAspectRatio: false,
        interaction: { intersect: false, mode: 'index' },
        plugins: { legend: { display: false },
            tooltip: { backgroundColor: '#111120', borderColor: 'rgba(139,92,246,0.25)', borderWidth: 1, titleColor: '#f0f0f5', bodyColor: '#a0a0b8', padding: 12 } },
        scales: { x: { grid: { color: 'rgba(139,92,246,0.06)' }, ticks: { color: '#5f5f7a', maxTicksLimit: 8, font: { size: 11 } } },
            y: { grid: { color: 'rgba(139,92,246,0.06)' }, ticks: { color: '#5f5f7a', font: { size: 11 }, callback: v => v.toLocaleString() } } } };
}
function renderEquityChart(data) {
    if (charts.equity) charts.equity.destroy();
    const ctx = $('#equityChart').getContext('2d');
    const grad = ctx.createLinearGradient(0,0,0,340); grad.addColorStop(0,'rgba(139,92,246,0.25)'); grad.addColorStop(1,'rgba(139,92,246,0)');
    charts.equity = new Chart(ctx, { type: 'line',
        data: { labels: data.dates, datasets: [
            { label: 'Strategy', data: data.equity, borderColor: '#8b5cf6', backgroundColor: grad, fill: true, tension: 0.3, pointRadius: 0, borderWidth: 2 },
            { label: 'Buy & Hold', data: data.benchmark, borderColor: '#5f5f7a', borderDash: [4,4], fill: false, pointRadius: 0, borderWidth: 1.5 }] },
        options: { ...chartBase(), plugins: { ...chartBase().plugins, tooltip: { ...chartBase().plugins.tooltip, callbacks: { label: c => c.dataset.label + ': $' + c.parsed.y.toLocaleString(undefined,{minimumFractionDigits:2}) } } } } });
}
function renderDrawdownChart(data) {
    if (charts.drawdown) charts.drawdown.destroy();
    const ctx = $('#drawdownChart').getContext('2d');
    charts.drawdown = new Chart(ctx, { type: 'line',
        data: { labels: data.dates, datasets: [{ label: 'DD', data: data.drawdown, borderColor: '#f87171', backgroundColor: 'rgba(248,113,113,0.1)', fill: true, pointRadius: 0, borderWidth: 1.5 }] },
        options: { ...chartBase(), plugins: { ...chartBase().plugins, tooltip: { ...chartBase().plugins.tooltip, callbacks: { label: c => c.parsed.y.toFixed(2) + '%' } } } } });
}
function renderMonthlyReturns(monthly, yearly) {
    const el = $('#monthlyContent'); if (!el) return;
    let html = '<div class="card-title">Monthly Returns</div>';
    if (yearly && yearly.length) {
        html += '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px;">';
        yearly.forEach(y => html += `<span class="tag ${y['return']>=0?'tag-green':'tag-red'}">${y.year}: ${y['return']>=0?'+':''}${y['return'].toFixed(1)}%</span>`);
        html += '</div>';
    }
    if (monthly && monthly.length) {
        const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
        html += '<div style="display:grid;grid-template-columns:repeat(12,1fr);gap:3px;">';
        months.forEach(m => html += `<div style="text-align:center;font-size:10px;color:var(--text-dim);padding:4px 0;">${m}</div>`);
        const byYear = {};
        monthly.forEach(m => { const [y,mo] = m.month.split('-'); if(!byYear[y]) byYear[y]={}; byYear[y][parseInt(mo)-1] = m['return']; });
        Object.keys(byYear).sort().forEach(y => {
            for (let i=0;i<12;i++){ const v=byYear[y][i];
                if (v!==undefined){ let cls='heat-neutral';
                    if(v>5)cls='heat-pos-3';else if(v>2)cls='heat-pos-2';else if(v>0)cls='heat-pos-1';
                    else if(v<-5)cls='heat-neg-3';else if(v<-2)cls='heat-neg-2';else if(v<0)cls='heat-neg-1';
                    html += `<div class="monthly-cell ${cls}">${v>=0?'+':''}${v.toFixed(1)}</div>`; }
                else html += '<div class="monthly-cell heat-neutral">-</div>';
            }
        });
        html += '</div>';
    }
    el.innerHTML = html;
}
function renderTrades(trades) {
    const el = $('#tradesContent'); if (!el) return;
    const sells = trades.filter(t => t.action === 'SELL' || t.action === 'COVER');
    let html = '<table><thead><tr><th>Date</th><th>Action</th><th>Price</th><th>Shares</th><th>P&L</th><th>%</th><th>Exit</th></tr></thead><tbody>';
    sells.forEach(t => {
        const cls = (t.pnl||0)>=0?'pos':'neg';
        html += `<tr><td class="mono">${t.date}</td><td><span class="tag ${t.action==='SELL'?'tag-pink':'tag-purple'}">${t.action}</span></td>
          <td class="mono">$${t.price.toFixed(2)}</td><td>${t.shares}</td>
          <td class="${cls}">${(t.pnl>=0?'+':'')+'$'+t.pnl.toFixed(2)}</td><td class="${cls}">${(t.pnl_pct>=0?'+':'')+t.pnl_pct.toFixed(2)}%</td>
          <td style="font-size:11px;color:var(--text-dim);">${t.exit_reason||'signal'}</td></tr>`;
    });
    el.innerHTML = html + '</tbody></table>';
}
function renderAIAnalysis(a) {
    if (!a) return; const el = $('#aiAnalysisContent'); if (!el) return;
    let html = `<div class="ai-analysis" style="margin-bottom:16px;">
      <div class="ai-banner"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" stroke-width="2"><path d="M12 2a10 10 0 0 1 10 10c0 5.52-4.48 10-10 10S2 17.52 2 12 6.48 2 12 2z"/><path d="M12 8v4"/><path d="M12 16h.01"/></svg> AI Analysis</div>
      <div class="analysis-signal" style="border-color:rgba(139,92,246,0.3);background:var(--accent-soft);font-weight:600;color:var(--accent);">${a.summary}</div>
      ${a.signals.map(s => `<div class="analysis-signal">${s}</div>`).join('')}</div>`;
    html += `<div class="grid-2">
      <div class="card"><div class="card-title" style="color:var(--green);">Strengths</div>${a.strengths.map(s=>`<div class="analysis-signal">${s}</div>`).join('')}</div>
      <div class="card"><div class="card-title" style="color:var(--red);">Weaknesses</div>${a.weaknesses.map(w=>`<div class="analysis-signal">${w}</div>`).join('')}</div></div>`;
    html += `<div class="card" style="margin-top:16px;">
      <div class="card-title">Overfitting Risk</div>
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;">
        <span class="tag ${a.overfit_risk.level==='High'?'tag-red':a.overfit_risk.level==='Moderate'?'tag-yellow':'tag-green'}">${a.overfit_risk.level} (${a.overfit_risk.score}/100)</span>
      </div>
      <div class="bar-track"><div class="bar-fill" style="width:${a.overfit_risk.score}%;background:${a.overfit_risk.score>60?'var(--red)':a.overfit_risk.score>30?'var(--yellow)':'var(--green)'};"></div></div>
      <ul class="assumptions-list">${a.overfit_risk.factors.map(f=>`<li>${f}</li>`).join('')}</ul>
      <div style="margin-top:10px;font-size:12px;color:var(--text-dim);font-style:italic;">${a.overfit_risk.advice}</div></div>`;
    if (a.recommendations && a.recommendations.length) html += `<div class="card" style="margin-top:16px;"><div class="card-title">Recommendations</div><ul class="assumptions-list">${a.recommendations.map(r=>`<li>${r}</li>`).join('')}</ul></div>`;
    el.innerHTML = html;
}
async function runRobustness() {
    if (!lastResults) return;
    const el = $('#robustnessContent'); el.innerHTML = '<div style="text-align:center;padding:20px;"><div class="spinner" style="margin:0 auto 12px;"></div><p style="color:var(--text-muted);font-size:13px;">Running Monte Carlo simulation...</p></div>';
    try {
        const mc = await api('/api/robustness/monte-carlo', { results: lastResults, simulations: 1000 });
        if (mc.error) throw new Error(mc.error);
        el.innerHTML = `<div class="card">
          <div class="card-title">Monte Carlo (1,000 simulations)</div>
          <div class="grid-4" style="margin-bottom:16px;">
            <div class="metric-card"><div class="metric-label">P(Profit)</div><div class="metric-value ${mc.probability_profit>50?'pos':'neg'}">${mc.probability_profit}%</div></div>
            <div class="metric-card"><div class="metric-label">P(2x Return)</div><div class="metric-value">${mc.probability_double}%</div></div>
            <div class="metric-card"><div class="metric-label">P(Large Loss)</div><div class="metric-value neg">${mc.probability_ruin}%</div></div>
            <div class="metric-card"><div class="metric-label">Median Final</div><div class="metric-value">$${mc.median_final_value.toLocaleString()}</div></div>
          </div>
          <div class="card-title" style="font-size:13px;">Return distribution</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;">${Object.entries(mc.return_distribution).map(([k,v])=>`<span class="tag tag-purple">${k}: $${v.toLocaleString()}</span>`).join('')}</div>
          <div class="card-title" style="font-size:13px;">Max drawdown distribution</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">${Object.entries(mc.drawdown_distribution).map(([k,v])=>`<span class="tag tag-red">${k}: ${v}%</span>`).join('')}</div>
        </div>`;
    } catch (e) { el.innerHTML = `<div class="error-box">${e.message}</div>`; }
}

async function runCompare() {
    const ticker = $('#compareTicker').value.trim().toUpperCase();
    const sa = $('#compareStratA').value.trim(), sb = $('#compareStratB').value.trim();
    const start = $('#compareStart').value, end = $('#compareEnd').value;
    if (!ticker || !sa || !sb) return showErr('compareError','Fill in all fields.');
    if (!start || !end) return showErr('compareError','Select a date range.');
    hideErr('compareError');
    showLoading('Comparing strategies...');
    try {
        const r = await api('/api/compare', { ticker, strategy_a: sa, strategy_b: sb, start_date: start, end_date: end, initial_capital: 10000 });
        if (r.error) throw new Error(r.error);
        displayComparison(r);
    } catch (e) { showErr('compareError', e.message); } finally { hideLoading(); }
}
function displayComparison(r) {
    const a = r.strategy_a, b = r.strategy_b, c = r.comparison.comparison;
    const win = (va,vb)=>va>vb?'compare-winner':'';
    const metrics = [
        {label:'Total Return', key:'total_return', fmt: v=> (v>=0?'+':'')+v.toFixed(2)+'%'},
        {label:'Annualised', key:'annualised_return', fmt: v=> (v>=0?'+':'')+v.toFixed(2)+'%'},
        {label:'Sharpe', key:'sharpe_ratio', fmt: v=>v.toFixed(2)},
        {label:'Sortino', key:'sortino_ratio', fmt: v=>v.toFixed(2)},
        {label:'Max Drawdown', key:'max_drawdown', fmt: v=>v.toFixed(2)+'%'},
        {label:'Win Rate', key:'win_rate', fmt: v=>v.toFixed(1)+'%'},
        {label:'Profit Factor', key:'profit_factor', fmt: v=>v.toFixed(2)},
        {label:'Trades', key:'completed_trades', fmt: v=>v.toString()},
    ];
    let rows = '';
    metrics.forEach(m => {
        const va = c[m.key].strategy_a, vb = c[m.key].strategy_b;
        rows += `<div class="compare-row"><div class="compare-a compare-val ${win(va,vb)}">${m.fmt(va)}</div><div class="compare-label">${m.label}</div><div class="compare-b compare-val ${win(vb,va)}">${m.fmt(vb)}</div></div>`;
    });
    $('#compareResults').innerHTML = `<div class="card">
      <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <div class="card-title">${a.strategy_name} vs ${b.strategy_name}</div>
        <span class="tag ${r.comparison.overall_winner==='Tie'?'tag-yellow':'tag-purple'}">Winner: ${r.comparison.overall_winner}</span>
      </div>
      <div style="display:grid;grid-template-columns:1fr auto 1fr;gap:16px;margin-bottom:12px;">
        <div style="text-align:center;font-size:12px;color:var(--text-muted);font-weight:600;">${a.strategy_name}</div><div></div>
        <div style="text-align:center;font-size:12px;color:var(--text-muted);font-weight:600;">${b.strategy_name}</div></div>
      ${rows}
      <div class="ai-analysis" style="margin-top:16px;"><div class="card-title" style="font-size:14px;">AI Comparison</div><div class="analysis-signal">${r.comparison.summary}</div></div>
    </div>`;
}

async function loadLibrary() {
    const grid = $('#qlLibraryGrid'); if (!grid) return;
    try {
        const strats = await api('/api/library');
        if (!strats || strats.length === 0) { grid.innerHTML = '<div class="empty-state"><div class="icon">📚</div><p>No strategies saved yet. Run a backtest to save one.</p></div>'; return; }
        grid.innerHTML = `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px;">
          ${strats.map(s => { const r = s.last_results; return `
            <div class="strategy-card">
              <div class="strategy-card-header"><div class="strategy-card-name">${s.name}</div>
                <div><button class="btn btn-ghost btn-sm" onclick="event.stopPropagation();rerunStrategy('${s.id}')">Run</button>
                <button class="btn btn-ghost btn-sm" onclick="event.stopPropagation();deleteStrategy('${s.id}')">Del</button></div></div>
              <div class="strategy-card-meta">${s.ticker} · ${s.timeframe} · ${s.direction}</div>
              <div style="font-size:12px;color:var(--text-dim);margin:8px 0;">${(s.raw_text||'').substring(0,90)}</div>
              ${r ? `<div class="strategy-card-stats">
                <span class="strategy-stat"><span class="strategy-stat-label">Return:</span><span class="strategy-stat-value ${r.total_return>=0?'pos':'neg'}">${r.total_return>=0?'+':''}${r.total_return.toFixed(1)}%</span></span>
                <span class="strategy-stat"><span class="strategy-stat-label">Sharpe:</span><span class="strategy-stat-value">${r.sharpe_ratio?.toFixed(2)}</span></span>
                <span class="strategy-stat"><span class="strategy-stat-label">Max DD:</span><span class="strategy-stat-value neg">-${r.max_drawdown?.toFixed(1)}%</span></span></div>` : '<div style="font-size:12px;color:var(--text-dim);">Not yet tested</div>'}
            </div>`; }).join('')}</div>`;
    } catch {}
}
async function rerunStrategy(id) {
    try { const s = await api(`/api/library/${id}`);
        if (s && s.raw_text) { switchQLTab($$('.tab[data-qt="builder"]')[0],'builder');
            $('#ticker').value = s.ticker||''; $('#strategyInput').value = s.raw_text;
            if (s.suggested_start) $('#startDate').value = s.suggested_start;
            if (s.stop_loss_pct) $('#stopLoss').value = s.stop_loss_pct;
            if (s.take_profit_pct) $('#takeProfit').value = s.take_profit_pct;
            if (s.trailing_stop_pct) $('#trailingStop').value = s.trailing_stop_pct;
            parseStrategyPreview(); }
    } catch {}
}
async function deleteStrategy(id) { if (!confirm('Delete this strategy?')) return; try { await api(`/api/library/${id}`,null,'DELETE'); loadLibrary(); } catch {} }

function showErr(id, msg) { const el = $('#' + id); if (el) { el.textContent = msg; el.style.display = 'flex'; } }
function hideErr(id) { const el = $('#' + id); if (el) el.style.display = 'none'; }
function renderEmpty(msg) { $('#appRoot').innerHTML = `<div class="view"><div class="empty-state"><div class="icon">🔍</div><p>${msg}<br><br><button class="btn btn-primary" onclick="go('home')">Go home</button></p></div></div>`; }
function renderErrorState(title, sub, onRetry) {
    return `<div class="view"><div class="empty-state"><div class="icon">⚠️</div>
      <h3 style="margin-bottom:10px;">${title}</h3><p style="color:var(--text-muted);margin-bottom:20px;">${sub}</p>
      <button class="btn btn-primary" onclick="onRetry()">Back to home</button></div></div>`;
}

/* ─── browse assets ─── */
async function renderBrowse() {
    const root = $('#appRoot');
    root.innerHTML = `
      <div class="view">
        <div class="page-head">
          <h1>Browse Assets</h1>
          <p>Search or browse stocks, crypto, ETFs, indices and forex. Click any asset to research it.</p>
        </div>
        <div class="browse-search">
          <input id="browseSearch" type="text" placeholder="Search all assets, e.g. bitcoin, s&p, gold, apple..." oninput="browseFilter()">
        </div>
        <div id="browseGrid"><div style="text-align:center;color:var(--text-dim);padding:40px;">Loading...</div></div>
      </div>`;
    try {
        const data = await api('/api/browse');
        renderBrowseGrid(data.categories || {});
    } catch {
        $('#browseGrid').innerHTML = '<div style="text-align:center;color:var(--text-dim);padding:40px;">Could not load assets.</div>';
    }
}

let browseData = null;
function renderBrowseGrid(categories) {
    browseData = categories || {};
    let html = '';
    for (const [cat, items] of Object.entries(browseData)) {
        html += `<div class="browse-cat"><h3 class="browse-cat-title">${cat}</h3><div class="browse-chips">`;
        for (const [sym, name] of items) {
            html += `<span class="browse-chip" onclick="go('research','${sym}')"><span class="bc-ticker">${sym}</span><span class="bc-name">${name}</span></span>`;
        }
        html += `</div></div>`;
    }
    $('#browseGrid').innerHTML = html;
}

function browseFilter() {
    if (!browseData) return;
    const q = ($('#browseSearch').value || '').toLowerCase().trim();
    let html = '';
    for (const [cat, items] of Object.entries(browseData)) {
        const matches = items.filter(([sym, name]) => !q || sym.toLowerCase().includes(q) || name.toLowerCase().includes(q));
        if (!matches.length) continue;
        html += `<div class="browse-cat"><h3 class="browse-cat-title">${cat}</h3><div class="browse-chips">`;
        for (const [sym, name] of matches) html += `<span class="browse-chip" onclick="go('research','${sym}')"><span class="bc-ticker">${sym}</span><span class="bc-name">${name}</span></span>`;
        html += `</div></div>`;
    }
    $('#browseGrid').innerHTML = html || '<div style="text-align:center;color:var(--text-dim);padding:40px;">No matches found.</div>';
}

/* ─── global search ─── */
let searchDebounce;
function globalSearchKey(e) {
    clearTimeout(searchDebounce);
    const input = $('#globalSearchInput');
    const dd = $('#globalSearchDropdown');
    if (e.key === 'Enter') {
        const q = input.value.trim().toUpperCase();
        if (q) { dd.classList.remove('show'); go('research', q); input.value=''; }
        return;
    }
    const q = input.value.trim();
    if (!q) { dd.classList.remove('show'); return; }
    searchDebounce = setTimeout(async () => {
        try {
            const r = await api(`/api/search?q=${encodeURIComponent(q)}`);
            if (r.length) {
                dd.innerHTML = r.map(it => `<div class="search-item" onclick="go('research','${it.ticker}');document.getElementById('globalSearchInput').value='';document.getElementById('globalSearchDropdown').classList.remove('show');">
                    <span><span class="si-ticker">${it.ticker}</span> <span class="si-name">${it.name||''}</span></span>
                    <span class="si-price ${(it.change_pct||0)>=0?'pos':'neg'}">${it.price!=null?'$'+Number(it.price).toLocaleString(undefined,{maximumFractionDigits:2}):''}</span></div>`).join('');
            } else dd.innerHTML = '<div class="search-empty">No valid ticker found</div>';
            dd.classList.add('show');
        } catch { dd.classList.remove('show'); }
    }, 500);
}

document.addEventListener('click', e => {
    const dd = $('#globalSearchDropdown'); if (!dd) return;
    if (!e.target.closest('.global-search')) dd.classList.remove('show');
});

document.addEventListener('click', e => {
    const hd = $('#homeSearchDropdown'); if (!hd) return;
    if (!e.target.closest('.hero-search')) hd.classList.remove('show');
});

/* ─── init ─── */
document.addEventListener('DOMContentLoaded', () => {
    const route = parseHash();
    render(route.view, route.param);
    window.addEventListener('hashchange', () => {
        const r = parseHash();
        render(r.view, r.param);
    });
});
