import datetime
import json
import pytest
from unittest.mock import patch, MagicMock, mock_open


class TestRand:
    @patch("main.db")
    @patch("main.random.randint", return_value=500)
    def test_rand_returns_song(self, mock_randint, mock_db):
        from main import song_id_random
        mock_db.song.return_value = {"name": "Melt", "id": 500}
        result = song_id_random()
        assert result == {"name": "Melt", "id": 500}
        mock_db.song.assert_called_once_with(song_id=500, fields="pvs,Artists,Albums")

    @patch("main.db")
    @patch("main.random.randint", return_value=999999)
    def test_rand_returns_none_when_no_song(self, mock_randint, mock_db):
        from main import song_id_random
        mock_db.song.return_value = None
        result = song_id_random()
        assert result is None


class TestPvChecker:
    def test_returns_youtube_url(self):
        from main import pvChecker
        song = {
            "name": "World is Mine",
            "pvs": [
                {"url": "https://www.nicovideo.jp/watch/sm123"},
                {"url": "https://www.youtube.com/watch?v=abc123"},
            ],
        }
        assert pvChecker(song) == "https://www.youtube.com/watch?v=abc123"

    def test_returns_youtu_be_url(self):
        from main import pvChecker
        song = {
            "name": "Melt",
            "pvs": [{"url": "https://youtu.be/xyz789"}],
        }
        assert pvChecker(song) == "https://youtu.be/xyz789"

    def test_returns_none_when_no_pvs_key(self):
        from main import pvChecker
        song = {"name": "No PVs"}
        assert pvChecker(song) is None

    def test_returns_none_when_pvs_empty(self):
        from main import pvChecker
        song = {"name": "Empty PVs", "pvs": []}
        assert pvChecker(song) is None

    def test_returns_none_when_no_youtube(self):
        from main import pvChecker
        song = {
            "name": "NND Only",
            "pvs": [{"url": "https://www.nicovideo.jp/watch/sm456"}],
        }
        assert pvChecker(song) is None

    def test_returns_first_youtube_match(self):
        from main import pvChecker
        song = {
            "name": "Multi YT",
            "pvs": [
                {"url": "https://www.youtube.com/watch?v=first"},
                {"url": "https://www.youtube.com/watch?v=second"},
            ],
        }
        assert pvChecker(song) == "https://www.youtube.com/watch?v=first"

    def test_rejects_spoofed_youtube_domain(self):
        from main import pvChecker
        song = {
            "name": "Spoofed",
            "pvs": [
                {"url": "https://notyoutube.com/watch?v=abc"},
                {"url": "https://youtube.com.evil.com/watch?v=abc"},
                {"url": "https://youtu.be.evil.com/xyz"},
            ],
        }
        assert pvChecker(song) is None


class TestTxtBuilder:
    TEMPLATES_JSON = json.dumps({
        "templates": ["{name} by {artists}"],
        "album_suffixes": [" from {album}"],
        "umamusume shitposting": ["uma: {name} by {artists}"],
    })

    def test_normal_template(self):
        from main import txt_builder
        song = {"name": "Melt", "artists": [{"name": "ryo"}], "albums": []}
        with patch("builtins.open", mock_open(read_data=self.TEMPLATES_JSON)):
            result = txt_builder(song)
        assert result == "Melt by ryo"

    def test_multiple_artists(self):
        from main import txt_builder
        song = {"name": "Melt", "artists": [{"name": "ryo"}, {"name": "supercell"}], "albums": []}
        with patch("builtins.open", mock_open(read_data=self.TEMPLATES_JSON)):
            result = txt_builder(song)
        assert result == "Melt by ryo, supercell"

    def test_unknown_artists_when_empty(self):
        from main import txt_builder
        song = {"name": "Melt", "artists": [], "albums": []}
        with patch("builtins.open", mock_open(read_data=self.TEMPLATES_JSON)):
            result = txt_builder(song)
        assert result == "Melt by unknown"

    def test_unknown_artists_when_missing(self):
        from main import txt_builder
        song = {"name": "Melt", "albums": []}
        with patch("builtins.open", mock_open(read_data=self.TEMPLATES_JSON)):
            result = txt_builder(song)
        assert result == "Melt by unknown"

    def test_album_suffix_appended(self):
        from main import txt_builder
        song = {"name": "Melt", "artists": [{"name": "ryo"}], "albums": [{"name": "supercell"}]}
        with patch("builtins.open", mock_open(read_data=self.TEMPLATES_JSON)):
            result = txt_builder(song)
        assert result == "Melt by ryo from supercell"

    def test_feb_24_template(self):
        from main import txt_builder
        song = {"name": "Melt", "artists": [{"name": "ryo"}], "albums": []}
        with patch("builtins.open", mock_open(read_data=self.TEMPLATES_JSON)):
            result = txt_builder(song, override_date=datetime.date(2000, 2, 24))
        assert result == "uma: Melt by ryo"

    def test_fallback_on_error(self):
        from main import txt_builder
        song = {"name": "Melt", "artists": [{"name": "ryo"}]}
        with patch("builtins.open", side_effect=FileNotFoundError):
            result = txt_builder(song)
        assert result == "Vocaloid song of the day: Melt by ryo"


