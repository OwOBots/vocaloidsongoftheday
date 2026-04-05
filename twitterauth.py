import os
import sys
import time
import json
import tweepy
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from loguru import logger
load_dotenv()
logger.add(sys.stderr, format="{time} {level} {message}", filter="main", level="INFO")

TOKEN_FILE = os.environ.get("TWITTER_TOKEN_FILE", "twitter_token.json")


def _save_token(token):
    with open(TOKEN_FILE, "w") as f:
        json.dump(token, f)
    logger.info("Twitter token saved to {}", TOKEN_FILE)


def _load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            token = json.load(f)
        logger.info("Loaded Twitter token from {}", TOKEN_FILE)
        return token
    return None

class TwitterPKCEClient:
    """Wraps tweepy.Client with automatic OAuth 2.0 PKCE token refresh."""

    def __init__(self, token, client_id, client_secret):
        self._token = token
        self._client_id = client_id
        self._client_secret = client_secret
        self._client = tweepy.Client(token["access_token"])

    def _refresh_if_needed(self):
        if time.time() >= self._token.get("expires_at", 0) - 60:
            from requests_oauthlib import OAuth2Session
            session = OAuth2Session(self._client_id, token=self._token)
            self._token = session.refresh_token(
                "https://api.twitter.com/2/oauth2/token",
                auth=HTTPBasicAuth(self._client_id, self._client_secret),
                client_id=self._client_id,
            )
            self._client = tweepy.Client(self._token["access_token"])
            _save_token(self._token)

    def create_tweet(self, **kwargs):
        self._refresh_if_needed()
        return self._client.create_tweet(**kwargs,user_auth=False)


def localhost_login() -> TwitterPKCEClient:
    client_id = os.environ["TWITTER_CLIENT_ID"]
    client_secret = os.environ["TWITTER_CLIENT_SECRET"]

    token = _load_token()
    if token:
        return TwitterPKCEClient(token, client_id, client_secret)

    handler = tweepy.OAuth2UserHandler(
        client_id=client_id,
        # must match the redirect URI set in the Twitter developer portal for this app
        redirect_uri=os.environ.get("TWITTER_REDIRECT_URI", "http://localhost:5000/callback"),
        scope=["tweet.read", "tweet.write", "users.read", "offline.access"],
        client_secret=client_secret,
    )
    print(f"Please go to this URL and authorize the app:\n{handler.get_authorization_url()}")
    redirected_url = input("Paste the full redirect URL here: ")
    token = handler.fetch_token(redirected_url)
    _save_token(token)
    return TwitterPKCEClient(token, client_id, client_secret)