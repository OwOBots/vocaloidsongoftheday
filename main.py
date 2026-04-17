import datetime
import sys
import time
import argparse
from urllib.parse import urlparse
import json

import requests as req
from vocadb_wrapper import VocaDB
import random
from loguru import logger
from atproto import client_utils, models
import twitterauth
import blueauth
import configparser

cfg = configparser.ConfigParser()
cfg.read("config.ini")

db = VocaDB()
logger.add(sys.stderr, format="{time} {level} {message}", filter="main", level="INFO")

def txt_builder(song, override_date=None):
    # imagine delaying your game for 5 years. couldn't be me. (lie)
    # it may swap text templates ;3
    # for now this is just gonna be a list of templates that we randomly pick from, but eventually i want it to be a bit smarter and like, use different templates based on the song or something. but for now, this is good enough.
    artists = ", ".join(artist["name"] for artist in song.get("artists", []))
    if not artists:
        artists = "unknown"
    try:
        with open("text_templates.json", "r") as f:
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
    except Exception as e:
        logger.warning(f"Failed to load text templates: {e}, using fallback")
        return f"Vocaloid song of the day: {song['name']} by {artists}"


def song_id_random() -> dict | None:
    """

    :rtype: dict | None
    """
    rng = random.randint(0, 1000000)
    try:
        logger.debug(f"Trying to fetch song with ID {rng}")
        song = db.song(song_id=rng, fields="pvs,Artists,Albums")
        if song is not None:
            logger.debug(f"Successfully fetched song: {song['name']}")
            return song
        else:
            logger.debug(f"No song found with ID {rng}")
            return None
    except req.HTTPError as e:
        logger.error(f"HTTP error while fetching song with ID {rng}: {e}")
        return None


def find_song_with_pv(max_attempts=50):
    for _ in range(max_attempts):
        try:
            song = song_id_random()
        except Exception as e:
            logger.warning(f"VocaDB API error: {e}")
            time.sleep(5)
            continue
        if song is None:
            continue
        logger.info(f"Fetched song: {song['name']} (ID: {song['id']})")
        pv_url = pvChecker(song)
        if pv_url is not None:
            return song, pv_url
    return None, None


def pvChecker(song) -> str | None:
    # let's be real, if there are no PVs at all, it's not gonna have a youtube one
    if "pvs" not in song or len(song["pvs"]) == 0:
        logger.info(f"No PV found for song '{song['name']}'")
        return None
    #TODO: niconico pvs are common tbh. add support for them, but you know,
    # niconico blocks non jp ips. and the bot is hosted in the us.
    for pv in song["pvs"]:
        host = urlparse(pv["url"]).hostname or ""
        if host in ("www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"):
            logger.info(f"YouTube PV found for song '{song['name']}': {pv['url']}")
            return pv["url"]
    logger.debug(f"No YouTube PV for song '{song['name']}', skipping.")
    return None

# i dont like this, bsky embeds have to do this. but twitter just takes a url and does the rest. bluesky is so annoying.
def build_bsky_embed(client, url: str):
    oembed = req.get(
        "https://www.youtube.com/oembed",
        params={"url": url, "format": "json"},
        timeout=10,
    ).json()
    thumb_data = req.get(oembed["thumbnail_url"], timeout=10).content
    thumb_blob = client.upload_blob(thumb_data).blob
    return models.AppBskyEmbedExternal.Main(
        external=models.AppBskyEmbedExternal.External(
            uri=url,
            title=oembed["title"],
            description="",
            thumb=thumb_blob,
        )
    )


# at some point im gonna add fediverse but the apis for them depends
# on the specific platform so for now this is just twitter and bluesky
def post(client, platform: str, text: str, url: str):
    if platform == "twitter":
        client.create_tweet(text=f"{text}\n{url}")
    elif platform == "bluesky":
        tb = client_utils.TextBuilder().text(text)
        embed = build_bsky_embed(client, url)
        client.send_post(tb, embed=embed)
    elif platform == "dry-run":
        logger.info(f"Dry run mode: would post '{text}' with URL {url}")
        logger.info(text)
    else:
        raise ValueError(f"Unsupported platform: {platform}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=["twitter", "bluesky", "dry-run"], default="bluesky")
    parser.add_argument("--date", help="override date for template selection (MM-DD), dry-run only", default=None)
    args = parser.parse_args()

    if args.platform == "twitter":
        if cfg.get("twitter", "flask_oauth", fallback="false").lower() == "true":
            client = twitterauth.flask_login() # atp i gotta chose one or the other.
        else:
            client = twitterauth.localhost_login()
    elif args.platform == "bluesky":
        client = blueauth.blue_login()
    elif args.platform == "dry-run":
        client = None
    else:
        raise ValueError(f"Unsupported platform: {args.platform}")

    logger.info(f"Posting to {args.platform}")
    max_song_attempts = 50

    if args.platform == "dry-run":
        song, pv_url = find_song_with_pv(max_song_attempts)
        if pv_url is None:
            logger.error(f"Failed to find a song with a YouTube PV after {max_song_attempts} attempts.")
            return "done"
        override_date = None
        if args.date:
            month, day = args.date.split("-")
            override_date = datetime.date(2000, int(month), int(day))
        text = txt_builder(song, override_date=override_date)
        post(client, args.platform, text, pv_url)
        return "done"

    while True:
        song, pv_url = find_song_with_pv(max_song_attempts)
        if pv_url is None:
            logger.error(
                f"Failed to find a song with a YouTube PV after {max_song_attempts} attempts, will retry next cycle.")
            time.sleep(6 * 60 * 60)
            continue
        text = txt_builder(song)
        for attempt in range(5):
            try:
                post(client, args.platform, text, pv_url)
                logger.info(f"Posted: {text}")
                break
            except Exception as e:
                # this could fail for a lot of reasons, like a transient network error, or hitting a rate limit. in any case, we should just wait a bit and try again, rather than crashing the whole bot
                logger.warning(f"Post failed (attempt {attempt + 1}/5): {e}")
                time.sleep(30 * (attempt + 1))
        else:
            # dear god.. if we failed 5 times in a row, something is really wrong and we should wait a long time before trying again
            logger.error("Failed to post after 5 attempts, will retry next cycle.")
        time.sleep(
            6 * 60 * 60)  # why did i make 6 hours math like... just do 21600 seconds smh. oh well it works and im not changing it now


if __name__ == "__main__":
    while True:
        try:
            if main() == "done":
                break
            logger.error("Main loop exited unexpectedly, restarting in 30s...")
        except KeyboardInterrupt:
            logger.info("Shutting down gracefully...")
            break
        except Exception as e:
            # tbh, if the bot is crashing this hard, we probably want to know about it and fix it, rather than just silently restarting. but at least this way it won't be down for days while i'm asleep or something.
            logger.error(f"Bot crashed: {e}, restarting in 30s...")
        time.sleep(30)
