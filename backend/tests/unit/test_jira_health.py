from unittest.mock import AsyncMock

import pytest

from app.integrations.jira_health import JiraHealthMonitor


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.ping = AsyncMock(return_value=True)
    return client


@pytest.fixture
def monitor(mock_client):
    return JiraHealthMonitor(mock_client)


class TestInitialState:
    def test_starts_online(self, monitor):
        assert monitor.status == "ONLINE"

    def test_zero_consecutive_failures(self, monitor):
        assert monitor.consecutive_failures == 0

    def test_no_outage_start(self, monitor):
        assert monitor.outage_start is None


class TestOnlineStaysOnline:
    @pytest.mark.asyncio
    async def test_successful_ping_stays_online(self, monitor, mock_client):
        mock_client.ping.return_value = True
        await monitor.check()
        assert monitor.status == "ONLINE"
        assert monitor.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_updates_last_checked(self, monitor, mock_client):
        mock_client.ping.return_value = True
        await monitor.check()
        assert monitor.last_checked is not None

    @pytest.mark.asyncio
    async def test_updates_last_online(self, monitor, mock_client):
        mock_client.ping.return_value = True
        await monitor.check()
        assert monitor.last_online is not None


class TestOnlineToOffline:
    @pytest.mark.asyncio
    async def test_one_failure_stays_online(self, monitor, mock_client):
        mock_client.ping.return_value = False
        await monitor.check()
        assert monitor.status == "ONLINE"
        assert monitor.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_two_failures_goes_offline(self, monitor, mock_client):
        mock_client.ping.return_value = False
        await monitor.check()
        await monitor.check()
        assert monitor.status == "OFFLINE"
        assert monitor.consecutive_failures == 2

    @pytest.mark.asyncio
    async def test_outage_start_set_on_offline(self, monitor, mock_client):
        mock_client.ping.return_value = False
        await monitor.check()
        await monitor.check()
        assert monitor.outage_start is not None


class TestOfflineToRecovering:
    @pytest.mark.asyncio
    async def test_ping_success_while_offline_goes_recovering(
        self, monitor, mock_client
    ):
        mock_client.ping.return_value = False
        await monitor.check()
        await monitor.check()
        assert monitor.status == "OFFLINE"

        mock_client.ping.return_value = True
        await monitor.check()
        assert monitor.status == "RECOVERING"

    @pytest.mark.asyncio
    async def test_consecutive_failures_reset_on_recovering(
        self, monitor, mock_client
    ):
        mock_client.ping.return_value = False
        await monitor.check()
        await monitor.check()

        mock_client.ping.return_value = True
        await monitor.check()
        assert monitor.consecutive_failures == 0


class TestRecoveringToOnline:
    @pytest.mark.asyncio
    async def test_mark_recovery_complete(self, monitor, mock_client):
        mock_client.ping.return_value = False
        await monitor.check()
        await monitor.check()

        mock_client.ping.return_value = True
        await monitor.check()
        assert monitor.status == "RECOVERING"

        monitor.mark_recovery_complete()
        assert monitor.status == "ONLINE"
        assert monitor.outage_start is None


class TestCallback:
    @pytest.mark.asyncio
    async def test_callback_on_offline(self, mock_client):
        callback = AsyncMock()
        monitor = JiraHealthMonitor(mock_client, on_status_change=callback)
        mock_client.ping.return_value = False
        await monitor.check()
        await monitor.check()
        callback.assert_awaited_once_with("ONLINE", "OFFLINE")

    @pytest.mark.asyncio
    async def test_callback_on_recovering(self, mock_client):
        callback = AsyncMock()
        monitor = JiraHealthMonitor(mock_client, on_status_change=callback)
        mock_client.ping.return_value = False
        await monitor.check()
        await monitor.check()
        callback.reset_mock()

        mock_client.ping.return_value = True
        await monitor.check()
        callback.assert_awaited_once_with("OFFLINE", "RECOVERING")

    @pytest.mark.asyncio
    async def test_no_callback_when_status_unchanged(self, mock_client):
        callback = AsyncMock()
        monitor = JiraHealthMonitor(mock_client, on_status_change=callback)
        mock_client.ping.return_value = True
        await monitor.check()
        callback.assert_not_awaited()
