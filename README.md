# Web Monitor

A lightweight Python script that watches a web page, Google Sheet, or online file and shows a popup when its content changes.

## How it works

The script fetches the target URL every `INTERVAL` seconds, reduces the response to its meaningful content, and compares a SHA-256 hash of that content against the previous check. If the hash differs, it prints a message and opens a popup.

What counts as "content" depends on what the URL returns:

| Target | What gets hashed |
|---|---|
| Web page (HTML) | Visible text only. Scripts, styles, `<noscript>`, nav, header, footer, aside and comments are removed, and whitespace is normalized. |
| Page with iframes | The page text plus the text of every iframe, fetched recursively (up to 3 levels deep). |
| Google Sheet / Doc / Slides | The exported contents (CSV for Sheets, plain text for Docs and Slides). |
| CSV, JSON, XML, plain text | The text itself. |
| Other files (PDF, images, ...) | The raw bytes. |

## Features

- **Noise filtering:** ignores scripts, styles, navigation and other non-content elements, so ads and tracking code are less likely to cause false alerts.
- **Iframe support:** embedded content is fetched and included in the comparison. Both `src` and inline `srcdoc` iframes work, and loops are detected.
- **Google Workspace support:** Sheets, Docs and Slides links, including published-to-web (`/pubhtml`) links, are automatically rewritten to export URLs. A `#gid=...` in the link selects a specific sheet tab.
- **Popup alerts:** a topmost message box with a sound, shown in a separate process so it never blocks monitoring.
- **Failure-safe:** if a request fails or times out, that check is skipped. A network error is never reported as a page change.
- **Browser-style User-Agent:** reduces the chance of being blocked by servers that reject unknown clients.

## Requirements

- Python 3.8 or newer
- `requests` and `beautifulsoup4` (listed in `requirements.txt`)
- `tkinter` for the popup. It is included with Python on Windows and macOS. On Debian/Ubuntu, install it with `sudo apt install python3-tk`. Without it, the script prints the alert to the terminal instead.

## Installation

```bash
git clone https://github.com/vlxdnt/web-monitor
cd web-monitor
pip install -r requirements.txt
```

## Configuration

Edit the constants at the top of `monitor.py`:

| Setting | Default | Description |
|---|---|---|
| `URL` | `"www.example.com"` | The page, sheet or file to monitor. `https://` is added automatically if you leave it out. |
| `INTERVAL` | `30` | Seconds between checks. |
| `MAX_IFRAME_DEPTH` | `3` | How many levels of nested iframes to follow. |
| `TIMEOUT` | `15` | Seconds before a request is abandoned. |

## Usage

```bash
python monitor.py
```

The script takes a baseline hash on startup, then checks at every interval. Press `Ctrl+C` to stop.

### Monitoring a Google Sheet

Paste the normal sheet URL (or the URL of a page that embeds the sheet in an iframe) into `URL`. The sheet must be either:

- shared as **"Anyone with the link can view"**, or
- **published to the web** (File → Share → Publish to web).

To watch a specific tab, make sure the URL ends with that tab's `#gid=...`. Each run watches one tab.

## Limitations

- **Private sheets and documents** are not supported, because the script cannot sign in to Google. Use the Google Sheets API with a service account for those.
- **JavaScript-rendered pages** (content injected by React, Vue and similar frameworks after the page loads) look empty to `requests`, so changes in that content won't be detected. A headless browser such as Playwright is needed for those.
- **Pages with built-in changing content** (timestamps, view counters, rotating ads, CSRF tokens) will trigger an alert on every check. If that happens, remove those elements before hashing or hash only the container you care about, for example `soup.select_one("#main")`.
- **Single page only:** the script monitors one URL, not a whole site.

## Disclaimer

This tool is intended for personal use. Keep your polling interval reasonable to avoid putting unnecessary load on servers or violating a site's Terms of Service. The author is not responsible for misuse or unintended consequences of automation.