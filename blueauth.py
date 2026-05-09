import os
import sys

from atproto_client import AsyncClient
from dotenv import load_dotenv
from loguru import logger as LOG
load_dotenv()


def check_required_vars():
    required_vars = {'APU': 'Bluesky handle', 'AP': 'Bluesky app password'}
    for var, desc in required_vars.items():
        if var not in os.environ:
            LOG.critical(f"Error: {var} ({desc}) environment variable is not set")
            sys.exit(1)


# from https://github.com/MarshalX/atproto/discussions/167#discussioncomment-8579573
class RateLimitedClient(AsyncClient):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._limit = self._remaining = self._reset = None

    def get_rate_limit(self):
        return self._limit, self._remaining, self._reset

    async def _invoke(self, *args, **kwargs):
        response = await super()._invoke(*args, **kwargs)
        self._limit = response.headers.get('ratelimit-limit')
        self._remaining = response.headers.get('ratelimit-remaining')
        self._reset = response.headers.get('ratelimit-reset')
        return response


async def blue_login():
    check_required_vars()
    client = RateLimitedClient()
    await client.login(os.environ["APU"], os.environ["AP"])
    return client