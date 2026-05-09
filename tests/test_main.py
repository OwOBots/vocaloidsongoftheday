import datetime
import json
import time
import pytest
from unittest.mock import patch, MagicMock, AsyncMock, mock_open


class _BreakLoop(Exception):
    """Used to break out of the while True loop in tests (_BreakLoop can't be raised inside coroutines)."""
    pass


class TestRand:
    @patch("main.db")
    @patch("main.random.randint", return_value=500)
    async def test_rand_returns_song(self, mock_randint, mock_db):
        from main import song_id_random
        mock_db.song = AsyncMock(return_value={"name": "Melt", "id": 500})
        result = await song_id_random()
        assert result == {"name": "Melt", "id": 500}
        mock_db.song.assert_called_once_with(song_id=500, fields="pvs,Artists,Albums")

    @patch("main.db")
    @patch("main.random.randint", return_value=999999)
    async def test_rand_returns_none_when_no_song(self, mock_randint, mock_db):
        from main import song_id_random
        mock_db.song = AsyncMock(return_value=None)
        result = await song_id_random()
        assert result is None


class TestPvChecker:
    def test_returns_youtube_url(self):
        from main import pv_checker
        song = {
            "name": "World is Mine",
            "pvs": [
                {"url": "https://www.nicovideo.jp/watch/sm123"},
                {"url": "https://www.youtube.com/watch?v=abc123"},
            ],
        }
        assert pv_checker(song) == "https://www.youtube.com/watch?v=abc123"

    def test_returns_youtu_be_url(self):
        from main import pv_checker
        song = {
            "name": "Melt",
            "pvs": [{"url": "https://youtu.be/xyz789"}],
        }
        assert pv_checker(song) == "https://youtu.be/xyz789"

    def test_returns_none_when_no_pvs_key(self):
        from main import pv_checker
        song = {"name": "No PVs"}
        assert pv_checker(song) is None

    def test_returns_none_when_pvs_empty(self):
        from main import pv_checker
        song = {"name": "Empty PVs", "pvs": []}
        assert pv_checker(song) is None

    def test_returns_none_when_no_supported_pv(self):
        from main import pv_checker
        song = {
            "name": "Unsupported Only",
            "pvs": [{"url": "https://www.bilibili.com/video/BV123"}],
        }
        assert pv_checker(song) is None

    def test_returns_niconico_when_no_youtube(self):
        from main import pv_checker
        song = {
            "name": "NND Only",
            "pvs": [{"url": "https://www.nicovideo.jp/watch/sm456"}],
        }
        assert pv_checker(song) == "https://www.nicovideo.jp/watch/sm456"

    def test_prefers_youtube_over_niconico(self):
        from main import pv_checker
        song = {
            "name": "Both PVs",
            "pvs": [
                {"url": "https://www.nicovideo.jp/watch/sm123"},
                {"url": "https://www.youtube.com/watch?v=abc123"},
            ],
        }
        assert pv_checker(song) == "https://www.youtube.com/watch?v=abc123"

    def test_prefers_youtube_over_niconico_reversed_order(self):
        from main import pv_checker
        song = {
            "name": "Both PVs Reversed",
            "pvs": [
                {"url": "https://www.youtube.com/watch?v=abc123"},
                {"url": "https://www.nicovideo.jp/watch/sm123"},
            ],
        }
        assert pv_checker(song) == "https://www.youtube.com/watch?v=abc123"

    def test_accepts_nico_ms_short_url(self):
        from main import pv_checker
        song = {
            "name": "Short NND",
            "pvs": [{"url": "https://nico.ms/sm456"}],
        }
        assert pv_checker(song) == "https://nico.ms/sm456"

    def test_accepts_bare_nicovideo_domain(self):
        from main import pv_checker
        song = {
            "name": "Bare NND",
            "pvs": [{"url": "https://nicovideo.jp/watch/sm789"}],
        }
        assert pv_checker(song) == "https://nicovideo.jp/watch/sm789"

    def test_rejects_spoofed_niconico_domain(self):
        from main import pv_checker
        song = {
            "name": "Spoofed NND",
            "pvs": [
                {"url": "https://nicovideo.jp.evil.com/watch/sm123"},
                {"url": "https://notnicovideo.jp/watch/sm456"},
                {"url": "https://nico.ms.evil.com/sm789"},
            ],
        }
        assert pv_checker(song) is None

    def test_returns_first_youtube_match(self):
        from main import pv_checker
        song = {
            "name": "Multi YT",
            "pvs": [
                {"url": "https://www.youtube.com/watch?v=first"},
                {"url": "https://www.youtube.com/watch?v=second"},
            ],
        }
        assert pv_checker(song) == "https://www.youtube.com/watch?v=first"

    def test_rejects_spoofed_youtube_domain(self):
        from main import pv_checker
        song = {
            "name": "Spoofed",
            "pvs": [
                {"url": "https://notyoutube.com/watch?v=abc"},
                {"url": "https://youtube.com.evil.com/watch?v=abc"},
                {"url": "https://youtu.be.evil.com/xyz"},
            ],
        }
        assert pv_checker(song) is None


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


