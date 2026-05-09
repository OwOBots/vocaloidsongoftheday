import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class Testcheck_required_vars:
    @patch.dict("os.environ", {"APU": "user", "AP": "pass"}, clear=False)
    def test_passes_when_vars_set(self):
        from blueauth import check_required_vars
        check_required_vars()  # should not raise or exit

    @patch.dict("os.environ", {}, clear=True)
    def test_exits_when_apu_missing(self):
        from blueauth import check_required_vars
        with pytest.raises(SystemExit):
            check_required_vars()

    @patch.dict("os.environ", {"APU": "user"}, clear=True)
    def test_exits_when_ap_missing(self):
        from blueauth import check_required_vars
        with pytest.raises(SystemExit):
            check_required_vars()


class TestRateLimitedClient:
    def test_initial_rate_limit_is_none(self):
        from blueauth import RateLimitedClient
        client = RateLimitedClient()
        assert client.get_rate_limit() == (None, None, None)

    @patch("blueauth.AsyncClient._invoke", new_callable=AsyncMock)
    async def test_invoke_captures_headers(self, mock_invoke):
        from blueauth import RateLimitedClient
        mock_resp = MagicMock()
        mock_resp.headers = {
            "ratelimit-limit": "100",
            "ratelimit-remaining": "99",
            "ratelimit-reset": "1700000000",
        }
        mock_invoke.return_value = mock_resp

        client = RateLimitedClient()
        await client._invoke("some.method")

        assert client.get_rate_limit() == ("100", "99", "1700000000")


class TestBlueLogin:
    @patch("blueauth.RateLimitedClient")
    @patch.dict("os.environ", {"APU": "testuser", "AP": "testpass"})
    async def test_blue_login(self, mock_client_cls):
        from blueauth import blue_login
        mock_instance = MagicMock()
        mock_instance.login = AsyncMock()
        mock_client_cls.return_value = mock_instance

        result = await blue_login()

        mock_instance.login.assert_called_once_with("testuser", "testpass")
        assert result is mock_instance