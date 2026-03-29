import os
import tweepy
from dotenv import load_dotenv

load_dotenv()

#classic auth.
def get_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=os.environ["TWITTER_API_KEY"],
        consumer_secret=os.environ["TWITTER_API_SECRET_KEY"],
        access_token=os.environ["TWITTER_ACCESS_TOKEN"],
        access_token_secret=os.environ["TWITTER_ACCESS_TOKEN_SECRET"],
    )
# OAuth 2.0 PKCE flow — requires TWITTER_CLIENT_ID and TWITTER_CLIENT_SECRET,
# and the redirect URI must match what's set in the Twitter developer portal.
def localhost_login() -> tweepy.Client:
    handler = tweepy.OAuth2UserHandler(
        client_id=os.environ["TWITTER_CLIENT_ID"],
        redirect_uri=os.environ.get("TWITTER_REDIRECT_URI", "http://localhost:5000/callback"),
        scope=["tweet.read", "tweet.write", "users.read"],
        client_secret=os.environ["TWITTER_CLIENT_SECRET"],
    )
    print(f"Please go to this URL and authorize the app:\n{handler.get_authorization_url()}")
    redirected_url = input("Paste the full redirect URL here: ")
    token = handler.fetch_token(redirected_url)
    return tweepy.Client(token["access_token"])