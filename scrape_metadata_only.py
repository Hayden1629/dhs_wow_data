"""
Scrape metadata only (no image downloads). Use when you already have the mugshots.
Saves JSON to output/mugshots.json.
"""
import argparse
from pathlib import Path

from scraper import OUTPUT_DIR, scrape_all, save_data

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Scrape DHS WOW metadata only (no images)")
    ap.add_argument("--start", type=int, default=0, help="Start page (0-indexed)")
    ap.add_argument("--end", type=int, default=1687, help="End page (inclusive)")
    ap.add_argument("-o", "--output", type=Path, default=None, help="Output JSON path")
    args = ap.parse_args()

    out = OUTPUT_DIR
    data_path = args.output or (out / "mugshots.json")
    data_path = Path(data_path)
    data_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Scraping metadata only (pages {args.start}–{args.end}), no image downloads...")
    print(f"Writing incrementally to {data_path}")
    records = scrape_all(
        start=args.start,
        end=args.end,
        download_images=False,
        output_dir=out,
        headless=True,
        save_every_page=data_path,
    )
    print(f"\nDone. {len(records)} records in {data_path}")
