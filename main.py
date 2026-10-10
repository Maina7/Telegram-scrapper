import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

WEBSITE = os.getenv("WEBSITE")
if not WEBSITE:
    raise SystemExit("WEBSITE must be set in .env")

OUT_DIR = BASE_DIR / "kenyan_towns"
OUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/127.0 Safari/537.36"
    )
}

# WordPress thumbnails are named "<name>-600x600.jpg"; the original is "<name>.jpg"
THUMB_SUFFIX = re.compile(r"-\d+x\d+(?=\.\w+$)")


def safe_name(text):
    """Turn a town name into a filename-safe string."""
    return re.sub(r"[^\w\- ]", "", text).strip().replace(" ", "_")


def find_images(html):
    """Return a list of (name, image_url) for every town card on the page."""
    soup = BeautifulSoup(html, "html.parser")
    found = []
    seen = set()

    for card in soup.select("div.cards div.card"):
        img = card.find("img")
        if not img or not img.get("src"):
            continue

        url = urljoin(WEBSITE, img["src"])
        if url in seen:
            continue
        seen.add(url)

        title = card.find(["h4", "h3", "h2"])
        name = safe_name(title.get_text()) if title else ""
        if not name:
            name = safe_name(Path(urlparse(url).path).stem)
        found.append((name, url))

    return found


def download(session, name, url):
    """Download one image, preferring the full-size original over the thumbnail."""
    ext = Path(urlparse(url).path).suffix.lower() or ".jpg"
    path = OUT_DIR / f"{name}{ext}"
    if path.exists():
        return path, False

    original = THUMB_SUFFIX.sub("", url)
    for candidate in dict.fromkeys([original, url]):
        r = session.get(candidate, timeout=30)
        if r.ok and r.headers.get("Content-Type", "").startswith("image/"):
            path.write_bytes(r.content)
            return path, True

    raise RuntimeError(f"HTTP {r.status_code}")


def main():
    with requests.Session() as session:
        session.headers.update(HEADERS)

        page = session.get(WEBSITE, timeout=30)
        page.raise_for_status()

        images = find_images(page.text)
        if not images:
            raise SystemExit("No images found - the page layout may have changed.")
        print(f"Found {len(images)} images, saving into {OUT_DIR}")

        saved = skipped = failed = 0
        for name, url in images:
            try:
                path, is_new = download(session, name, url)
            except Exception as e:
                failed += 1
                print(f"Failed {name}: {e}")
                continue

            if is_new:
                saved += 1
                print(f"Saved {path.name}")
                time.sleep(0.5)  # be polite to the server
            else:
                skipped += 1

        print(f"Done. Saved {saved}, skipped {skipped} already downloaded, failed {failed}.")


if __name__ == "__main__":
    main()
