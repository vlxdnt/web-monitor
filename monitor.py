import requests
import hashlib
import time
import re
import sys
import subprocess
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup, Comment, NavigableString


URL = "www.example.com"  # Replace with the URL you want to monitor
INTERVAL = 30  # In seconds, adjust as needed
MAX_IFRAME_DEPTH = 3  # How many levels of nested iframes to follow
TIMEOUT = 15  # Seconds before a request gives up

HEADERS = {  # Mimic a browser request to avoid being blocked by the server
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}


def normalize_url(url):
    """Add https:// if the URL has no scheme (requests fails on 'www.example.com')"""
    url = url.strip()
    if not re.match(r"^[a-z][a-z0-9+.\-]*://", url, re.I):
        url = "https://" + url
    return url


def rewrite_google_url(url):
    """Turn Google Sheets/Docs/Slides viewer URLs into export URLs that return real data."""
    p = urlparse(url)
    if p.netloc != "docs.google.com":
        return url

    qs = parse_qs(p.query)
    frag = parse_qs(p.fragment)  # gid is often in the #fragment: ...#gid=123
    gid = (qs.get("gid") or frag.get("gid") or ["0"])[0]

    # Published-to-web sheet (/d/e/<key>/pubhtml)
    m = re.search(r"/spreadsheets/d/e/([\w-]+)", p.path)
    if m:
        return f"https://docs.google.com/spreadsheets/d/e/{m.group(1)}/pub?output=csv&gid={gid}"

    # Normal sheet
    m = re.search(r"/spreadsheets/d/([\w-]+)", p.path)
    if m:
        return f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv&gid={gid}"

    # Google Doc
    m = re.search(r"/document/d/([\w-]+)", p.path)
    if m and "/d/e/" not in p.path:
        return f"https://docs.google.com/document/d/{m.group(1)}/export?format=txt"

    # Google Slides
    m = re.search(r"/presentation/d/([\w-]+)", p.path)
    if m and "/d/e/" not in p.path:
        return f"https://docs.google.com/presentation/d/{m.group(1)}/export/txt"

    return url


def html_to_text(html, base_url, session, depth, seen):
    soup = BeautifulSoup(html, "html.parser")

    # Removes dynamic elements that change constantly or aren't "page content"
    for element in soup(["script", "style", "noscript", "nav", "footer", "header", "aside"]):
        element.decompose()
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()

    # Replace each iframe/frame with the text of the page it points to
    for frame in soup.find_all(["iframe", "frame"]):
        inner = ""
        if frame.get("srcdoc"):  # inline iframe content
            inner = html_to_text(frame["srcdoc"], base_url, session, depth + 1, seen)
        elif frame.get("src") and depth < MAX_IFRAME_DEPTH:
            src = frame["src"].strip()
            if not src.lower().startswith(("javascript:", "about:", "data:")):
                inner = fetch_content(urljoin(base_url, src), session, depth + 1, seen)
        frame.replace_with(NavigableString(f" {inner} "))

    return soup.get_text(separator=" ", strip=True)


def fetch_content(url, session, depth=0, seen=None):
    """Return the text (or a binary hash) for a URL, following iframes.
    Raises on network errors so a temporary failure is never mistaken for a page change"""
    seen = seen if seen is not None else set()
    url = rewrite_google_url(url)
    if url in seen:  # avoid infinite iframe loops
        return ""
    seen.add(url)

    response = session.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()
    if "text/html" in content_type:
        return html_to_text(response.text, response.url, session, depth, seen)
    if any(t in content_type for t in ("text/csv", "text/plain", "json", "xml")):
        return response.text  # Sheets CSV, Docs txt, APIs
    return "bin:" + hashlib.sha256(response.content).hexdigest()  # PDF, images, etc.


def get_page_hash(url):
    try:
        with requests.Session() as session:
            content = fetch_content(normalize_url(url), session)
    except requests.exceptions.ConnectionError as e:
        print(f"Connection error: {e}")
        return None
    except requests.exceptions.Timeout as e:
        print(f"Request timed out: {e}")
        return None
    except Exception as e:
        print(f"Error fetching the page: {e}")
        return None

    content = re.sub(r"\s+", " ", content).strip()  # ignore whitespace-only changes
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# Runs in a separate process so the popup never blocks the monitoring loop
POPUP_SCRIPT = """
import sys
import tkinter as tk
from tkinter import messagebox

root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
root.bell()
messagebox.showinfo("Page changed", sys.argv[1], parent=root)
root.destroy()
"""


def spawn_popup(url=URL):
    message = f"The page changed at {datetime.now():%H:%M:%S}:\n{url}"
    try:
        import tkinter  
    except ImportError:
        # Linux without python3-tk: fall back to the terminal
        print("\a" + message)
        return
    subprocess.Popen(
        [sys.executable, "-c", POPUP_SCRIPT, message],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main():
    print(f"Monitoring page for changes every {INTERVAL} seconds...")
    last_hash = get_page_hash(URL)

    if not last_hash:
        print("Failed to get initial page hash. Exiting.")
        return

    while True:
        time.sleep(INTERVAL)
        current_hash = get_page_hash(URL)

        if current_hash and current_hash != last_hash:
            print(f"Page changed at {datetime.now()}")
            spawn_popup(URL)
            last_hash = current_hash


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"Exiting...")