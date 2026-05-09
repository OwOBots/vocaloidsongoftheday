import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx

from vocadb_wrapper import VocaDB


@pytest.fixture
def db():
    return VocaDB()


@pytest.fixture
def db_japanese():
    return VocaDB(lang="Japanese")


class TestVocaDBInit:
    def test_default_lang(self, db):
        assert db.default_params == {"lang": "Default"}

    def test_custom_lang(self, db_japanese):
        assert db_japanese.default_params == {"lang": "Japanese"}

    def test_session_headers(self, db):
        assert db.session.headers["accept"] == "application/json"


class TestGet:
    async def test_get_merges_params(self, db):
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": 1, "name": "Test"}
        mock_response.raise_for_status.return_value = None

        with patch.object(db.session, "get", new_callable=AsyncMock, return_value=mock_response) as mock_get:
            result = await db._get("songs/1", fields="pvs")

            mock_get.assert_called_once_with(
                "https://vocadb.net/api/songs/1",
                params={"lang": "Default", "fields": "pvs"},
                timeout=10,
            )
            assert result == {"id": 1, "name": "Test"}

    async def test_get_raises_on_http_error(self, db):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )

        with patch.object(db.session, "get", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(httpx.HTTPStatusError):
                await db._get("songs/999999")

    async def test_custom_lang_overrides_default(self, db):
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status.return_value = None

        with patch.object(db.session, "get", new_callable=AsyncMock, return_value=mock_response) as mock_get:
            await db._get("songs", lang="English")

            _, kwargs = mock_get.call_args
            assert kwargs["params"]["lang"] == "English"


class TestResourceMethods:
    async def test_songs(self, db):
        with patch.object(db, "_get", new_callable=AsyncMock) as mock_get:
            await db.songs(query="miku")
            mock_get.assert_called_once_with("songs", query="miku")

    async def test_song(self, db):
        with patch.object(db, "_get_by_id", new_callable=AsyncMock) as mock_get:
            await db.song(123, fields="pvs")
            mock_get.assert_called_once_with("songs", 123, fields="pvs")

    async def test_top_rated_songs(self, db):
        with patch.object(db, "_get", new_callable=AsyncMock) as mock_get:
            await db.top_rated_songs(durationHours=24)
            mock_get.assert_called_once_with("songs/top-rated", durationHours=24)

    async def test_highlighted_songs(self, db):
        with patch.object(db, "_get", new_callable=AsyncMock) as mock_get:
            await db.highlighted_songs()
            mock_get.assert_called_once_with("songs/highlighted")

    async def test_artists(self, db):
        with patch.object(db, "_get", new_callable=AsyncMock) as mock_get:
            await db.artists(query="GUMI")
            mock_get.assert_called_once_with("artists", query="GUMI")

    async def test_artist(self, db):
        with patch.object(db, "_get_by_id", new_callable=AsyncMock) as mock_get:
            await db.artist(1)
            mock_get.assert_called_once_with("artists", 1)

    async def test_albums(self, db):
        with patch.object(db, "_get", new_callable=AsyncMock) as mock_get:
            await db.albums(query="EXIT TUNES")
            mock_get.assert_called_once_with("albums", query="EXIT TUNES")

    async def test_album(self, db):
        with patch.object(db, "_get_by_id", new_callable=AsyncMock) as mock_get:
            await db.album(5)
            mock_get.assert_called_once_with("albums", 5)

    async def test_tags(self, db):
        with patch.object(db, "_get", new_callable=AsyncMock) as mock_get:
            await db.tags()
            mock_get.assert_called_once_with("tags")

    async def test_tag(self, db):
        with patch.object(db, "_get_by_id", new_callable=AsyncMock) as mock_get:
            await db.tag(10)
            mock_get.assert_called_once_with("tags", 10)

    async def test_entries(self, db):
        with patch.object(db, "_get", new_callable=AsyncMock) as mock_get:
            await db.entries(query="world is mine")
            mock_get.assert_called_once_with("entries", query="world is mine")

    async def test_events(self, db):
        with patch.object(db, "_get", new_callable=AsyncMock) as mock_get:
            await db.events()
            mock_get.assert_called_once_with("releaseEvents")

    async def test_event(self, db):
        with patch.object(db, "_get_by_id", new_callable=AsyncMock) as mock_get:
            await db.event(42)
            mock_get.assert_called_once_with("releaseEvents", 42)

    async def test_activity(self, db):
        with patch.object(db, "_get", new_callable=AsyncMock) as mock_get:
            await db.activity()
            mock_get.assert_called_once_with("activityEntries")


class TestGetById:
    async def test_get_by_id_builds_path(self, db):
        with patch.object(db, "_get", new_callable=AsyncMock) as mock_get:
            await db._get_by_id("songs", 42, fields="pvs")
            mock_get.assert_called_once_with("songs/42", fields="pvs")