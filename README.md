# Vocaloid Song of the Day Bot

Automated bot that posts a randomly selected Vocaloid song every 6 hours. Supports posting to **Twitter** and **Bluesky**.

## How It Works

1. Picks a random song ID and fetches it from the [VocaDB API](https://vocadb.net/api)
2. Filters for songs that have a YouTube PV — retries if none found
3. Builds a post with the song title, artist(s), and YouTube link
4. On Bluesky, attaches a rich embed with the video thumbnail and title
5. Retries up to 5 times with exponential backoff on failure
6. Sleeps 6 hours and repeats

## Setup

**Install dependencies** (requires [uv](https://github.com/astral-sh/uv)):
```sh
uv sync
```

**Create a `.env` file** with your API credentials:
```env
# Twitter
TWITTER_API_KEY=...
TWITTER_API_SECRET_KEY=...
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_TOKEN_SECRET=...

# Bluesky
APU=yourhandle.bsky.social
AP=yourpassword
```

## Usage

```sh
# Post to Bluesky (default)
python main.py

# Post to Twitter
python main.py --platform twitter
```

## Files

| File | Description |
|------|-------------|
| `main.py` | Bot loop, song selection, and posting logic |
| `vocadb_wrapper.py` | VocaDB REST API client |
| `blueauth.py` | Bluesky authentication |
| `twitterauth.py` | Twitter (Tweepy) authentication |

## Dependencies

- [atproto](https://github.com/MarshalX/atproto) — Bluesky / AT Protocol client
- [tweepy](https://www.tweepy.org/) — Twitter API client
- [requests](https://requests.readthedocs.io/) — HTTP
- [loguru](https://github.com/Delgan/loguru) — Logging
- [python-dotenv](https://github.com/theskumar/python-dotenv) — Env var loading

Requires Python >= 3.13.
