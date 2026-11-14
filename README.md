
# AI Trader Activity Intelligence Scanner

An AI-powered public trading activity research platform.

## Features

- Forex, cryptocurrency, stocks, indices and commodities
- Rolling 30-day date filtering
- Minimum and maximum entry-price filters
- BUY and SELL classification
- Public webpage scraping
- RSS feed collection
- AI-powered trade extraction
- Trader identification when publicly available
- Stop-loss and take-profit extraction
- Trade idea and execution claim classification
- SQLite database
- CSV export
- Optional search discovery

## Installation

Install Python 3.11 or newer.

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the application:

```bash
streamlit run app.py
```

## Configuration

Configure:

- AI_API_KEY
- AI_BASE_URL
- AI_MODEL
- TAVILY_API_KEY
- DATABASE_PATH

Use environment variables rather than committing private credentials.

## Important

Only scan public sources you are permitted to access.

The application does not bypass authentication, CAPTCHAs,
paywalls or website access restrictions.

A public execution claim is not independent broker verification.
Always inspect the original source before relying on extracted data.
# AI-TRADER-SCANNER