class TestPost:
    @patch("main.build_bsky_embed")
    @patch("main.client_utils")
    def test_post_bluesky(self, mock_utils, mock_embed):
        from main import post
        mock_client = MagicMock()
        mock_tb = MagicMock()
        mock_utils.TextBuilder.return_value.text.return_value = mock_tb
        mock_embed.return_value = "embed_obj"

        post(mock_client, "bluesky", "song of the day", "https://youtube.com/x")

        mock_client.send_post.assert_called_once_with(mock_tb, embed="embed_obj")

    def test_post_twitter(self):
        from main import post
        mock_client = MagicMock()

        post(mock_client, "twitter", "song of the day", "https://youtube.com/x")

        mock_client.create_tweet.assert_called_once_with(
            text="song of the day\nhttps://youtube.com/x"
        )

    def test_post_dry_run(self):
        from main import post
        post(None, "dry-run", "song of the day", "https://youtube.com/x")

    def test_post_unsupported_platform(self):
        from main import post
        with pytest.raises(ValueError, match="Unsupported platform"):
            post(None, "mastodon", "song of the day", "https://youtube.com/x")


class TestBuildBskyEmbed:
    @patch("main.models")
    @patch("main.req.get")
    def test_build_embed(self, mock_get, mock_models):
        from main import build_bsky_embed

        oembed_resp = MagicMock()
        oembed_resp.json.return_value = {
            "title": "Cool Song",
            "thumbnail_url": "https://img.youtube.com/vi/abc/hqdefault.jpg",
        }
        thumb_resp = MagicMock()
        thumb_resp.content = b"fakethumbdata"

        mock_get.side_effect = [oembed_resp, thumb_resp]

        mock_client = MagicMock()
        mock_client.upload_blob.return_value.blob = "blob_ref"

        result = build_bsky_embed(mock_client, "https://www.youtube.com/watch?v=abc")

        assert mock_get.call_count == 2
        mock_client.upload_blob.assert_called_once_with(b"fakethumbdata")
        mock_models.AppBskyEmbedExternal.External.assert_called_once_with(
            uri="https://www.youtube.com/watch?v=abc",
            title="Cool Song",
            description="",
            thumb="blob_ref",
        )


