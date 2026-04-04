import sys
import time
import argparse

import requests as req
from vocadb_wrapper import VocaDB
import random
from loguru import logger
from atproto import client_utils, models
import twitterauth
import blueauth

db = VocaDB()
logger.add(sys.stderr, format="{time} {level} {message}", filter="main", level="INFO")
def rand():
    rng = random.randint(0, 1000000)
    song = db.song(song_id=rng, fields="pvs")
    logger.debug(f"Trying to fetch song with ID {rng}")
    if song is not None:
        logger.debug(f"Successfully fetched song: {song['name']}")
        return song
    else:
        logger.debug(f"No song found with ID {rng}")
        return None

def pvChecker(song):
    if "pvs" not in song or len(song["pvs"]) == 0:
        logger.info(f"No PV found for song '{song['name']}'")
        return None
    for pv in song["pvs"]:
        if "youtube.com" in pv["url"] or "youtu.be" in pv["url"]:
            logger.info(f"YouTube PV found for song '{song['name']}': {pv['url']}")
            return pv["url"]
    logger.debug(f"No YouTube PV for song '{song['name']}', skipping.")
    return None

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


def post(client, platform: str, text: str, url: str):
    if platform == "twitter":
        client.create_tweet(text=f"{text}\n{url}")
    else:
        tb = client_utils.TextBuilder().text(text)
        embed = build_bsky_embed(client, url)
        client.send_post(tb, embed=embed)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=["twitter", "bluesky"], default="bluesky")
    args = parser.parse_args()

    if args.platform == "twitter":
        client = twitterauth.localhost_login()
    else:
        client = blueauth.blue_login()

    logger.info(f"Posting to {args.platform}")
    max_song_attempts = 50
    while True:
        pv_url = None
        song = None
        for _ in range(max_song_attempts):
            try:
                song = rand()
            except Exception as e:
                logger.warning(f"VocaDB API error: {e}")
                time.sleep(5)
                continue
            if song is None:
                continue
            logger.info(f"Fetched song: {song['name']} (ID: {song['id']})")
            pv_url = pvChecker(song)
            if pv_url is not None:
                break
        if pv_url is None:
            logger.error(f"Failed to find a song with a YouTube PV after {max_song_attempts} attempts, will retry next cycle.")
            time.sleep(6 * 60 * 60)
            continue

        text = f"Vocaloid song of the day: {song['name']}"
        for attempt in range(5):
            try:
                post(client, args.platform, text, pv_url)
                logger.info(f"Posted: {text}")
                break
            except Exception as e:
                logger.warning(f"Post failed (attempt {attempt + 1}/5): {e}")
                time.sleep(30 * (attempt + 1))
        else:
            # dear god.. if we failed 5 times in a row, something is really wrong and we should wait a long time before trying again
            logger.error("Failed to post after 5 attempts, will retry next cycle.")
        time.sleep(6 * 60 * 60)


if __name__ == "__main__":
    main()