import pytest
import time as time_module
from unittest.mock import patch, MagicMock


class TestTwitterPKCEClient:
    def _make_client(self, expires_at=None):
        with patch("tweepy.Client"):
            from twitterauth import TwitterPKCEClient
            token = {
                "access_token": "tok123",
                "expires_at": expires_at if expires_at is not None else (time_module.time() + 3600),
            }
            return TwitterPKCEClient(token, "client_id", "client_secret")

    def _make_expired_client(self):
        return self._make_client(expires_at=time_module.time() - 100)

    def test_create_tweet_delegates(self):
        client = self._make_client()
        client.create_tweet(text="hello")
        client._client.create_tweet.assert_called_once_with(text="hello", user_auth=False)

    def test_no_refresh_when_not_expired(self):
        client = self._make_client(expires_at=time_module.time() + 3600)
        client.create_tweet(text="still valid")
        # should not blow up, token is fresh
        client._client.create_tweet.assert_called_once()

    def test_refresh_called_when_expired(self):
        client = self._make_client(expires_at=time_module.time() - 100)
        with patch.object(client, "_refresh_if_needed") as mock_refresh:
            # also mock _client so tweepy doesn't actually fire
            client._client = MagicMock()
            client.create_tweet(text="after refresh")
            mock_refresh.assert_called_once()

    @patch("requests_oauthlib.OAuth2Session")
    def test_refresh_if_needed_updates_token(self, mock_oauth_cls):
        client = self._make_client(expires_at=time_module.time() - 100)
        client._token["refresh_token"] = "refresh_tok"

        new_token = {"access_token": "new_tok", "expires_at": time_module.time() + 3600}
        mock_session = MagicMock()
        mock_session.refresh_token.return_value = new_token
        mock_oauth_cls.return_value = mock_session

        with patch("tweepy.Client") as mock_tweepy_cls:
            client._refresh_if_needed()

        mock_session.refresh_token.assert_called_once()
        assert client._token == new_token


class TestLocalhostLogin:
    @patch("builtins.input", return_value="http://localhost:5000/callback?code=abc")
    @patch("builtins.print")
    @patch("tweepy.OAuth2UserHandler")
    @patch.dict("os.environ", {
        "TWITTER_CLIENT_ID": "cid",
        "TWITTER_CLIENT_SECRET": "csecret",
    })
    def test_localhost_login_flow(self, mock_handler_cls, mock_print, mock_input):
        from twitterauth import localhost_login

        mock_handler = MagicMock()
        mock_handler.get_authorization_url.return_value = "https://twitter.com/auth"
        mock_handler.fetch_token.return_value = {
            "access_token": "tok",
            "expires_at": time_module.time() + 3600,
        }
        mock_handler_cls.return_value = mock_handler

        with patch("tweepy.Client"):
            result = localhost_login()

        mock_handler.fetch_token.assert_called_once_with(
            "http://localhost:5000/callback?code=abc"
        )
        assert result is not None
