# vocadb api shit
import requests
from loguru import logger

# this is a wrapper. i want to make a standalone version of this wrapper for pip. but i dont want that burden. so i'm just putting it here for now. it's not really worth testing since it's mostly just plumbing to the API, and the API is well-documented and stable.
# https://vocadb.net/swagger/index.html
# if i were to make a standalone package, i'd want to add some caching and rate limit handling, but for now this is fine. the API is pretty fast and i won't be making that many requests.
class VocaDB:
    """Client for the VocaDB REST API (https://vocadb.net/api).

    All resource methods accept arbitrary **params which are forwarded as
    query string parameters. Common ones include:
      query          – search string
      maxResults     – page size (default 10, max 50)
      start          – pagination offset
      getTotalCount  – include total count in response
      fields         – comma-separated optional fields to include
      lang           – content language preference (overrides instance default)
      nameMatchMode  – Auto | Partial | StartsWith | Exact
      sort           – resource-specific sort rule
    """

    BASE_URL = "https://vocadb.net/api"

    def __init__(self, lang: str = "Default"):
        """Create a VocaDB client.

        Args:
            lang: Default ContentLanguagePreference for all requests.
                  One of Default, Japanese, Romaji, English.
        """
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        self.default_params = {"lang": lang}

    def _get(self, path: str, **params) -> dict | list:
        """Send a GET request and return the parsed JSON response."""
        url = f"{self.BASE_URL}/{path}"
        merged = {**self.default_params, **params}
        logger.debug("GET {} params={}", url, merged)
        response = self.session.get(url, params=merged)
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            logger.error("HTTP error for {}: {}", url, e)
            raise
        return response.json()

    def _get_by_id(self, resource: str, entry_id: int, **params) -> dict:
        """Fetch a single entry by ID from the given resource."""
        return self._get(f"{resource}/{entry_id}", **params)

    # Songs
    def songs(self, **params) -> dict:
        """Search songs. Returns a paged result with items[]."""
        return self._get("songs", **params)

    def song(self, song_id: int, **params) -> dict:
        """Fetch a single song by ID."""
        return self._get_by_id("songs", song_id, **params)

    def top_rated_songs(self, **params) -> dict:
        """Get top-rated songs. Accepts durationHours, filterBy, vocalist, etc."""
        return self._get("songs/top-rated", **params)

    def highlighted_songs(self, **params) -> dict:
        """Get highlighted/featured songs."""
        return self._get("songs/highlighted", **params)

    # Artists
    def artists(self, **params) -> dict:
        """Search artists. Returns a paged result with items[]."""
        return self._get("artists", **params)

    def artist(self, artist_id: int, **params) -> dict:
        """Fetch a single artist by ID."""
        return self._get_by_id("artists", artist_id, **params)

    # Albums
    def albums(self, **params) -> dict:
        """Search albums. Returns a paged result with items[]."""
        return self._get("albums", **params)

    def album(self, album_id: int, **params) -> dict:
        """Fetch a single album by ID."""
        return self._get_by_id("albums", album_id, **params)

    # Tags
    def tags(self, **params) -> dict:
        """Search tags. Returns a paged result with items[]."""
        return self._get("tags", **params)

    def tag(self, tag_id: int, **params) -> dict:
        """Fetch a single tag by ID."""
        return self._get_by_id("tags", tag_id, **params)

    # Entries (global search across all types)
    def entries(self, **params) -> dict:
        """Search across all entry types (songs, artists, albums). Returns items[]."""
        return self._get("entries", **params)

    # Release events
    def events(self, **params) -> dict:
        """Search release events. Returns a paged result with items[]."""
        return self._get("releaseEvents", **params)

    def event(self, event_id: int, **params) -> dict:
        """Fetch a single release event by ID."""
        return self._get_by_id("releaseEvents", event_id, **params)

    # Activity
    def activity(self, **params) -> dict:
        """Get recent activity entries (edits, additions). Returns items[]."""
        return self._get("activityEntries", **params)
