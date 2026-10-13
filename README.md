# 📈 DiviTrack — Indian Stock Market Dividend Scanner

An analysis tool built for the Indian Stock Market (**NSE & BSE**) integrated with **Upstox API**. It tracks and filters shares announcing dividends across **5-day, 10-day, 20-day, 30-day, 45-day, 60-day, 75-day, and 90-day timeframes**, providing live market prices, dividend amounts, dividend yields, countdowns, and historical dividend track records.

---

## 🚀 Key Features

* **Timeframe Filters**: Scan shares with Ex-Dividend dates within **5, 10, 20, 30, 45, 60, 75, or 90 days**.
* **Upstox API Integration**:
  * Live Last Traded Price (LTP), day changes, and volume for listed stocks.
  * Historical corporate actions and dividend payout track records.
  * Automatic fallback to official exchange data when offline.
* **Dual Interfaces**:
  1. **Modern Interactive Web Dashboard**: Real-time filtering across all timeframes, live KPI counters, instant search, sorting, modal dividend history inspection, and CSV export.
  2. **Rich CLI Tool**: Formatted console tables with urgency countdown badges and export capabilities.
* **Modular Architecture**: Built with clear module separation so future analysis features can be integrated seamlessly.

---

## 🛠️ Project Structure

```
d:\share_analysis/
├── .env                     # Contains Upstox API Token (TOKEN=...)
├── config.py                # Environment configuration & cache settings
├── upstox_client.py         # Upstox API client (quotes, LTP, fundamentals)
├── corporate_actions.py     # Aggregator & timeframe categorizer (NSE + Upstox)
├── dividend_scanner.py      # Command-line interface (CLI) with rich output
├── app.py                   # Web dashboard backend (Flask REST API)
├── templates/
│   └── index.html           # Modern dashboard UI
└── static/
    ├── css/style.css        # Dark fintech theme with glassmorphism
    └── js/app.js            # Reactive filtering, search, sorting & modals
```

---

## 💻 How to Run

Ensure you are using the virtual environment in `d:\share_analysis`:

### 1. Launch the Modern Web Dashboard

To start the interactive web application:

```powershell
.\.venv\Scripts\python.exe app.py
```
Or via the scanner script:
```powershell
.\.venv\Scripts\python.exe dividend_scanner.py --web
```

Then open your browser at:
👉 **`http://localhost:5000`**

---

### 2. Run the CLI Scanner (Terminal)

You can run the scanner directly in your terminal with specific timeframe filters:

#### A. Show breakdown across all timeframes:
```powershell
.\.venv\Scripts\python.exe dividend_scanner.py
```

#### B. Filter by specific timeframe:
* **Within 5 Days:**
  ```powershell
  .\.venv\Scripts\python.exe dividend_scanner.py --days 5
  ```
* **Within 10 Days:**
  ```powershell
  .\.venv\Scripts\python.exe dividend_scanner.py --days 10
  ```
* **Within 20 Days:**
  ```powershell
  .\.venv\Scripts\python.exe dividend_scanner.py --days 20
  ```
* **Within 30 Days:**
  ```powershell
  .\.venv\Scripts\python.exe dividend_scanner.py --days 30
  ```
* **Within 45 Days:**
  ```powershell
  .\.venv\Scripts\python.exe dividend_scanner.py --days 45
  ```
* **Within 60 Days:**
  ```powershell
  .\.venv\Scripts\python.exe dividend_scanner.py --days 60
  ```
* **Within 75 Days:**
  ```powershell
  .\.venv\Scripts\python.exe dividend_scanner.py --days 75
  ```
* **Within 90 Days:**
  ```powershell
  .\.venv\Scripts\python.exe dividend_scanner.py --days 90
  ```

#### C. All upcoming dividends:
```powershell
.\.venv\Scripts\python.exe dividend_scanner.py --all
```

#### D. Filter by Minimum Dividend Yield (e.g., >= 2.0%):
```powershell
.\.venv\Scripts\python.exe dividend_scanner.py --days 60 --min-yield 2.0
``````

#### E. Export to CSV:
```powershell
.\.venv\Scripts\python.exe dividend_scanner.py --days 30 --export upcoming_dividends.csv
```

#### F. Force refresh live data from exchange:
```powershell
.\.venv\Scripts\python.exe dividend_scanner.py --days 10 --refresh
```

---

## 🔑 Configuration & Token

Your Upstox Analytics Token is stored in [.env](file:///d:/share_analysis/.env):
```env
TOKEN=your_token_here
```
When you regenerate a token in your Upstox Developer Console, simply update the token in this file or click **"Sync Live Data"** in the web dashboard.
