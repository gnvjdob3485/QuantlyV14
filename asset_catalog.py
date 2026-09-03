"""
Curated asset browser catalog for Quantly.

Provides a searchable, browsable list of representative assets across stocks,
crypto, ETFs, indices and forex. Tickers here all work with the FMP quote
endpoint so browsing them does not burn extra API budget — data is only fetched
when an asset is actually researched.

Purely seeds the UI with real, valid tickers; it does not fetch anything itself.
"""

CATEGORIES = {
    "Stocks": [
        ("AAPL", "Apple Inc."), ("MSFT", "Microsoft"), ("NVDA", "NVIDIA"),
        ("GOOGL", "Alphabet (Google)"), ("AMZN", "Amazon"), ("META", "Meta Platforms"),
        ("TSLA", "Tesla"), ("AMD", "AMD"), ("INTC", "Intel"), ("AVGO", "Broadcom"),
        ("QCOM", "Qualcomm"), ("NFLX", "Netflix"), ("DIS", "Walt Disney"),
        ("CRM", "Salesforce"), ("ORCL", "Oracle"), ("ADBE", "Adobe"),
        ("UBER", "Uber"), ("SHOP", "Shopify"), ("PYPL", "PayPal"),
        ("JPM", "JPMorgan"), ("BAC", "Bank of America"), ("WFC", "Wells Fargo"),
        ("GS", "Goldman Sachs"), ("MS", "Morgan Stanley"), ("V", "Visa"),
        ("MA", "Mastercard"), ("AXP", "American Express"), ("KO", "Coca-Cola"),
        ("PEP", "PepsiCo"), ("PG", "Procter & Gamble"), ("WMT", "Walmart"),
        ("COST", "Costco"), ("MCD", "McDonald's"), ("SBUX", "Starbucks"),
        ("NKE", "Nike"), ("HD", "Home Depot"), ("LOW", "Lowe's"), ("TGT", "Target"),
        ("AMGN", "Amgen"), ("GILD", "Gilead"), ("PFE", "Pfizer"), ("MRK", "Merck"),
        ("JNJ", "Johnson & Johnson"), ("UNH", "UnitedHealth"), ("LLY", "Eli Lilly"),
        ("ABBV", "AbbVie"), ("TMO", "Thermo Fisher"), ("XOM", "Exxon Mobil"),
        ("CVX", "Chevron"), ("COP", "ConocoPhillips"), ("SLB", "Schlumberger"),
        ("BA", "Boeing"), ("CAT", "Caterpillar"), ("GE", "GE Aerospace"),
        ("HON", "Honeywell"), ("UPS", "UPS"), ("FDX", "FedEx"),
        ("IBM", "IBM"), ("CSCO", "Cisco"), ("T", "AT&T"), ("VZ", "Verizon"),
        ("TMUS", "T-Mobile"), ("KO", "Coca-Cola"), ("PBR", "Petrobras"),
        ("TSM", "TSMC"), ("SAP", "SAP"), ("ASML", "ASML"), ("SONY", "Sony"),
        ("SHOP", "Shopify"), ("SPOT", "Spotify"),
    ],
    "Crypto": [
        ("BTCUSD", "Bitcoin"), ("ETHUSD", "Ethereum"), ("SOLUSD", "Solana"),
        ("BNBUSD", "BNB"), ("XRPUSD", "XRP"), ("ADAUSD", "Cardano"),
        ("DOGEUSD", "Dogecoin"), ("AVAXUSD", "Avalanche"), ("DOTUSD", "Polkadot"),
        ("LINKUSD", "Chainlink"), ("MATICUSD", "Polygon"), ("LTCUSD", "Litecoin"),
        ("UNIUSD", "Uniswap"), ("ATOMUSD", "Cosmos"), ("XLMUSD", "Stellar"),
        ("SHIBUSD", "Shiba Inu"), ("USDTUSD", "Tether"), ("USDCUSD", "USD Coin"),
    ],
    "ETFs": [
        ("SPY", "S&P 500 ETF"), ("QQQ", "Nasdaq 100 ETF"), ("DIA", "Dow Jones ETF"),
        ("VTI", "Total US Market"), ("VOO", "S&P 500 Vanguard"),
        ("IWM", "Russell 2000 ETF"), ("XLK", "Tech Sector ETF"),
        ("XLF", "Financial Sector ETF"), ("XLE", "Energy Sector ETF"),
        ("XLV", "Healthcare ETF"), ("GLD", "Gold ETF"), ("SLV", "Silver ETF"),
        ("USO", "Oil ETF"), ("TLT", "20+ Yr Treasury"), ("HYG", "High Yield Bonds"),
        ("EEM", "Emerging Markets"), ("VEA", "Developed ex-US"),
        ("ARKK", "ARK Innovation"), ("BND", "Total Bond"), ("TQQQ", "3x Nasdaq"),
        ("SQQQ", "Inverse 3x Nasdaq"), ("VXUS", "Total Intl Stock"),
        ("AIA", "Asia Dividend"), ("IBB", "Biotech ETF"), ("GAMR", "Video Game ETF"),
    ],
    "Indices": [
        ("^GSPC", "S&P 500"), ("^IXIC", "NASDAQ Composite"), ("^DJI", "Dow Jones"),
        ("^VIX", "Volatility Index"), ("^GDAXI", "DAX (Germany)"),
        ("^FTSE", "FTSE 100 (UK)"), ("^N225", "Nikkei 225 (Japan)"),
        ("^HSI", "Hang Seng (HK)"), ("^STOXX50E", "EURO STOXX 50"),
        ("^BVSP", "Bovespa (Brazil)"), ("^KS11", "KOSPI (Korea)"),
        ("^NSEI", "Nifty 50 (India)"), ("^GSPTSE", "TSX (Canada)"),
        ("^AXJO", "ASX 200 (Australia)"), ("XPTUSD", "Platinum"),
    ],
    "Forex": [
        ("EURUSD", "EUR/USD"), ("GBPUSD", "GBP/USD"), ("USDJPY", "USD/JPY"),
        ("USDCHF", "USD/CHF"), ("AUDUSD", "AUD/USD"), ("USDCAD", "USD/CAD"),
        ("NZDUSD", "NZD/USD"), ("EURGBP", "EUR/GBP"), ("EURJPY", "EUR/JPY"),
        ("GBPJPY", "GBP/JPY"),
    ],
}


# Build a flat search index over the catalog
def search(query: str, limit: int = 15) -> list:
    """Return matching {ticker, name, category} entries from the catalog."""
    q = (query or '').lower().strip()
    if not q:
        return []
    out = []
    for category, items in CATEGORIES.items():
        for ticker, name in items:
            if q in ticker.lower() or q in name.lower():
                out.append({'ticker': ticker, 'name': name, 'category': category})
    return out[:limit]


def all_assets() -> dict:
    return CATEGORIES
