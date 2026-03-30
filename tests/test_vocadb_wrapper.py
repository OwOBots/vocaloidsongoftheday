import pytest
from unittest.mock import patch, MagicMock
import requests

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
        assert db.session.headers["Accept"] == "application/json"


class TestGet:
    @patch.object(requests.Session, "get")
    def test_get_merges_params(self, mock_get, db):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": 1, "name": "Test"}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        result = db._get("songs/1", fields="pvs")

        mock_get.assert_called_once_with(
            "https://vocadb.net/api/songs/1",
            params={"lang": "Default", "fields": "pvs"},
        )
        assert result == {"id": 1, "name": "Test"}

    @patch.object(requests.Session, "get")
    def test_get_raises_on_http_error(self, mock_get, db):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("404")
        mock_get.return_value = mock_resp

        with pytest.raises(requests.HTTPError):
            db._get("songs/999999")

    @patch.object(requests.Session, "get")
    def test_custom_lang_overrides_default(self, mock_get, db):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        db._get("songs", lang="English")

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["lang"] == "English"


class TestResourceMethods:
    @patch.object(VocaDB, "_get")
    def test_songs(self, mock_get, db):
        db.songs(query="miku")
        mock_get.assert_called_once_with("songs", query="miku")

    @patch.object(VocaDB, "_get_by_id")
    def test_song(self, mock_get, db):
        db.song(123, fields="pvs")
        mock_get.assert_called_once_with("songs", 123, fields="pvs")

    @patch.object(VocaDB, "_get")
    def test_top_rated_songs(self, mock_get, db):
        db.top_rated_songs(durationHours=24)
        mock_get.assert_called_once_with("songs/top-rated", durationHours=24)

    @patch.object(VocaDB, "_get")
    def test_highlighted_songs(self, mock_get, db):
        db.highlighted_songs()
        mock_get.assert_called_once_with("songs/highlighted")

    @patch.object(VocaDB, "_get")
    def test_artists(self, mock_get, db):
        db.artists(query="GUMI")
        mock_get.assert_called_once_with("artists", query="GUMI")

    @patch.object(VocaDB, "_get_by_id")
    def test_artist(self, mock_get, db):
        db.artist(1)
        mock_get.assert_called_once_with("artists", 1)

    @patch.object(VocaDB, "_get")
    def test_albums(self, mock_get, db):
        db.albums(query="EXIT TUNES")
        mock_get.assert_called_once_with("albums", query="EXIT TUNES")

    @patch.object(VocaDB, "_get_by_id")
    def test_album(self, mock_get, db):
        db.album(5)
        mock_get.assert_called_once_with("albums", 5)

    @patch.object(VocaDB, "_get")
    def test_tags(self, mock_get, db):
        db.tags()
        mock_get.assert_called_once_with("tags")

    @patch.object(VocaDB, "_get_by_id")
    def test_tag(self, mock_get, db):
        db.tag(10)
        mock_get.assert_called_once_with("tags", 10)

    @patch.object(VocaDB, "_get")
    def test_entries(self, mock_get, db):
        db.entries(query="world is mine")
        mock_get.assert_called_once_with("entries", query="world is mine")

    @patch.object(VocaDB, "_get")
    def test_events(self, mock_get, db):
        db.events()
        mock_get.assert_called_once_with("releaseEvents")

    @patch.object(VocaDB, "_get_by_id")
    def test_event(self, mock_get, db):
        db.event(42)
        mock_get.assert_called_once_with("releaseEvents", 42)

    @patch.object(VocaDB, "_get")
    def test_activity(self, mock_get, db):
        db.activity()
        mock_get.assert_called_once_with("activityEntries")


class TestGetById:
    @patch.object(VocaDB, "_get")
    def test_get_by_id_builds_path(self, mock_get, db):
        db._get_by_id("songs", 42, fields="pvs")
        mock_get.assert_called_once_with("songs/42", fields="pvs")
