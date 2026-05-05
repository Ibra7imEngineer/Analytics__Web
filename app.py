import io
import json
import os
import platform
import random
import re
import subprocess
import sys
from urllib.parse import urlparse

import streamlit as st
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import google.generativeai as genai

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
PAGE_TIMEOUT_MS = 60_000
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
]

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

def install_playwright_browsers():
    """Install Playwright browsers if missing."""
    try:
        st.info("Installing Playwright browsers... This may take a few minutes.")
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )
        if result.returncode == 0:
            st.success("Playwright browsers installed successfully.")
        else:
            st.error(f"Failed to install browsers: {result.stderr}")
    except subprocess.TimeoutExpired:
        st.error("Browser installation timed out.")
    except Exception as e:
        st.error(f"Error installing browsers: {str(e)}")


def get_platform_install_instructions() -> str:
    current = platform.system().lower()
    if current == "linux":
        return (
            "Install the Playwright Chromium dependencies on Debian/Ubuntu with:\n"
            "  sudo apt-get update && sudo apt-get install -y libglib2.0-0 libnss3 libatk1.0-0 "
            "libatk-bridge2.0-0 libcups2 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 "
            "libwayland-client0 libwayland-cursor0 libwayland-egl1 libgbm1 libasound2 "
            "libpangocairo-1.0-0 libxshmfence1"
        )
    if current == "darwin":
        return (
            "Install Playwright browsers on macOS with:\n"
            "  python -m playwright install chromium"
        )
    if current == "windows":
        return (
            "Install Playwright browsers on Windows with an activated virtual environment:\n"
            "  python -m playwright install chromium"
        )
    return "Install Playwright browsers by running: python -m playwright install chromium"


def init_session_state():
    if "gemini_api_key" not in st.session_state:
        st.session_state["gemini_api_key"] = GEMINI_API_KEY or ""
    if st.session_state["gemini_api_key"]:
        genai.configure(api_key=st.session_state["gemini_api_key"])


def is_gemini_ready() -> bool:
    return bool(st.session_state.get("gemini_api_key", ""))

def validate_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def clean_html_text(html_content: str) -> str:
    soup = BeautifulSoup(html_content, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.extract()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    reduced = []
    for line in lines:
        line = re.sub(r"\s+", " ", line)
        if line:
            reduced.append(line)
    return "\n".join(reduced)


def build_gemini_prompt(raw_text: str) -> str:
    return (
        "Act as a data extraction engine. Analyze the provided webpage text, identify the primary recurring "
        "data entities (e.g., e-commerce products, player stats, articles), and extract them into a structured JSON "
        "array of objects. Automatically determine the appropriate column names (keys) based on the context. "
        "If the page is empty or blocked, return an empty array. Output only valid JSON. No additional text.\n\n"
        "Webpage Text:\n" + raw_text
    )


def parse_gemini_response(response) -> list:
    raw_text = response.text.strip()
    raw_text = re.sub(r"^```json\s*|```$", "", raw_text, flags=re.I).strip()
    match = re.search(r"(\[.*\])", raw_text, re.S)
    if match:
        raw_text = match.group(1)

    try:
        data = json.loads(raw_text)
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        return []
    return []


def fetch_page_content(url: str) -> str:
    if not validate_url(url):
        raise ValueError("Invalid URL. Use http:// or https:// format.")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ])
            context = browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            page = context.new_page()
            page.set_default_navigation_timeout(PAGE_TIMEOUT_MS)
            page.goto(url, wait_until="networkidle", timeout=PAGE_TIMEOUT_MS)
            page.wait_for_timeout(1200)
            return page.content()
    except Exception as error:
        msg = str(error)
        if "Executable doesn't exist" in msg and "playwright install" in msg:
            install_playwright_browsers()
            # Retry after install
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True, args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                    ])
                    context = browser.new_context(
                        user_agent=random.choice(USER_AGENTS),
                        viewport={"width": 1280, "height": 800},
                        locale="en-US",
                        extra_http_headers={
                            "Accept-Language": "en-US,en;q=0.9",
                        },
                    )
                    page = context.new_page()
                    page.set_default_navigation_timeout(PAGE_TIMEOUT_MS)
                    page.goto(url, wait_until="networkidle", timeout=PAGE_TIMEOUT_MS)
                    page.wait_for_timeout(1200)
                    return page.content()
            except Exception as retry_error:
                raise RuntimeError(f"Unable to fetch content after browser install: {str(retry_error)}") from retry_error
        if "error while loading shared libraries" in msg.lower() or "cannot open shared object file" in msg.lower():
            raise RuntimeError(
                "Playwright browser launch failed because required system libraries are missing. "
                + get_platform_install_instructions()
                + "\nThen rerun the app."
            ) from error
        if any(keyword in msg.lower() for keyword in ["blocked", "captcha", "bot", "denied"]):
            raise RuntimeError(
                "The target site appears to be blocking automated access. Try using a different URL or inspect anti-bot protection."
            ) from error
        raise RuntimeError(f"Unable to fetch content from the page: {msg}") from error


def parse_with_gemini(raw_text: str) -> list:
    if not is_gemini_ready():
        raise RuntimeError("Missing GEMINI_API_KEY environment variable.")

    prompt = build_gemini_prompt(raw_text)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return parse_gemini_response(response)
    except Exception as error:
        raise RuntimeError(f"Gemini parsing failed: {error}") from error


