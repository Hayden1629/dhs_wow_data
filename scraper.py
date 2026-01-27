"""
DHS WOW mugshot scraper.
Fetches mugshots and metadata from https://www.dhs.gov/wow via Selenium,
downloads images, saves data as JSON.
"""

import base64
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

ROOT_LINK = "https://www.dhs.gov/wow?page="  # add integer, page 0 to 1687
BASE_URL = "https://www.dhs.gov"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
MUGSHOTS_DIR = OUTPUT_DIR / "mugshots"
DATA_FILE = OUTPUT_DIR / "mugshots.json"


def _make_driver(headless: bool = True) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)


def _sanitize_filename(s: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", s).strip() or "unknown"


def _parse_card(li, index_offset: int) -> dict | None:
    """Parse a single li.usa-card into mugshot data."""
    heading = li.select_one("h2.usa-card__heading")
    name_el = li.select_one(".usa-card_name")
    crime_el = li.select_one(".usa-card__crime")
    location_el = li.select_one(".usa-card__location")
    img = li.select_one(".usa-card__media img")

    if not all([heading, name_el, crime_el, location_el, img]):
        return None

    country = heading.get_text(strip=True)
    raw_name = name_el.get_text(strip=True).replace("Name:", "").strip()
    name = raw_name or "Unknown"

    raw_crime = crime_el.get_text(strip=True).replace("Convicted of:", "").strip()
    convicted_of = [c.strip() for c in raw_crime.split(",") if c.strip()] if raw_crime else []

    raw_loc = location_el.get_text(strip=True).replace("Arrested:", "").strip()
    arrested = raw_loc.replace("\xa0", " ").strip() if raw_loc else ""

    gang_affiliation = ""
    gang_el = li.select_one(".usa-card__gang")
    if gang_el:
        gang_affiliation = re.sub(r"Gang\s+Affiliation\s*:\s*", "", gang_el.get_text(strip=True), flags=re.I).strip()
    else:
        for div in li.select(".usa-card__body > div"):
            t = div.get_text(strip=True)
            if "Gang Affiliation" in t:
                gang_affiliation = re.sub(r"Gang\s+Affiliation\s*:\s*", "", t, flags=re.I).strip()
                break

    src = img.get("src", "")
    if not src:
        return None
    picture_url = urljoin(BASE_URL, src)

    # Use hash from filename for unique ID, e.g. wow-mugshot-01e06361f372bb503291a899ec89affa.jpg
    m = re.search(r"wow-mugshot-([a-f0-9]+)\.(?:jpg|png)", src, re.I)
    if m:
        file_id = m.group(1)
    else:
        # e.g. "Sahal%20Osman%20Shidane.png" -> use sanitized name + index
        m2 = re.search(r"/([^/]+)\.(?:jpg|png)", src)
        file_id = re.sub(r"[^a-zA-Z0-9_-]", "_", (m2.group(1) if m2 else "")) or f"idx{index_offset}"

    return {
        "ID": file_id,
        "NAME": name,
        "COUNTRY": country,
        "ARRESTED": arrested,
        "CONVICTED_OF": convicted_of,
        "GANG_AFFILIATION": gang_affiliation,
        "PICTURE": picture_url,
        "PICTURE_LOCAL": None,  # set after download
    }


def _download_image_via_selenium(driver: webdriver.Chrome, url: str, save_path: Path) -> bool:
    """Fetch image via same-origin fetch() in page context; save to disk."""
    try:
        b64 = driver.execute_async_script(
            """
            const url = arguments[0];
            const callback = arguments[arguments.length - 1];
            fetch(url)
                .then(r => r.blob())
                .then(blob => {
                    const fr = new FileReader();
                    fr.onload = () => {
                        const dataUrl = fr.result;
                        const b64 = dataUrl.indexOf(',') >= 0 ? dataUrl.split(',')[1] : '';
                        callback(b64);
                    };
                    fr.onerror = () => callback(null);
                    fr.readAsDataURL(blob);
                })
                .catch(() => callback(null));
            """,
            url,
        )
        if not b64:
            return False
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(base64.b64decode(b64))
        return True
    except Exception:
        return False


def _fetch_page(driver: webdriver.Chrome, page: int, wait_s: int = 1) -> BeautifulSoup | None:
    url = f"{ROOT_LINK}{page}"
    try:
        
        driver.get(url)
        WebDriverWait(driver, wait_s).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "li.usa-card"))
        )
        time.sleep(1)
        return BeautifulSoup(driver.page_source, "html.parser")
    except Exception:
        return None