class TestMainRetryLogic:
    """Tests for the retry and error handling logic in main()."""

    @patch("main.time.sleep")
    @patch("main.post")
    @patch("main.txt_builder", return_value="test text")
    @patch("main.pvChecker", return_value="https://www.youtube.com/watch?v=abc")
    @patch("main.song_id_random", return_value={"name": "Melt", "id": 1, "pvs": []})
    @patch("main.blueauth.blue_login", return_value=MagicMock())
    @patch("main.argparse.ArgumentParser")
    def test_posts_successfully_on_first_try(
        self, mock_argparse, mock_login, mock_rand, mock_pv, mock_txt, mock_post, mock_sleep
    ):
        from main import main

        mock_argparse.return_value.parse_args.return_value = MagicMock(platform="bluesky")
        # Break out of the while True loop after one cycle
        mock_sleep.side_effect = [StopIteration]
        with pytest.raises(StopIteration):
            main()
        mock_post.assert_called_once()

    @patch("main.time.sleep")
    @patch("main.post")
    @patch("main.txt_builder", return_value="test text")
    @patch("main.pvChecker", return_value="https://www.youtube.com/watch?v=abc")
    @patch("main.song_id_random")
    @patch("main.blueauth.blue_login", return_value=MagicMock())
    @patch("main.argparse.ArgumentParser")
    def test_retries_on_api_exception(
        self, mock_argparse, mock_login, mock_rand, mock_pv, mock_txt, mock_post, mock_sleep
    ):
        from main import main

        mock_argparse.return_value.parse_args.return_value = MagicMock(platform="bluesky")
        # First call raises, second call succeeds
        mock_rand.side_effect = [
            Exception("VocaDB 404"),
            {"name": "Melt", "id": 1, "pvs": []},
        ]
        mock_sleep.side_effect = [None, StopIteration]  # first sleep is the 5s retry delay
        with pytest.raises(StopIteration):
            main()
        assert mock_rand.call_count == 2
        mock_post.assert_called_once()

    @patch("main.time.sleep")
    @patch("main.post")
    @patch("main.txt_builder", return_value="test text")
    @patch("main.pvChecker", return_value=None)
    @patch("main.song_id_random", return_value={"name": "No YT", "id": 1, "pvs": []})
    @patch("main.blueauth.blue_login", return_value=MagicMock())
    @patch("main.argparse.ArgumentParser")
    def test_gives_up_after_max_attempts(
        self, mock_argparse, mock_login, mock_rand, mock_pv, mock_txt, mock_post, mock_sleep
    ):
        from main import main

        mock_argparse.return_value.parse_args.return_value = MagicMock(platform="bluesky")
        # The 6hr sleep after exhausting attempts, then break
        mock_sleep.side_effect = StopIteration
        with pytest.raises(StopIteration):
            main()
        assert mock_rand.call_count == 50
        mock_post.assert_not_called()

    @patch("main.time.sleep")
    @patch("main.post")
    @patch("main.txt_builder", return_value="test text")
    @patch("main.pvChecker", return_value="https://www.youtube.com/watch?v=abc")
    @patch("main.song_id_random", return_value={"name": "Melt", "id": 1, "pvs": []})
    @patch("main.blueauth.blue_login", return_value=MagicMock())
    @patch("main.argparse.ArgumentParser")
    def test_retries_failed_posts(
        self, mock_argparse, mock_login, mock_rand, mock_pv, mock_txt, mock_post, mock_sleep
    ):
        from main import main

        mock_argparse.return_value.parse_args.return_value = MagicMock(platform="bluesky")
        # Post fails twice, then succeeds
        mock_post.side_effect = [Exception("network"), Exception("timeout"), None]
        mock_sleep.side_effect = [None, None, StopIteration]  # two backoff sleeps + final cycle sleep
        with pytest.raises(StopIteration):
            main()
        assert mock_post.call_count == 3

    @patch("main.time.sleep")
    @patch("main.post")
    @patch("main.txt_builder", return_value="test text")
    @patch("main.pvChecker", return_value="https://www.youtube.com/watch?v=abc")
    @patch("main.song_id_random", return_value={"name": "Melt", "id": 1, "pvs": []})
    @patch("main.blueauth.blue_login", return_value=MagicMock())
    @patch("main.argparse.ArgumentParser")
    def test_gives_up_posting_after_5_failures(
        self, mock_argparse, mock_login, mock_rand, mock_pv, mock_txt, mock_post, mock_sleep
    ):
        from main import main

        mock_argparse.return_value.parse_args.return_value = MagicMock(platform="bluesky")
        mock_post.side_effect = Exception("always fails")
        # 5 backoff sleeps + final cycle sleep, then break
        mock_sleep.side_effect = [None, None, None, None, None, StopIteration]
        with pytest.raises(StopIteration):
            main()
        assert mock_post.call_count == 5


