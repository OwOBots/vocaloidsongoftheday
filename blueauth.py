import logging
import os
import sys

from atproto_client import Client
from dotenv import load_dotenv
from loguru import logger as LOG
load_dotenv()

#TODO: swap to the fork with a oauth version, the "main" version dont have oauth out the box
# i want to replace this with the oauth fork. but i fear it may break. the oauth version is here:
# https://github.com/MarshalX/atproto/pull/636

# simple helper to check that the required env vars are set before we try to log in to bluesky. this is separate from the twitter auth stuff since the bluesky client will just throw
# a generic error if the vars are missing, and this way we can log a more specific message about which var is missing instead of just "invalid credentials" or whatever

def ReqVars():
    required_vars = ['APU', 'AP']
    for var in required_vars:
        if var not in os.environ:
            LOG.critical(f"Error: {var} environment variable is not set")
            sys.exit(1)


# stolen from https://github.com/MarshalX/atproto/discussions/167#discussioncomment-8579573
class RateLimitedClient(Client):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._limit = self._remaining = self._reset = None

    def get_rate_limit(self):
        return self._limit, self._remaining, self._reset

    def _invoke(self, *args, **kwargs):
        response = super()._invoke(*args, **kwargs)

        self._limit = response.headers.get('ratelimit-limit')
        self._remaining = response.headers.get('ratelimit-remaining')
        self._reset = response.headers.get('ratelimit-reset')

        return response


def blue_login():
    client = RateLimitedClient()
    client.login(os.environ["APU"], os.environ["AP"])
    return client
