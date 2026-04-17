import os
import sys
import time
import json
import threading
import tweepy
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from loguru import logger
import flask
#todo: there are 30 different ways in this one file. i could do a refactor and add a config file.... nah, this is fine for now. maybe later if i add more services or something. but for now, this is just gonna be a bit of a mess. sorry future me.
load_dotenv()
logger.add(sys.stderr, format="{time} {level} {message}", filter="main", level="INFO")

TOKEN_FILE = os.environ.get("TWITTER_TOKEN_FILE", "twitter_token.json")


def _save_token(token):
    with open(TOKEN_FILE, "w") as f:
        json.dump(token, f)
    logger.info("Twitter token saved to {}", TOKEN_FILE)


def _load_token() -> dict | None:
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            token = json.load(f)
        logger.info("Loaded Twitter token from {}", TOKEN_FILE)
        return token
    return None

# god there has to be a better way to do this.
class TwitterPKCEClient:
    """Wraps tweepy.Client with automatic OAuth 2.0 PKCE token refresh."""

    def __init__(self, token: dict, client_id: str, client_secret: str):
        self._token = token
        self._client_id = client_id
        self._client_secret = client_secret
        self._client = tweepy.Client(token["access_token"])

    def _refresh(self):
        from requests_oauthlib import OAuth2Session
        session = OAuth2Session(self._client_id, token=self._token)
        self._token = session.refresh_token(
            "https://api.twitter.com/2/oauth2/token",
            auth=HTTPBasicAuth(self._client_id, self._client_secret),
            client_id=self._client_id,
        )
        self._client = tweepy.Client(self._token["access_token"])
        _save_token(self._token)

    def _refresh_if_needed(self):
        if time.time() >= self._token.get("expires_at", 0) - 60:
            self._refresh()

    def create_tweet(self, **kwargs):
        self._refresh_if_needed()
        try:
            return self._client.create_tweet(**kwargs, user_auth=False)
        except tweepy.errors.BadRequest as e:
            if "token was invalid" in str(e):
                logger.warning("Token rejected by Twitter, forcing refresh")
                self._refresh()
                return self._client.create_tweet(**kwargs, user_auth=False)
            raise

def flask_login() -> TwitterPKCEClient:
    app = flask.Flask(__name__)
    token_ready = threading.Event()

    @app.route("/callback")
    def callback():
        token = handler.fetch_token(flask.request.url)
        _save_token(token)
        token_ready.set()
        return "Authorization successful! You can close this window."

    client_id = os.environ["TWITTER_CLIENT_ID"]
    client_secret = os.environ["TWITTER_CLIENT_SECRET"]

    token = _load_token()
    if token is not None:
        return TwitterPKCEClient(token, client_id, client_secret)

    handler = tweepy.OAuth2UserHandler(
        client_id=client_id,
        # must match the redirect URI set in the Twitter developer portal for this app
        redirect_uri=os.environ.get("TWITTER_REDIRECT_URI", "http://localhost:5000/callback"),
        scope=["tweet.read", "tweet.write", "users.read", "offline.access"],
        client_secret=client_secret,
    )
    print(f"Please go to this URL and authorize the app:\n{handler.get_authorization_url()}")
    # run flask in a daemon thread so the main thread can continue once the callback fires
    server = threading.Thread(target=lambda: app.run(port=5000), daemon=True)
    server.start()
    token_ready.wait()
    token = _load_token()
    if token is None:
        raise Exception("Failed to obtain Twitter token")
    return TwitterPKCEClient(token, client_id, client_secret)

def localhost_login() -> TwitterPKCEClient:
    client_id = os.environ["TWITTER_CLIENT_ID"]
    client_secret = os.environ["TWITTER_CLIENT_SECRET"]

    token = _load_token()
    if token is not None:
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