@patch("main.webhook")
@patch("main.cfg")
class TestPost:
    @patch("main.build_bsky_embed", new_callable=AsyncMock)
    @patch("main.client_utils")
    async def test_post_bluesky(self, mock_utils, mock_embed, mock_cfg, mock_webhook):
        from main import post
        mock_client = MagicMock()
        mock_client.send_post = AsyncMock()
        mock_tb = MagicMock()
        mock_utils.TextBuilder.return_value.text.return_value = mock_tb
        mock_embed.return_value = "embed_obj"

        await post(mock_client, "bluesky", "song of the day", "https://youtube.com/x")

        mock_client.send_post.assert_called_once_with(mock_tb, embed="embed_obj")

    async def test_post_twitter(self, mock_cfg, mock_webhook):
        from main import post
        mock_client = MagicMock()

        with patch("main.asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            await post(mock_client, "twitter", "song of the day", "https://youtube.com/x")
            mock_to_thread.assert_called_once_with(
                mock_client.create_tweet, text="song of the day\nhttps://youtube.com/x"
            )

    async def test_post_dry_run(self, mock_cfg, mock_webhook):
        from main import post
        await post(None, "dry-run", "song of the day", "https://youtube.com/x")

    async def test_post_unsupported_platform(self, mock_cfg, mock_webhook):
        from main import post
        with pytest.raises(ValueError, match="Unsupported platform"):
            await post(None, "mastodon", "song of the day", "https://youtube.com/x")


class TestBuildBskyEmbed:
    @patch("main.models")
    @patch("main.httpx.AsyncClient")
    async def test_build_embed(self, mock_client_cls, mock_models):
        from main import build_bsky_embed

        oembed_resp = MagicMock()
        oembed_resp.json.return_value = {
            "title": "Cool Song",
            "thumbnail_url": "https://img.youtube.com/vi/abc/hqdefault.jpg",
        }
        thumb_resp = MagicMock()
        thumb_resp.content = b"fakethumbdata"

        mock_http = AsyncMock()
        mock_http.get.side_effect = [oembed_resp, thumb_resp]
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_http

        mock_client = MagicMock()
        mock_client.upload_blob = AsyncMock()
        mock_client.upload_blob.return_value.blob = "blob_ref"

        result = await build_bsky_embed(mock_client, "https://www.youtube.com/watch?v=abc")

        assert mock_http.get.call_count == 2
        mock_client.upload_blob.assert_called_once_with(b"fakethumbdata")
        mock_models.AppBskyEmbedExternal.External.assert_called_once_with(
            uri="https://www.youtube.com/watch?v=abc",
            title="Cool Song",
            description="",
            thumb="blob_ref",
        )


class TestMainRetryLogic:
    """Tests for the retry and error handling logic in main()."""

    @patch("main.get_sleep_duration", return_value=21600)
    @patch("main.save_next_post_time")
    @patch("main.asyncio.sleep", new_callable=AsyncMock)
    @patch("main.post", new_callable=AsyncMock)
    @patch("main.txt_builder", return_value="test text")
    @patch("main.pv_checker", return_value="https://www.youtube.com/watch?v=abc")
    @patch("main.song_id_random", new_callable=AsyncMock, return_value={"name": "Melt", "id": 1, "pvs": []})
    @patch("main.blueauth.blue_login", new_callable=AsyncMock, return_value=MagicMock())
    @patch("main.argparse.ArgumentParser")
    async def test_posts_successfully_on_first_try(
        self, mock_argparse, mock_login, mock_rand, mock_pv, mock_txt, mock_post, mock_sleep,
        mock_save, mock_get_sleep
    ):
        from main import main

        mock_argparse.return_value.parse_args.return_value = MagicMock(platform="bluesky")
        # Break out of the while True loop after one cycle
        mock_sleep.side_effect = [_BreakLoop]
        with pytest.raises(_BreakLoop):
            await main()
        mock_post.assert_called_once()

    @patch("main.get_sleep_duration", return_value=21600)
    @patch("main.save_next_post_time")
    @patch("main.asyncio.sleep", new_callable=AsyncMock)
    @patch("main.post", new_callable=AsyncMock)
    @patch("main.txt_builder", return_value="test text")
    @patch("main.pv_checker", return_value="https://www.youtube.com/watch?v=abc")
    @patch("main.song_id_random", new_callable=AsyncMock)
    @patch("main.blueauth.blue_login", new_callable=AsyncMock, return_value=MagicMock())
    @patch("main.argparse.ArgumentParser")
    async def test_retries_on_api_exception(
        self, mock_argparse, mock_login, mock_rand, mock_pv, mock_txt, mock_post, mock_sleep,
        mock_save, mock_get_sleep
    ):
        from main import main

        mock_argparse.return_value.parse_args.return_value = MagicMock(platform="bluesky")
        # First call raises, second call succeeds
        mock_rand.side_effect = [
            Exception("VocaDB 404"),
            {"name": "Melt", "id": 1, "pvs": []},
        ]
        mock_sleep.side_effect = [None, _BreakLoop]  # first sleep is the 5s retry delay
        with pytest.raises(_BreakLoop):
            await main()
        assert mock_rand.call_count == 2
        mock_post.assert_called_once()

    @patch("main.get_sleep_duration", return_value=21600)
    @patch("main.save_next_post_time")
    @patch("main.asyncio.sleep", new_callable=AsyncMock)
    @patch("main.post", new_callable=AsyncMock)
    @patch("main.txt_builder", return_value="test text")
    @patch("main.pv_checker", return_value=None)
    @patch("main.song_id_random", new_callable=AsyncMock, return_value={"name": "No YT", "id": 1, "pvs": []})
    @patch("main.blueauth.blue_login", new_callable=AsyncMock, return_value=MagicMock())
    @patch("main.argparse.ArgumentParser")
    async def test_gives_up_after_max_attempts(
        self, mock_argparse, mock_login, mock_rand, mock_pv, mock_txt, mock_post, mock_sleep,
        mock_save, mock_get_sleep
    ):
        from main import main

        mock_argparse.return_value.parse_args.return_value = MagicMock(platform="bluesky")
        # The 6hr sleep after exhausting attempts, then break
        mock_sleep.side_effect = _BreakLoop
        with pytest.raises(_BreakLoop):
            await main()
        assert mock_rand.call_count == 50
        mock_post.assert_not_called()

    @patch("main.get_sleep_duration", return_value=21600)
    @patch("main.save_next_post_time")
    @patch("main.asyncio.sleep", new_callable=AsyncMock)
    @patch("main.post", new_callable=AsyncMock)
    @patch("main.txt_builder", return_value="test text")
    @patch("main.pv_checker", return_value="https://www.youtube.com/watch?v=abc")
    @patch("main.song_id_random", new_callable=AsyncMock, return_value={"name": "Melt", "id": 1, "pvs": []})
    @patch("main.blueauth.blue_login", new_callable=AsyncMock, return_value=MagicMock())
    @patch("main.argparse.ArgumentParser")
    async def test_retries_failed_posts(
        self, mock_argparse, mock_login, mock_rand, mock_pv, mock_txt, mock_post, mock_sleep,
        mock_save, mock_get_sleep
    ):
        from main import main

        mock_argparse.return_value.parse_args.return_value = MagicMock(platform="bluesky")
        # Post fails twice, then succeeds
        mock_post.side_effect = [Exception("network"), Exception("timeout"), None]
        mock_sleep.side_effect = [None, None, _BreakLoop]  # two backoff sleeps + final cycle sleep
        with pytest.raises(_BreakLoop):
            await main()
        assert mock_post.call_count == 3

    @patch("main.get_sleep_duration", return_value=21600)
    @patch("main.save_next_post_time")
    @patch("main.asyncio.sleep", new_callable=AsyncMock)
    @patch("main.post", new_callable=AsyncMock)
    @patch("main.txt_builder", return_value="test text")
    @patch("main.pv_checker", return_value="https://www.youtube.com/watch?v=abc")
    @patch("main.song_id_random", new_callable=AsyncMock, return_value={"name": "Melt", "id": 1, "pvs": []})
    @patch("main.blueauth.blue_login", new_callable=AsyncMock, return_value=MagicMock())
    @patch("main.argparse.ArgumentParser")
    async def test_gives_up_posting_after_5_failures(
        self, mock_argparse, mock_login, mock_rand, mock_pv, mock_txt, mock_post, mock_sleep,
        mock_save, mock_get_sleep
    ):
        from main import main

        mock_argparse.return_value.parse_args.return_value = MagicMock(platform="bluesky")
        mock_post.side_effect = Exception("always fails")
        # 5 backoff sleeps + final cycle sleep, then break
        mock_sleep.side_effect = [None, None, None, None, None, _BreakLoop]
        with pytest.raises(_BreakLoop):
            await main()
        assert mock_post.call_count == 5


class TestMainDryRun:
    @patch("main.post", new_callable=AsyncMock)
    @patch("main.txt_builder", return_value="test text")
    @patch("main.pv_checker", return_value="https://www.youtube.com/watch?v=abc")
    @patch("main.song_id_random", new_callable=AsyncMock, return_value={"name": "Melt", "id": 1, "pvs": []})
    @patch("main.argparse.ArgumentParser")
    async def test_dry_run_exits_with_done(self, mock_argparse, mock_rand, mock_pv, mock_txt, mock_post):
        from main import main
        mock_argparse.return_value.parse_args.return_value = MagicMock(platform="dry-run", date=None)
        result = await main()
        assert result == "done"
        mock_post.assert_called_once_with(None, "dry-run", "test text", "https://www.youtube.com/watch?v=abc")

    @patch("main.post", new_callable=AsyncMock)
    @patch("main.txt_builder", return_value="test text")
    @patch("main.pv_checker", return_value="https://www.youtube.com/watch?v=abc")
    @patch("main.song_id_random", new_callable=AsyncMock, return_value={"name": "Melt", "id": 1, "pvs": []})
    @patch("main.argparse.ArgumentParser")
    async def test_dry_run_date_override(self, mock_argparse, mock_rand, mock_pv, mock_txt, mock_post):
        from main import main
        mock_argparse.return_value.parse_args.return_value = MagicMock(platform="dry-run", date="02-24")
        await main()
        mock_txt.assert_called_once()
        _, kwargs = mock_txt.call_args
        assert kwargs["override_date"] == datetime.date(2000, 2, 24)

    @patch("main.pv_checker", return_value=None)
    @patch("main.song_id_random", new_callable=AsyncMock, return_value={"name": "No YT", "id": 1, "pvs": []})
    @patch("main.argparse.ArgumentParser")
    async def test_dry_run_returns_done_on_no_pv(self, mock_argparse, mock_rand, mock_pv):
        from main import main
        mock_argparse.return_value.parse_args.return_value = MagicMock(platform="dry-run", date=None)
        result = await main()
        assert result == "done"


class TestTwitterConfigSelection:
    @patch("main.get_sleep_duration", return_value=21600)
    @patch("main.save_next_post_time")
    @patch("main.twitterauth.localhost_login", return_value=MagicMock())
    @patch("main.cfg")
    @patch("main.asyncio.sleep", new_callable=AsyncMock)
    @patch("main.post", new_callable=AsyncMock)
    @patch("main.txt_builder", return_value="test text")
    @patch("main.pv_checker", return_value="https://www.youtube.com/watch?v=abc")
    @patch("main.song_id_random", new_callable=AsyncMock, return_value={"name": "Melt", "id": 1, "pvs": []})
    @patch("main.argparse.ArgumentParser")
    async def test_uses_localhost_login_by_default(
        self, mock_argparse, mock_rand, mock_pv, mock_txt, mock_post, mock_sleep, mock_cfg, mock_localhost,
        mock_save, mock_get_sleep
    ):
        from main import main
        mock_argparse.return_value.parse_args.return_value = MagicMock(platform="twitter")
        mock_cfg.get.return_value = "false"
        mock_sleep.side_effect = _BreakLoop
        with pytest.raises(_BreakLoop):
            await main()
        mock_localhost.assert_called_once()

    @patch("main.get_sleep_duration", return_value=21600)
    @patch("main.save_next_post_time")
    @patch("main.twitterauth.flask_login", return_value=MagicMock())
    @patch("main.cfg")
    @patch("main.asyncio.sleep", new_callable=AsyncMock)
    @patch("main.post", new_callable=AsyncMock)
    @patch("main.txt_builder", return_value="test text")
    @patch("main.pv_checker", return_value="https://www.youtube.com/watch?v=abc")
    @patch("main.song_id_random", new_callable=AsyncMock, return_value={"name": "Melt", "id": 1, "pvs": []})
    @patch("main.argparse.ArgumentParser")
    async def test_uses_flask_login_when_configured(
        self, mock_argparse, mock_rand, mock_pv, mock_txt, mock_post, mock_sleep, mock_cfg, mock_flask,
        mock_save, mock_get_sleep
    ):
        from main import main
        mock_argparse.return_value.parse_args.return_value = MagicMock(platform="twitter")
        mock_cfg.get.return_value = "true"
        mock_sleep.side_effect = _BreakLoop
        with pytest.raises(_BreakLoop):
            await main()
        mock_flask.assert_called_once()


class TestTimerCache:
    @patch("main.TIMER_CACHE_FILE", "test_timer_cache.json")
    @patch("main.CYCLE_INTERVAL", 21600)
    @patch("main.time.time", return_value=1000000.0)
    def test_save_next_post_time_writes_valid_json(self, mock_time):
        from main import save_next_post_time
        m = mock_open()
        with patch("builtins.open", m):
            save_next_post_time()
        m.assert_called_once_with("test_timer_cache.json", "w")
        written = "".join(call.args[0] for call in m().write.call_args_list)
        data = json.loads(written)
        assert data == {"next_post_utc": 1000000.0 + 21600}

    @patch("main.TIMER_CACHE_FILE", "test_timer_cache.json")
    @patch("main.CYCLE_INTERVAL", 21600)
    @patch("main.time.time", return_value=1000000.0)
    def test_get_sleep_duration_returns_remaining_time(self, mock_time):
        from main import get_sleep_duration
        # next post is 10000 seconds from now
        cache_data = json.dumps({"next_post_utc": 1010000.0})
        with patch("builtins.open", mock_open(read_data=cache_data)):
            result = get_sleep_duration()
        assert result == 10000.0

    @patch("main.TIMER_CACHE_FILE", "test_timer_cache.json")
    @patch("main.CYCLE_INTERVAL", 21600)
    def test_get_sleep_duration_returns_cycle_interval_when_file_missing(self):
        from main import get_sleep_duration
        with patch("builtins.open", side_effect=FileNotFoundError):
            result = get_sleep_duration()
        assert result == 21600

    @patch("main.TIMER_CACHE_FILE", "test_timer_cache.json")
    @patch("main.CYCLE_INTERVAL", 21600)
    def test_get_sleep_duration_returns_cycle_interval_when_file_corrupt(self):
        from main import get_sleep_duration
        with patch("builtins.open", mock_open(read_data="not valid json{{")):
            result = get_sleep_duration()
        assert result == 21600

    @patch("main.TIMER_CACHE_FILE", "test_timer_cache.json")
    @patch("main.CYCLE_INTERVAL", 21600)
    @patch("main.time.time", return_value=1000000.0)
    def test_get_sleep_duration_clamps_to_zero_when_past(self, mock_time):
        from main import get_sleep_duration
        # next post was 500 seconds ago
        cache_data = json.dumps({"next_post_utc": 999500.0})
        with patch("builtins.open", mock_open(read_data=cache_data)):
            result = get_sleep_duration()
        assert result == 0

    @patch("main.TIMER_CACHE_FILE", "test_timer_cache.json")
    @patch("main.CYCLE_INTERVAL", 21600)
    @patch("main.time.time", return_value=1000000.0)
    def test_get_sleep_duration_clamps_to_cycle_interval_when_too_far(self, mock_time):
        from main import get_sleep_duration
        # next post is 50000 seconds from now (more than CYCLE_INTERVAL)
        cache_data = json.dumps({"next_post_utc": 1050000.0})
        with patch("builtins.open", mock_open(read_data=cache_data)):
            result = get_sleep_duration()
        assert result == 21600