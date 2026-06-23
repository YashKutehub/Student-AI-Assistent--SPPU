import os
import re
from datetime import datetime
from urllib.parse import urlparse, quote

import requests
from bs4 import BeautifulSoup

DATA_FOLDER = "./data"
if not os.path.exists(DATA_FOLDER):
    alt = os.path.join(os.path.dirname(__file__), "data")
    if os.path.exists(alt):
        DATA_FOLDER = alt

TARGET_URLS = [
    "http://sppudocs.unipune.ac.in/sites/circulars/Admission%20Circulars/Forms/AllItems.aspx",
    "http://sppudocs.unipune.ac.in/sites/circulars/Administrative%20Circulars%20%20Teaching/Forms/AllItems.aspx",
]

BASE_URL = "http://sppudocs.unipune.ac.in"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; StudentAI-SPPUbot/1.0)"}
PDF_EXT_RE = re.compile(r"\.pdf($|\s*$)", re.IGNORECASE)


def _fix_url(href: str) -> str:
    """
    SharePoint hrefs contain raw spaces — encode them properly.
    e.g. '/sites/circulars/Admission Circulars/file name.pdf'
         -> 'http://sppudocs.unipune.ac.in/sites/circulars/Admission%20Circulars/file%20name.pdf'
    """
    href = href.strip()
    if href.startswith("http"):
        parsed = urlparse(href)
        return parsed._replace(path=quote(parsed.path, safe="/%")).geturl()
    else:
        return BASE_URL + quote(href, safe="/%")


def _pick_top_pdf_links(html: str, limit: int = 5) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    pdf_links = []

    for a in soup.find_all("a", href=True):
        href = str(a.get("href", "")).strip()
        if not href:
            continue
        if not PDF_EXT_RE.search(href.split("?")[0]):
            continue

        full_url = _fix_url(href)

        if full_url not in pdf_links:
            pdf_links.append(full_url)

        if len(pdf_links) >= limit:
            break

    return pdf_links


def _safe_local_filename(pdf_url: str) -> str:
    path = urlparse(pdf_url).path
    raw_name = os.path.basename(path)

    if not raw_name or len(raw_name) < 2:
        raw_name = f"sppu_notice_{int(datetime.utcnow().timestamp())}.pdf"

    if not raw_name.startswith("LATEST_NOTICE_"):
        filename = f"LATEST_NOTICE_{raw_name}"
    else:
        filename = raw_name

    return filename.replace("%20", "_").replace(" ", "_")


def scrape_latest_sppu_notice():
    print("🌐 Initiating SPPU Multi-Target Scraper...")
    try:
        downloaded_files: list[str] = []

        for url in TARGET_URLS:
            section = url.split('/sites/')[1].split('/Forms')[0].replace('%20', ' ')
            print(f"   🔍 Scanning: {section}")

            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()

            pdf_urls = _pick_top_pdf_links(resp.text, limit=5)

            if not pdf_urls:
                print(f"      ⚠️  No PDF links found on this page.")
                continue

            print(f"      Found {len(pdf_urls)} PDF links.")

            for pdf_url in pdf_urls:
                filename = _safe_local_filename(pdf_url)
                local_path = os.path.join(DATA_FOLDER, filename)

                if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                    print(f"      ⏩ Already exists: '{filename}'. Stopping for this section.")
                    break

                print(f"      📥 Downloading: {filename}...")
                os.makedirs(DATA_FOLDER, exist_ok=True)

                resp_pdf = requests.get(pdf_url, headers=HEADERS, timeout=30, stream=True)
                resp_pdf.raise_for_status()

                with open(local_path, "wb") as f:
                    for chunk in resp_pdf.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            f.write(chunk)

                downloaded_files.append(filename)
                print(f"      ✅ Saved: {filename}")

        if downloaded_files:
            msg = f"Successfully synced {len(downloaded_files)} new notice(s): {', '.join(downloaded_files)}"
            print(f"🎉 {msg}")
            return True, msg

        print("✅ All boards already up to date.")
        return True, "All targeted boards are already up to date."

    except Exception as e:
        print(f"❌ Scraper Error: {e}")
        return False, f"Failed to sync: {str(e)}"


if __name__ == "__main__":
    scrape_latest_sppu_notice()