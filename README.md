# Universal Data Extraction Portal

A Streamlit-based commercial-grade data extraction portal using Playwright for stealth browser navigation and Google Gemini for dynamic schema generation.

## Features

- Fetch dynamic webpages with Playwright and realistic browser emulation
- Extract cleaned page text without relying on hardcoded table or selector rules
- Send page text to Google Gemini API for schema-free JSON extraction
- Build a pandas DataFrame dynamically from AI-generated records
- Export extracted results as CSV or Excel
- Prepare payloads for Google Sheets or cloud sync

## Requirements

- Python 3.11 or 3.12 (recommended)
- Python 3.15 is not supported for this app because many dependencies may not have compatible wheels yet
- `GEMINI_API_KEY` environment variable configured
- Playwright browsers installed

## Setup

1. Create a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

3. Install Playwright browsers:

```powershell
python -m playwright install chromium
```

4. Playwright browsers will be installed automatically on first run if missing.

5. On Linux, install the required browser dependencies if Playwright fails to launch:

```bash
sudo apt-get update && sudo apt-get install -y libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 libwayland-client0 libwayland-cursor0 libwayland-egl1 libgbm1 libasound2 libpangocairo-1.0-0 libxshmfence1
```

Alternatively use Playwright's built-in helper:

```bash
playwright install-deps
```

5. Set the Gemini API key in the app sidebar or via environment variable.

6. Run the app:

```powershell
streamlit run app.py
```

## Notes

- The project intentionally avoids hardcoded scraping rules and static table schemas.
- If you want Google Sheets or cloud database sync, use the prepared payload from the UI and connect it using `gspread`, `sqlalchemy`, or your cloud SDK.
