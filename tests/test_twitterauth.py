import pytest
import json
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

    @patch("twitterauth._save_token")
    @patch("requests_oauthlib.OAuth2Session")
    def test_refresh_if_needed_updates_token(self, mock_oauth_cls, mock_save):
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
        mock_save.assert_called_once_with(new_token)


class TestTokenPersistence:
    def test_save_and_load_token(self, tmp_path):
        token_file = tmp_path / "token.json"
        token = {"access_token": "tok", "expires_at": 9999999999}

        with patch("twitterauth.TOKEN_FILE", str(token_file)):
            from twitterauth import _save_token, _load_token
            _save_token(token)
            loaded = _load_token()

        assert loaded == token

    def test_load_token_returns_none_when_missing(self, tmp_path):
        token_file = tmp_path / "nonexistent.json"
        with patch("twitterauth.TOKEN_FILE", str(token_file)):
            from twitterauth import _load_token
            assert _load_token() is None


class TestLocalhostLogin:
    @patch("twitterauth._load_token")
    @patch.dict("os.environ", {
        "TWITTER_CLIENT_ID": "cid",
        "TWITTER_CLIENT_SECRET": "csecret",
    })
    def test_reuses_saved_token(self, mock_load):
        from twitterauth import localhost_login
        saved_token = {"access_token": "saved_tok", "expires_at": time_module.time() + 3600}
        mock_load.return_value = saved_token

        with patch("tweepy.Client"):
            result = localhost_login()

        assert result._token == saved_token

    @patch("twitterauth._save_token")
    @patch("twitterauth._load_token", return_value=None)
    @patch("builtins.input", return_value="http://localhost:5000/callback?code=abc")
    @patch("builtins.print")
    @patch("tweepy.OAuth2UserHandler")
    @patch.dict("os.environ", {
        "TWITTER_CLIENT_ID": "cid",
        "TWITTER_CLIENT_SECRET": "csecret",
    })
    def test_fresh_login_saves_token(self, mock_handler_cls, mock_print, mock_input, mock_load, mock_save):
        from twitterauth import localhost_login

        mock_handler = MagicMock()
        mock_handler.get_authorization_url.return_value = "https://twitter.com/auth"
        token = {"access_token": "tok", "expires_at": time_module.time() + 3600}
        mock_handler.fetch_token.return_value = token
        mock_handler_cls.return_value = mock_handler

        with patch("tweepy.Client"):
            result = localhost_login()

        mock_handler.fetch_token.assert_called_once_with(
            "http://localhost:5000/callback?code=abc"
        )
        mock_save.assert_called_once_with(token)
        assert result is not None
