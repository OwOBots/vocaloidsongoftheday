# vocadb api shit
import httpx
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
        self.session = httpx.AsyncClient(headers={"Accept": "application/json"})
        self.default_params = {"lang": lang}

    async def aclose(self):
        """Close the underlying HTTP session."""
        await self.session.aclose()

    async def _get(self, path: str, **params) -> dict | list:
        """Send a GET request and return the parsed JSON response."""
        url = f"{self.BASE_URL}/{path}"
        merged = {**self.default_params, **params}
        logger.debug("GET {} params={}", url, merged)
        response = await self.session.get(url, params=merged, timeout=10)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error("HTTP error for {}: {}", url, e)
            raise
        return response.json()

    async def _get_by_id(self, resource: str, entry_id: int, **params) -> dict:
        """Fetch a single entry by ID from the given resource."""
        return await self._get(f"{resource}/{entry_id}", **params)

    # Songs
    async def songs(self, **params) -> dict:
        """Search songs. Returns a paged result with items[]."""
        return await self._get("songs", **params)

    async def song(self, song_id: int, **params) -> dict:
        """Fetch a single song by ID."""
        return await self._get_by_id("songs", song_id, **params)

    async def top_rated_songs(self, **params) -> dict:
        """Get top-rated songs. Accepts durationHours, filterBy, vocalist, etc."""
        return await self._get("songs/top-rated", **params)

    async def highlighted_songs(self, **params) -> dict:
        """Get highlighted/featured songs."""
        return await self._get("songs/highlighted", **params)

    # Artists
    async def artists(self, **params) -> dict:
        """Search artists. Returns a paged result with items[]."""
        return await self._get("artists", **params)

    async def artist(self, artist_id: int, **params) -> dict:
        """Fetch a single artist by ID."""
        return await self._get_by_id("artists", artist_id, **params)

    # Albums
    async def albums(self, **params) -> dict:
        """Search albums. Returns a paged result with items[]."""
        return await self._get("albums", **params)

    async def album(self, album_id: int, **params) -> dict:
        """Fetch a single album by ID."""
        return await self._get_by_id("albums", album_id, **params)

    # Tags
    async def tags(self, **params) -> dict:
        """Search tags. Returns a paged result with items[]."""
        return await self._get("tags", **params)

    async def tag(self, tag_id: int, **params) -> dict:
        """Fetch a single tag by ID."""
        return await self._get_by_id("tags", tag_id, **params)

    # Entries (global search across all types)
    async def entries(self, **params) -> dict:
        """Search across all entry types (songs, artists, albums). Returns items[]."""
        return await self._get("entries", **params)

    # Release events
    async def events(self, **params) -> dict:
        """Search release events. Returns a paged result with items[]."""
        return await self._get("releaseEvents", **params)

    async def event(self, event_id: int, **params) -> dict:
        """Fetch a single release event by ID."""
        return await self._get_by_id("releaseEvents", event_id, **params)

    # Activity
    async def activity(self, **params) -> dict:
        """Get recent activity entries (edits, additions). Returns items[]."""
        return await self._get("activityEntries", **params)