class TestMainDryRun:
    @patch("main.post")
    @patch("main.txt_builder", return_value="test text")
    @patch("main.pvChecker", return_value="https://www.youtube.com/watch?v=abc")
    @patch("main.song_id_random", return_value={"name": "Melt", "id": 1, "pvs": []})
    @patch("main.argparse.ArgumentParser")
    def test_dry_run_exits_with_done(self, mock_argparse, mock_rand, mock_pv, mock_txt, mock_post):
        from main import main
        mock_argparse.return_value.parse_args.return_value = MagicMock(platform="dry-run", date=None)
        result = main()
        assert result == "done"
        mock_post.assert_called_once_with(None, "dry-run", "test text", "https://www.youtube.com/watch?v=abc")

    @patch("main.post")
    @patch("main.txt_builder", return_value="test text")
    @patch("main.pvChecker", return_value="https://www.youtube.com/watch?v=abc")
    @patch("main.song_id_random", return_value={"name": "Melt", "id": 1, "pvs": []})
    @patch("main.argparse.ArgumentParser")
    def test_dry_run_date_override(self, mock_argparse, mock_rand, mock_pv, mock_txt, mock_post):
        from main import main
        mock_argparse.return_value.parse_args.return_value = MagicMock(platform="dry-run", date="02-24")
        main()
        mock_txt.assert_called_once()
        _, kwargs = mock_txt.call_args
        assert kwargs["override_date"] == datetime.date(2000, 2, 24)

    @patch("main.pvChecker", return_value=None)
    @patch("main.song_id_random", return_value={"name": "No YT", "id": 1, "pvs": []})
    @patch("main.argparse.ArgumentParser")
    def test_dry_run_returns_done_on_no_pv(self, mock_argparse, mock_rand, mock_pv):
        from main import main
        mock_argparse.return_value.parse_args.return_value = MagicMock(platform="dry-run", date=None)
        result = main()
        assert result == "done"


class TestTwitterConfigSelection:
    @patch("main.twitterauth.localhost_login", return_value=MagicMock())
    @patch("main.cfg")
    @patch("main.time.sleep")
    @patch("main.post")
    @patch("main.txt_builder", return_value="test text")
    @patch("main.pvChecker", return_value="https://www.youtube.com/watch?v=abc")
    @patch("main.song_id_random", return_value={"name": "Melt", "id": 1, "pvs": []})
    @patch("main.argparse.ArgumentParser")
    def test_uses_localhost_login_by_default(
        self, mock_argparse, mock_rand, mock_pv, mock_txt, mock_post, mock_sleep, mock_cfg, mock_localhost
    ):
        from main import main
        mock_argparse.return_value.parse_args.return_value = MagicMock(platform="twitter")
        mock_cfg.get.return_value = "false"
        mock_sleep.side_effect = StopIteration
        with pytest.raises(StopIteration):
            main()
        mock_localhost.assert_called_once()

    @patch("main.twitterauth.flask_login", return_value=MagicMock())
    @patch("main.cfg")
    @patch("main.time.sleep")
    @patch("main.post")
    @patch("main.txt_builder", return_value="test text")
    @patch("main.pvChecker", return_value="https://www.youtube.com/watch?v=abc")
    @patch("main.song_id_random", return_value={"name": "Melt", "id": 1, "pvs": []})
    @patch("main.argparse.ArgumentParser")
    def test_uses_flask_login_when_configured(
        self, mock_argparse, mock_rand, mock_pv, mock_txt, mock_post, mock_sleep, mock_cfg, mock_flask
    ):
        from main import main
        mock_argparse.return_value.parse_args.return_value = MagicMock(platform="twitter")
        mock_cfg.get.return_value = "true"
        mock_sleep.side_effect = StopIteration
        with pytest.raises(StopIteration):
            main()
        mock_flask.assert_called_once()
