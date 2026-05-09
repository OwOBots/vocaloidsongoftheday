import asyncio
import datetime
import sys
import argparse
from urllib.parse import urlparse
import json

import httpx
from vocadb_wrapper import VocaDB
import random
from loguru import logger
from atproto import client_utils, models
import twitterauth
import blueauth
import configparser
import webhook

cfg = configparser.ConfigParser()
cfg.read("config.ini")

MAX_SONG_ID = cfg.getint("general", "max_song_id", fallback=1000000)
MAX_SONG_ATTEMPTS = cfg.getint("general", "max_song_attempts", fallback=50)
MAX_POST_ATTEMPTS = cfg.getint("general", "max_post_attempts", fallback=5)
POST_RETRY_BACKOFF = cfg.getint("general", "post_retry_backoff_seconds", fallback=30)
CYCLE_INTERVAL = cfg.getint("general", "cycle_interval_seconds", fallback=21600)

db = VocaDB()
logger.add(sys.stderr, format="{time} {level} {message}", filter="main", level="INFO")


def _webhook_notify(message):
    if cfg.get("general", "enable_webhook_notifications", fallback="false").lower() == "true":
        webhook.send_webhook_message(message)


def txt_builder(song, override_date=None):
    artists = ", ".join(artist["name"] for artist in song.get("artists", []))
    if not artists:
        artists = "unknown"
    try:
        txttemp = cfg.get("general", "text_templates_file", fallback="text_templates.json")
        with open(txttemp, "r") as f:
            data = json.load(f)
        today = override_date or datetime.date.today()
        if today.month == 2 and today.day == 24:
            text = random.choice(data["umamusume shitposting"]).format(name=song["name"], artists=artists)
        else:
            text = random.choice(data["templates"]).format(name=song["name"], artists=artists)
        albums = song.get("albums", [])
        if albums:
            text += random.choice(data["album_suffixes"]).format(album=albums[0]["name"])
        return text
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to load text templates: {e}, using fallback")
        return f"Vocaloid song of the day: {song['name']} by {artists}"


async def song_id_random() -> dict | None:
    rng = random.randint(0, MAX_SONG_ID)
    try:
        logger.debug(f"Trying to fetch song with ID {rng}")
        song = await db.song(song_id=rng, fields="pvs,Artists,Albums")
        if song is not None:
            logger.debug(f"Successfully fetched song: {song['name']}")
            return song
        else:
            logger.debug(f"No song found with ID {rng}")
            return None
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error while fetching song with ID {rng}: {e}")
        return None


async def find_song_with_pv(max_attempts=None):
    if max_attempts is None:
        max_attempts = MAX_SONG_ATTEMPTS
    for _ in range(max_attempts):
        try:
            song = await song_id_random()
        except Exception as e:
            logger.warning(f"VocaDB API error: {e}")
            await asyncio.sleep(5)
            continue
        if song is None:
            continue
        logger.info(f"Fetched song: {song['name']} (ID: {song['id']})")
        pv_url = pv_checker(song)
        if pv_url is not None:
            return song, pv_url
    return None, None


def pv_checker(song) -> str | None:
    if "pvs" not in song or len(song["pvs"]) == 0:
        logger.info(f"No PV found for song '{song['name']}'")
        return None
    youtube_url = None
    niconico_url = None
    for pv in song["pvs"]:
        host = urlparse(pv["url"]).hostname or ""
        if youtube_url is None and host in ("www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"):
            youtube_url = pv["url"]
        if niconico_url is None and host in ("www.nicovideo.jp", "nicovideo.jp", "nico.ms"):
            niconico_url = pv["url"]
    if youtube_url:
        logger.info(f"YouTube PV found for song '{song['name']}': {youtube_url}")
        return youtube_url
    if niconico_url:
        logger.info(f"NicoNico PV found for song '{song['name']}': {niconico_url}")
        return niconico_url
    logger.debug(f"No supported PV for song '{song['name']}', skipping.")
    return None


