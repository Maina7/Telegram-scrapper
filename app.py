import os
import sys
import asyncio
import argparse
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument

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


def is_image(msg):
    """True for photos and images sent as files; videos and everything else are ignored."""
    if isinstance(msg.media, MessageMediaPhoto):
        return True
    if isinstance(msg.media, MessageMediaDocument):
        doc = msg.media.document
        mime = getattr(doc, "mime_type", None) or ""
        return mime.startswith("image/")
    return False


def get_count():
    """Number of images to save, from the command line or asked interactively."""
    parser = argparse.ArgumentParser(description="Save images from a Telegram channel.")
    parser.add_argument("count", nargs="?", type=int, help="number of new images to save")
    count = parser.parse_args().count

    while count is None or count < 1:
        try:
            count = int(input("How many images do you want to save? "))
        except ValueError:
            count = None
        except (EOFError, KeyboardInterrupt):
            sys.exit(1)
        if count is None or count < 1:
            print("Please enter a whole number greater than 0.")
    return count


def already_downloaded(msg_id):
    return any(OUT_DIR.glob(f"{msg_id}.*"))


async def main(count):
    async with TelegramClient(str(BASE_DIR / "session"), API_ID, API_HASH) as client:
        channel = await client.get_entity(CHANNEL)
        print(f"Saving {count} images from '{getattr(channel, 'title', CHANNEL)}' into {OUT_DIR}")

        saved = skipped = 0
        async for msg in client.iter_messages(channel, limit=None):
            if saved >= count:
                break
            if not msg.media or not is_image(msg):
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
                print(f"Saved {saved}/{count}: {path}")

        if saved < count:
            print(f"Channel ran out of new images: saved {saved} of {count}.")
        print(f"Done. Saved {saved}, skipped {skipped} already downloaded.")


if __name__ == "__main__":
    asyncio.run(main(get_count()))
