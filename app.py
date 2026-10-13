import os
import io
import csv
import gzip
import datetime
from flask import Flask, render_template, jsonify, request, send_file, Response

from config import SERVER_PORT, SERVER_HOST, CACHE_FILE
from upstox_client import UpstoxClient
from corporate_actions import CorporateActionsManager
from isin_resolver import isin_resolver

app = Flask(__name__)

# Initialize client and manager
client = UpstoxClient()
manager = CorporateActionsManager(client)

@app.after_request
def optimize_response(response):
    """Apply caching headers, gzip compression, and security headers for production."""
    # 1. Security Headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    # Content Security Policy (CSP)
    csp = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'https://fonts.googleapis.com' 'unsafe-inline'; "
        "font-src 'self' 'https://fonts.gstatic.com'; "
        "img-src 'self' data:; "
        "connect-src 'self';"
    )
    response.headers["Content-Security-Policy"] = csp

    # 2. Caching headers
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif request.path == "/favicon.ico":
        response.headers["Cache-Control"] = "public, max-age=86400"
    elif not response.headers.get("Cache-Control"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"

    # 2. Gzip Compression for text/json/css/js
    accept_encoding = request.headers.get("Accept-Encoding", "")
    if "gzip" not in accept_encoding.lower():
        return response

    if response.direct_passthrough:
        return response

    mimetype = response.mimetype or ""
    if not (mimetype.startswith("text/") or mimetype in ["application/json", "application/javascript", "image/svg+xml"]):
        return response

    data = response.get_data()
    if len(data) < 500:
        return response

    gzip_buffer = io.BytesIO()
    with gzip.GzipFile(mode="wb", fileobj=gzip_buffer) as gz:
        gz.write(data)

    compressed_data = gzip_buffer.getvalue()
    if len(compressed_data) < len(data):
        response.set_data(compressed_data)
        response.headers["Content-Encoding"] = "gzip"
        response.headers["Content-Length"] = len(compressed_data)
        response.headers["Vary"] = "Accept-Encoding"

    return response

@app.route("/")
def index():
    """Main dashboard page."""
    return render_template("index.html")

@app.route("/favicon.ico")
def favicon():
    """Serve favicon."""
    return send_file("static/favicon.ico", mimetype="image/vnd.microsoft.icon")

@app.route("/api/dividends")
def get_dividends():
    """Fetch dividends with optional filtering by timeframe, yield, and search."""
    try:
        timeframe = request.args.get("timeframe", "all")
        if timeframe not in ["all", "30", "90", "180", "365"]:
            timeframe = "all"

        try:
            min_yield = float(request.args.get("min_yield", 0.0))
            if min_yield < 0 or min_yield > 100:
                min_yield = 0.0
        except (ValueError, TypeError):
            min_yield = 0.0

        search_query = request.args.get("search", "").strip().lower()
        if len(search_query) > 100:
            search_query = search_query[:100]
    except Exception:
        return jsonify({"status": "error", "message": "Invalid query parameters"}), 400

    # Get cached or fresh dividends
    all_divs = manager.get_all_dividends()
    stats = manager.get_statistics(all_divs)
    token_status = client.validate_token()

    # Filter by timeframe
    filtered = manager.filter_by_timeframe(all_divs, timeframe)

    # Filter by minimum yield
    if min_yield > 0:
        filtered = [d for d in filtered if d.get("dividend_yield", 0) >= min_yield]

    # Filter by search query (symbol or company name)
    if search_query:
        filtered = [
            d for d in filtered
            if search_query in d.get("symbol", "").lower()
            or search_query in d.get("company_name", "").lower()
        ]

    # Get last updated time from cache if available
    last_updated = "Just now"
    if CACHE_FILE.exists():
        try:
            mtime = os.path.getmtime(CACHE_FILE)
            last_updated = datetime.datetime.fromtimestamp(mtime).strftime("%d %b %Y, %I:%M %p")
        except Exception:
            pass

    return jsonify({
        "status": "success",
        "timeframe": timeframe,
        "count": len(filtered),
        "dividends": filtered,
        "stats": stats,
        "token_status": token_status,
        "last_updated": last_updated
    })

@app.route("/api/refresh", methods=["POST"])
def refresh_data():
    """Force refresh live data from exchange and Upstox."""
    client.reload_token()
    fresh_divs = manager.get_all_dividends(force_refresh=True)
    stats = manager.get_statistics(fresh_divs)
    token_status = client.validate_token()

    return jsonify({
        "status": "success",
        "message": f"Successfully refreshed {len(fresh_divs)} corporate action records.",
        "stats": stats,
        "token_status": token_status,
        "last_updated": datetime.datetime.now().strftime("%d %b %Y, %I:%M %p")
    })

@app.route("/api/stock/<identifier>/history")
def stock_history(identifier):
    """Fetch company's complete multi-year dividend track record."""
    # Validate identifier to prevent path traversal or oversized requests
    identifier = identifier.strip()
    if len(identifier) > 50 or any(char in identifier for char in ['/', '\\', '..']):
        return jsonify({"status": "error", "message": "Invalid identifier"}), 400

    history = manager.get_complete_dividend_history(identifier)
    isin = isin_resolver.get_isin(identifier) if not identifier.startswith("INE") else identifier
    return jsonify({
        "status": "success",
        "symbol": identifier,
        "isin": isin or identifier,
        "count": len(history),
        "history": history
    })

@app.route("/api/export")
def export_csv():
    """Export currently filtered dividends to CSV."""
    timeframe = request.args.get("timeframe", "all")
    all_divs = manager.get_all_dividends()
    filtered = manager.filter_by_timeframe(all_divs, timeframe)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Symbol", "Company Name", "ISIN", "Dividend Type",
        "Announced Dividend (INR)", "Annual Div / Share (INR)", "LTP (INR)", "Dividend Yield (%)",
        "Ex-Date", "Record Date", "Days Remaining"
    ])

    for d in filtered:
        writer.writerow([
            d.get("symbol", ""),
            d.get("company_name", ""),
            d.get("isin", ""),
            d.get("dividend_type", ""),
            d.get("dividend_amount", 0.0),
            d.get("annual_dividend", 0.0),
            d.get("ltp", 0.0),
            d.get("dividend_yield", 0.0),
            d.get("ex_date", ""),
            d.get("record_date", ""),
            d.get("days_remaining", "")
        ])

    output.seek(0)
    filename = f"dividends_{timeframe}days_{datetime.date.today().strftime('%Y%m%d')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

if __name__ == "__main__":
    # Production safety: debug must be False.
    # Railway provides the PORT environment variable automatically.
    print(f"🚀 Dividend Scanner Dashboard running at http://{SERVER_HOST}:{SERVER_PORT}")
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False)
