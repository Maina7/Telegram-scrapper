import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument

# Folder that contains this script; everything is resolved relative to it,
# so the script behaves the same no matter which directory it is run from.
BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
CHANNEL = os.getenv("CHANNEL")
if not (API_ID and API_HASH and CHANNEL):
    raise SystemExit("API_ID, API_HASH and CHANNEL must be set in .env")
API_ID = int(API_ID)

OUT_DIR = BASE_DIR / (os.getenv("OUT_DIR") or "downloads")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def media_kind(msg):
    """Return 'photo', 'video' or None for a message's media."""
    if isinstance(msg.media, MessageMediaPhoto):
        return "photo"
    if isinstance(msg.media, MessageMediaDocument):
        doc = msg.media.document
        mime = getattr(doc, "mime_type", None) or ""
        if mime.startswith("video/"):
            return "video"
    return None


def already_downloaded(msg_id):
    return any(OUT_DIR.glob(f"{msg_id}.*"))


async def main():
    async with TelegramClient(str(BASE_DIR / "session"), API_ID, API_HASH) as client:
        channel = await client.get_entity(CHANNEL)
        print(f"Scraping '{getattr(channel, 'title', CHANNEL)}' into {OUT_DIR}")

        saved = skipped = 0
        async for msg in client.iter_messages(channel, limit=None):
            if not msg.media or media_kind(msg) is None:
                continue

            if already_downloaded(msg.id):
                skipped += 1
                continue

            try:
                path = await msg.download_media(file=str(OUT_DIR / str(msg.id)))
            except Exception as e:
                print(f"Failed {msg.id}: {e}")
                continue

            if path:
                saved += 1
                print(f"Saved {path}")

        print(f"Done. Saved {saved}, skipped {skipped} already downloaded.")


if __name__ == "__main__":
    asyncio.run(main())
