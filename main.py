import os
import re
import csv
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

WEBSITE = os.getenv("WEBSITE")
if not WEBSITE:
    raise SystemExit("WEBSITE must be set in .env")

OUT_FILE = BASE_DIR / "nairobi_cities.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/127.0 Safari/537.36"
    )
}

# Delay between page requests, to be polite to the server
DELAY = 2


def parse_page(html, page_url):
    """Return (cities, page_urls, expected_total) for one listing page."""
    soup = BeautifulSoup(html, "html.parser")

    cities = []
    for a in soup.select(".card-body a.link[href$='_city']"):
        name = " ".join(a.get_text().split())
        if name:
            cities.append((name, urljoin(page_url, a["href"])))

    # Links to every page (1, 2, 3, ...) from the pagination bar
    page_urls = [urljoin(page_url, a["href"]) for a in soup.select("ul.pagination a.page-link[href]")]

    # "276 found in this state." -> 276
    total = None
    match = re.search(r"(\d+)\s+found in this state", soup.get_text())
    if match:
        total = int(match.group(1))

    return cities, page_urls, total


def main():
    with requests.Session() as session:
        session.headers.update(HEADERS)

        to_visit = [WEBSITE]
        visited = set()
        cities = {}
        expected = None

        while to_visit:
            url = to_visit.pop(0)
            if url in visited:
                continue
            visited.add(url)

            if len(visited) > 1:
                time.sleep(DELAY)

            r = session.get(url, timeout=30)
            r.raise_for_status()

            page_cities, page_urls, total = parse_page(r.text, r.url)
            expected = expected or total
            for name, link in page_cities:
                cities.setdefault(link, name)
            print(f"{url}: {len(page_cities)} cities")

            to_visit.extend(u for u in page_urls if u not in visited)

    if not cities:
        raise SystemExit("No cities found - the page layout may have changed.")

    with OUT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["city", "url"])
        for link, name in sorted(cities.items(), key=lambda item: item[1].lower()):
            writer.writerow([name, link])

    print(f"Done. Saved {len(cities)} cities from {len(visited)} pages to {OUT_FILE}")
    if expected and expected != len(cities):
        print(f"Warning: the site says {expected} cities, but {len(cities)} were scraped.")


if __name__ == "__main__":
    main()
