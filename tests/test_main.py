import pytest
from unittest.mock import patch, MagicMock


class TestRand:
    @patch("main.db")
    @patch("main.random.randint", return_value=500)
    def test_rand_returns_song(self, mock_randint, mock_db):
        from main import rand
        mock_db.song.return_value = {"name": "Melt", "id": 500}
        result = rand()
        assert result == {"name": "Melt", "id": 500}
        mock_db.song.assert_called_once_with(song_id=500, fields="pvs")

    @patch("main.db")
    @patch("main.random.randint", return_value=999999)
    def test_rand_returns_none_when_no_song(self, mock_randint, mock_db):
        from main import rand
        mock_db.song.return_value = None
        result = rand()
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
    @patch("main.pvChecker", return_value="https://www.youtube.com/watch?v=abc")
    @patch("main.rand", return_value={"name": "Melt", "id": 1, "pvs": []})
    @patch("main.blueauth.blue_login", return_value=MagicMock())
    @patch("main.argparse.ArgumentParser")
    def test_posts_successfully_on_first_try(
        self, mock_argparse, mock_login, mock_rand, mock_pv, mock_post, mock_sleep
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
    @patch("main.pvChecker", return_value="https://www.youtube.com/watch?v=abc")
    @patch("main.rand")
    @patch("main.blueauth.blue_login", return_value=MagicMock())
    @patch("main.argparse.ArgumentParser")
    def test_retries_on_api_exception(
        self, mock_argparse, mock_login, mock_rand, mock_pv, mock_post, mock_sleep
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
    @patch("main.pvChecker", return_value=None)
    @patch("main.rand", return_value={"name": "No YT", "id": 1, "pvs": []})
    @patch("main.blueauth.blue_login", return_value=MagicMock())
    @patch("main.argparse.ArgumentParser")
    def test_gives_up_after_max_attempts(
        self, mock_argparse, mock_login, mock_rand, mock_pv, mock_post, mock_sleep
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
    @patch("main.pvChecker", return_value="https://www.youtube.com/watch?v=abc")
    @patch("main.rand", return_value={"name": "Melt", "id": 1, "pvs": []})
    @patch("main.blueauth.blue_login", return_value=MagicMock())
    @patch("main.argparse.ArgumentParser")
    def test_retries_failed_posts(
        self, mock_argparse, mock_login, mock_rand, mock_pv, mock_post, mock_sleep
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
    @patch("main.pvChecker", return_value="https://www.youtube.com/watch?v=abc")
    @patch("main.rand", return_value={"name": "Melt", "id": 1, "pvs": []})
    @patch("main.blueauth.blue_login", return_value=MagicMock())
    @patch("main.argparse.ArgumentParser")
    def test_gives_up_posting_after_5_failures(
        self, mock_argparse, mock_login, mock_rand, mock_pv, mock_post, mock_sleep
    ):
        from main import main

        mock_argparse.return_value.parse_args.return_value = MagicMock(platform="bluesky")
        mock_post.side_effect = Exception("always fails")
        # 5 backoff sleeps + final cycle sleep, then break
        mock_sleep.side_effect = [None, None, None, None, None, StopIteration]
        with pytest.raises(StopIteration):
            main()
        assert mock_post.call_count == 5