def normalize_records(records: list) -> list:
    normalized = []
    for record in records:
        if isinstance(record, dict):
            normalized.append({str(k): v for k, v in record.items()})
        else:
            normalized.append({"value": record})
    return normalized


def infer_columns(records: list) -> list:
    columns = []
    for record in records:
        if not isinstance(record, dict):
            continue
        for key in record.keys():
            if key not in columns:
                columns.append(key)
    return columns


def build_google_sheets_payload(records: list) -> list:
    normalized = normalize_records(records)
    if not normalized:
        return []

    columns = infer_columns(normalized)
    payload = [columns]
    for record in normalized:
        payload.append([record.get(col, "") for col in columns])
    return payload


def create_csv_bytes(records: list) -> bytes:
    normalized = normalize_records(records)
    if not normalized:
        return b""

    columns = infer_columns(normalized)
    buffer = io.StringIO()
    import csv
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for record in normalized:
        writer.writerow([record.get(col, "") for col in columns])
    return buffer.getvalue().encode("utf-8")


def create_excel_bytes(records: list) -> bytes:
    normalized = normalize_records(records)
    if not normalized:
        return b""

    from openpyxl import Workbook
    columns = infer_columns(normalized)
    wb = Workbook()
    ws = wb.active
    ws.append(columns)
    for record in normalized:
        ws.append([record.get(col, "") for col in columns])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


# -----------------------------------------------------------------------------
# Streamlit UI
# -----------------------------------------------------------------------------

def main():
    st.set_page_config(page_title="Universal Data Extraction Portal", page_icon="🔍", layout="wide")
    st.title("Universal Data Extraction Portal")
    st.markdown(
        "Use AI-driven, schema-free extraction to convert any website into structured tabular data. "
        "Powered by Playwright stealth browsing and Google Gemini."
    )

    init_session_state()
    gemini_ready = is_gemini_ready()

    with st.sidebar:
        st.header("Connector Status")
        st.write("Gemini API:", "✅ Ready" if gemini_ready else "❌ Missing")
        st.write("Playwright:", "✅ Enabled")
        st.markdown("---")
        st.text_input(
            "Gemini API Key",
            type="password",
            key="gemini_api_key_input",
            value=st.session_state.get("gemini_api_key", ""),
            help="Paste your Gemini API key here for this session.",
        )
        if st.session_state.get("gemini_api_key_input"):
            if st.session_state.get("gemini_api_key") != st.session_state["gemini_api_key_input"]:
                st.session_state["gemini_api_key"] = st.session_state["gemini_api_key_input"]
                genai.configure(api_key=st.session_state["gemini_api_key"])
                st.success("Gemini API key stored for this session.")
            gemini_ready = True

        st.markdown("---")
        st.write("**Run instructions:**")
        st.markdown(
            "1. Install dependencies from `requirements.txt`.\n"
            "2. Run `python -m playwright install chromium`.\n"
            "3. Paste the Gemini API key into the sidebar.\n"
            "4. Click Extract Data."
        )

    if not gemini_ready:
        st.warning(
            "The Gemini API key is required before extraction can proceed. Paste it into the sidebar or set GEMINI_API_KEY."
        )

    url = st.text_input("Target URL")
    action = st.button("Extract Data")

    if action:
        if not url:
            st.error("Please enter a valid URL to extract.")
        elif not validate_url(url):
            st.error("Please enter a valid http:// or https:// URL.")
        elif not gemini_ready:
            st.error("The Gemini API key is required before extraction can proceed.")
        else:
            try:
                with st.spinner("Fetching page content with Playwright..."):
                    html_content = fetch_page_content(url)
                    page_text = clean_html_text(html_content)

                if not page_text:
                    st.warning("Page loaded successfully but no text was extracted.")
                else:
                    with st.spinner("Parsing extracted text with Gemini..."):
                        records = parse_with_gemini(page_text)

                    if not records:
                        st.warning("Gemini did not return structured records. The page may be blocked or empty.")
                    else:
                        normalized_records = normalize_records(records)
                        columns = infer_columns(normalized_records)
                        st.success(f"Extracted {len(normalized_records)} records and {len(columns)} columns.")
                        st.table(normalized_records)
                        st.session_state["extracted_records"] = normalized_records
            except Exception as error:
                st.error(str(error))

    if "extracted_records" in st.session_state and st.session_state["extracted_records"]:
        records = st.session_state["extracted_records"]
        st.markdown("## Export / Sync")
        col1, col2 = st.columns(2)
        with col1:
            csv_data = create_csv_bytes(records)
            st.download_button(
                label="Download CSV",
                data=csv_data,
                file_name="extracted_data.csv",
                mime="text/csv",
            )
        with col2:
            excel_bytes = create_excel_bytes(records)
            st.download_button(
                label="Download Excel",
                data=excel_bytes,
                file_name="extracted_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        st.markdown("### Cloud sync payload")
        st.code(json.dumps(build_google_sheets_payload(records)[:5], indent=2, ensure_ascii=False), language="json")
        st.info("Use the payload above as a Google Sheets or cloud database sync structure.")


if __name__ == "__main__":
    main()