async def build_bsky_embed(client, url: str):
    host = urlparse(url).hostname or ""
    if host not in ("www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"):
        logger.debug(f"Skipping embed for non-YouTube URL: {url}")
        return None
    try:
        async with httpx.AsyncClient() as http:
            oembed_resp = await http.get(
                "https://www.youtube.com/oembed",
                params={"url": url, "format": "json"},
                timeout=10,
            )
            oembed = oembed_resp.json()
            thumb_resp = await http.get(oembed["thumbnail_url"], timeout=10)
            thumb_data = thumb_resp.content
        thumb_blob = (await client.upload_blob(thumb_data)).blob
        return models.AppBskyEmbedExternal.Main(
            external=models.AppBskyEmbedExternal.External(
                uri=url,
                title=oembed["title"],
                description="",
                thumb=thumb_blob,
            )
        )
    except (httpx.HTTPError, KeyError) as e:
        logger.warning(f"Failed to build Bluesky embed for {url}: {e}")
        return None


async def post(client, platform: str, text: str, url: str):
    if platform == "twitter":
        await asyncio.to_thread(client.create_tweet, text=f"{text}\n{url}")
    elif platform == "bluesky":
        tb = client_utils.TextBuilder().text(text)
        embed = await build_bsky_embed(client, url)
        await client.send_post(tb, embed=embed)
    elif platform == "dry-run":
        logger.info(f"Dry run mode: would post '{text}' with URL {url}")
        logger.info(text)
    else:
        raise ValueError(f"Unsupported platform: {platform}")

    _webhook_notify(f"Posted to {platform}: {text}\n{url}")


async def initialize_client(platform):
    if platform == "twitter":
        if cfg.get("twitter", "flask_oauth", fallback="false").lower() == "true":
            return twitterauth.flask_login()
        return twitterauth.localhost_login()
    elif platform == "bluesky":
        return await blueauth.blue_login()
    elif platform == "dry-run":
        return None
    raise ValueError(f"Unsupported platform: {platform}")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=["twitter", "bluesky", "dry-run"], default="bluesky")
    parser.add_argument("--date", help="override date for template selection (MM-DD), dry-run only", default=None)
    args = parser.parse_args()

    client = await initialize_client(args.platform)
    logger.info(f"Posting to {args.platform}")

    if args.platform == "dry-run":
        song, pv_url = await find_song_with_pv()
        if pv_url is None:
            logger.error(f"Failed to find a song with a YouTube PV after {MAX_SONG_ATTEMPTS} attempts.")
            return "done"
        override_date = None
        if args.date:
            month, day = args.date.split("-")
            override_date = datetime.date(2000, int(month), int(day))
        text = txt_builder(song, override_date=override_date)
        await post(client, args.platform, text, pv_url)
        return "done"

    while True:
        song, pv_url = await find_song_with_pv()
        if pv_url is None:
            logger.error(
                f"Failed to find a song with a YouTube PV after {MAX_SONG_ATTEMPTS} attempts, will retry next cycle.")
            await asyncio.sleep(CYCLE_INTERVAL)
            continue
        text = txt_builder(song)
        for attempt in range(MAX_POST_ATTEMPTS):
            try:
                await post(client, args.platform, text, pv_url)
                logger.info(f"Posted: {text}")
                break
            except Exception as e:
                logger.warning(f"Post failed (attempt {attempt + 1}/{MAX_POST_ATTEMPTS}): {e}")
                await asyncio.sleep(POST_RETRY_BACKOFF * (attempt + 1))
        else:
            logger.error(f"Failed to post after {MAX_POST_ATTEMPTS} attempts, will retry next cycle.")
        await asyncio.sleep(CYCLE_INTERVAL)


if __name__ == "__main__":
    async def _run():
        while True:
            try:
                _webhook_notify("Bot started/restarted")
                if await main() == "done":
                    break
                logger.error("Main loop exited unexpectedly, restarting in 30s...")
            except KeyboardInterrupt:
                logger.info("Shutting down gracefully...")
                break
            except Exception as e:
                _webhook_notify(f"Bot crashed with error: {e}, restarting in 30s...")
                logger.error(f"Bot crashed: {e}, restarting in 30s...")
            await asyncio.sleep(30)

    asyncio.run(_run())