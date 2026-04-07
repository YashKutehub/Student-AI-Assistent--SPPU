import os
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Folder where `ingest.py` expects PDFs.
DATA_FOLDER = "./data"
if not os.path.exists(DATA_FOLDER):
    alt = os.path.join(os.path.dirname(__file__), "data")
    if os.path.exists(alt):
        DATA_FOLDER = alt

# This is the page that actually contains direct PDF links.
TARGET_URLS = [
    "http://sppudocs.unipune.ac.in/sites/circulars/Admission%20Circulars/Forms/AllItems.aspx",
    "http://sppudocs.unipune.ac.in/sites/circulars/Administrative%20Circulars%20%20Teaching/Forms/AllItems.aspx",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; StudentAI-SPPUbot/1.0)"}
PDF_EXT_RE = re.compile(r"\.pdf($|\?)", re.IGNORECASE)


def _pick_top_pdf_links(html: str, base_url: str, limit: int = 5) -> list[str]:
    """
    Grabs the top N PDF links from the SharePoint list.
    We grab multiple so we don't miss batch uploads on the same day.
    """
    soup = BeautifulSoup(html, "html.parser")
    pdf_links = []
    
    for a in soup.find_all("a", href=True):
        href = str(a.get("href", "")).strip()
        if not href or not PDF_EXT_RE.search(href):
            continue
            
        full_url = urljoin(base_url, href)
        
        # Prevent duplicates if the SharePoint list uses the same link for the icon and text
        if full_url not in pdf_links:
            pdf_links.append(full_url)
            
        if len(pdf_links) >= limit:
            break
            
    return pdf_links


def _safe_local_filename(pdf_url: str) -> str:
    """
    Use URL path basename and inject the Temporal Tag for the AI RAG system.
    """
    path = urlparse(pdf_url).path
    raw_name = os.path.basename(path)
    
    if not raw_name or len(raw_name) < 2:
        raw_name = f"sppu_notice_{int(datetime.utcnow().timestamp())}.pdf"
        
    # 🎯 THE FIX 1: Force the RAG system to recognize this as the newest file
    if not raw_name.startswith("LATEST_NOTICE_"):
        filename = f"LATEST_NOTICE_{raw_name}"
    else:
        filename = raw_name
        
    # Clean any lingering URL encoded spaces (%20)
    return filename.replace("%20", "_").replace(" ", "_")


def scrape_latest_sppu_notice():
    """
    Loops through the boards, downloads the top 5 newest PDFs, 
    and stops immediately if it sees a file we already have.
    """
    print("🌐 Initiating SPPU Multi-Target Scraper...")
    try:
        downloaded_files: list[str] = []

        for url in TARGET_URLS:
            print(f"   🔍 Scanning: {url.split('/sites/')[1].split('/Forms')[0].replace('%20', ' ')}")
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()

            pdf_urls = _pick_top_pdf_links(resp.text, base_url=url, limit=5)
            if not pdf_urls:
                continue

            for pdf_url in pdf_urls:
                filename = _safe_local_filename(pdf_url)
                local_path = os.path.join(DATA_FOLDER, filename)

                # 🎯 THE FIX 2: The Smart Break
                # If we hit a file we already have, we know all files below it are old!
                if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                    print(f"      ⏩ Found existing file '{filename}'. Stopping search for this board.")
                    break 

                # Download new file logic
                print(f"      📥 Downloading NEW notice: {filename}...")
                os.makedirs(DATA_FOLDER, exist_ok=True)
                
                resp_pdf = requests.get(pdf_url, headers=HEADERS, timeout=30, stream=True)
                resp_pdf.raise_for_status()

                with open(local_path, "wb") as f:
                    for chunk in resp_pdf.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            f.write(chunk)

                downloaded_files.append(filename)

        if downloaded_files:
            success_msg = f"Successfully synced {len(downloaded_files)} new notice(s): {', '.join(downloaded_files)}"
            print(f"🎉 {success_msg}")
            return True, success_msg
            
        print("✅ All targeted boards are already up to date.")
        return True, "All targeted boards are already up to date."

    except Exception as e:
        print(f"❌ Scraper Error: {e}")
        return False, f"Failed to sync: {str(e)}"