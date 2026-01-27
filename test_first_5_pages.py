"""
Test scrape of first 5 pages (0–4) to verify rate limiting and image downloads.
"""
from pathlib import Path

from scraper import OUTPUT_DIR, scrape_all, save_data

if __name__ == "__main__":
    out = Path(OUTPUT_DIR) / "first_5_pages"
    out.mkdir(parents=True, exist_ok=True)
    data_path = out / "mugshots_first5.json"

    print("Scraping first 5 pages (0–4)...")
    records = scrape_all(
        start=0,
        end=4,
        download_images=True,
        output_dir=out,
        headless=True,
    )

    save_data(records, data_path)
    print(f"\nDone. {len(records)} total mugshots.")
    print(f"Data: {data_path}")
    print(f"Images: {out / 'mugshots'}")

    with_local = sum(1 for r in records if r.get("PICTURE_LOCAL"))
    print(f"Images saved: {with_local} / {len(records)}")
    if with_local < len(records):
        print("(Some image downloads may have failed.)")