def scrape_page(
    page: int,
    download_images: bool = True,
    output_dir: Path | None = None,
    driver: webdriver.Chrome | None = None,
    headless: bool = True,
) -> list[dict]:
    """
    Scrape a single page (0-indexed). Returns list of mugshot records.
    If driver is provided, it is not closed; otherwise a new one is created and closed.
    """
    out = output_dir or OUTPUT_DIR
    mugshots_path = out / "mugshots"
    mugshots_path.mkdir(parents=True, exist_ok=True)

    own_driver = driver is None
    if own_driver:
        driver = _make_driver(headless=headless)
    try:
        soup = _fetch_page(driver, page)
        if not soup:
            return []

        cards = soup.select("li.usa-card")
        records = []
        for i, li in enumerate(cards):
            rec = _parse_card(li, page * 1000 + i)
            if not rec:
                continue

            if download_images:
                ext = "jpg"
                if ".png" in rec["PICTURE"].lower():
                    ext = "png"
                safe_name = _sanitize_filename(rec["NAME"])[:80]
                fname = f"{rec['ID']}_{safe_name}.{ext}"
                save_path = mugshots_path / fname
                if _download_image_via_selenium(driver, rec["PICTURE"], save_path):
                    rec["PICTURE_LOCAL"] = str(save_path)
                time.sleep(0.25)

            records.append(rec)

        return records
    finally:
        if own_driver and driver:
            driver.quit()


def scrape_all(
    start: int = 0,
    end: int | None = None,
    download_images: bool = True,
    output_dir: Path | None = None,
    headless: bool = True,
    save_every_page: Path | str | None = None,
) -> list[dict]:
    """Scrape all pages from start to end (inclusive). end=None means up to page 1687.
    If save_every_page is set, append and save JSON after each page (incremental write).
    """
    if end is None:
        end = 1687
    out = output_dir or OUTPUT_DIR
    save_path = Path(save_every_page) if save_every_page else None
    all_records = []
    driver = _make_driver(headless=headless)
    try:
        for page in range(start, end + 1):
            recs = scrape_page(
                page,
                download_images=download_images,
                output_dir=out,
                driver=driver,
            )
            all_records.extend(recs)
            if recs:
                print(f"Page {page}: {len(recs)} mugshots")
            if save_path is not None:
                save_data(all_records, save_path)
            time.sleep(0.5)
        return all_records
    finally:
        driver.quit()


def save_data(records: list[dict], path: Path | None = None) -> None:
    path = path or DATA_FILE
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


def test_scrape_page_1(output_dir: Path | None = None) -> list[dict]:
    """
    Test run: scrape only page 1 (page=0), download images, save JSON.
    Returns the list of parsed mugshot records.
    """
    out = Path(output_dir or OUTPUT_DIR)
    data_path = out / "mugshots_page1_test.json"

    print("Test: scraping page 1 (page=0) only...")
    records = scrape_page(0, download_images=True, output_dir=out)
    print(f"Parsed {len(records)} mugshots from page 1.")

    if records:
        save_data(records, data_path)
        print(f"Data saved to {data_path}")
        print(f"Images saved to {out / 'mugshots'}")
        for r in records[:3]:
            crimes = r["CONVICTED_OF"][:2] if r["CONVICTED_OF"] else []
            gang = f" | Gang: {r['GANG_AFFILIATION']}" if r.get("GANG_AFFILIATION") else ""
            print(f"  - {r['NAME']} ({r['COUNTRY']}): {crimes}{gang}")
    else:
        print("No records found. Check page structure or network.")

    return records


def test_parse_list_html(html_path: Path | str | None = None) -> list[dict]:
    """
    Test parsing against a local HTML file (e.g. list.html).
    Does not fetch or download anything. Use to verify selectors.
    """
    path = Path(html_path or Path(__file__).resolve().parent / "list.html")
    if not path.exists():
        print(f"File not found: {path}")
        return []
    with open(path, encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    cards = soup.select("li.usa-card")
    records = []
    for i, li in enumerate(cards):
        rec = _parse_card(li, i)
        if rec:
            records.append(rec)
    print(f"Parsed {len(records)} mugshots from {path}")
    for r in records[:5]:
        gang = f" | Gang: {r['GANG_AFFILIATION']}" if r.get("GANG_AFFILIATION") else ""
        print(f"  - {r['NAME']} | {r['COUNTRY']} | {r['ARRESTED']} | {r['CONVICTED_OF']}{gang}")
    return records


if __name__ == "__main__":
    test_parse_list_html()  # verify parsing on list.html
    print("---")
    scrape_all(start=0, end=None, download_images=True, output_dir=OUTPUT_DIR, headless=True)
    #test_scrape_page_1()  # fetch page 1, download images, save JSON
