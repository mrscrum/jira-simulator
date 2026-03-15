from unittest.mock import MagicMock, patch

import pytest

from app.integrations.alerting import AlertEvent, AlertingService


@pytest.fixture
def alerting():
    return AlertingService(
        email_from="sim@test.com",
        email_to="admin@test.com",
        ses_region="us-east-1",
    )


@pytest.fixture
def alerting_no_config():
    return AlertingService(email_from="", email_to="", ses_region="us-east-1")


class TestSendAlert:
    @pytest.mark.asyncio
    async def test_sends_jira_offline_email(self, alerting):
        with patch(
            "app.integrations.alerting.boto3"
        ) as mock_boto:
            mock_ses = MagicMock()
            mock_boto.client.return_value = mock_ses
            await alerting.send_alert(AlertEvent.JIRA_OFFLINE, {})
            mock_ses.send_email.assert_called_once()
            call_args = mock_ses.send_email.call_args
            assert "[Simulator] Jira connection lost" in str(
                call_args
            )

    @pytest.mark.asyncio
    async def test_sends_jira_recovered_email(self, alerting):
        with patch(
            "app.integrations.alerting.boto3"
        ) as mock_boto:
            mock_ses = MagicMock()
            mock_boto.client.return_value = mock_ses
            await alerting.send_alert(AlertEvent.JIRA_RECOVERED, {})
            call_args = mock_ses.send_email.call_args
            assert "[Simulator] Jira connection restored" in str(
                call_args
            )

    @pytest.mark.asyncio
    async def test_sends_engine_crash_email(self, alerting):
        with patch(
            "app.integrations.alerting.boto3"
        ) as mock_boto:
            mock_ses = MagicMock()
            mock_boto.client.return_value = mock_ses
            await alerting.send_alert(
                AlertEvent.ENGINE_CRASH, {"error": "OOM"}
            )
            call_args = mock_ses.send_email.call_args
            assert "Engine error" in str(call_args)

    @pytest.mark.asyncio
    async def test_sends_bootstrap_incomplete_email(self, alerting):
        with patch(
            "app.integrations.alerting.boto3"
        ) as mock_boto:
            mock_ses = MagicMock()
            mock_boto.client.return_value = mock_ses
            await alerting.send_alert(
                AlertEvent.BOOTSTRAP_INCOMPLETE,
                {"team": "Alpha Squad"},
            )
            call_args = mock_ses.send_email.call_args
            assert "Bootstrap warnings" in str(call_args)

    @pytest.mark.asyncio
    async def test_noop_when_no_config(self, alerting_no_config):
        with patch(
            "app.integrations.alerting.boto3"
        ) as mock_boto:
            await alerting_no_config.send_alert(
                AlertEvent.JIRA_OFFLINE, {}
            )
            mock_boto.client.assert_not_called()


class TestSendDailyDigest:
    @pytest.mark.asyncio
    async def test_sends_digest_email(self, alerting):
        digest_data = {
            "simulation_status": "Running",
            "active_teams": 2,
            "current_sprint": "Sprint 3 (day 5 of 14)",
            "team_summaries": [
                "Alpha: 12 in flight, 3 completed, 2 dysfunctions",
            ],
            "writes_completed": 847,
            "writes_failed": 3,
            "queue_depth": 12,
            "recent_dysfunctions": [
                "Low quality story x3",
                "Bug injection x5",
            ],
        }
        with patch(
            "app.integrations.alerting.boto3"
        ) as mock_boto:
            mock_ses = MagicMock()
            mock_boto.client.return_value = mock_ses
            await alerting.send_daily_digest(digest_data)
            mock_ses.send_email.assert_called_once()
            call_args = mock_ses.send_email.call_args
            assert "Daily activity digest" in str(call_args)

    @pytest.mark.asyncio
    async def test_digest_noop_when_no_config(self, alerting_no_config):
        with patch(
            "app.integrations.alerting.boto3"
        ) as mock_boto:
            await alerting_no_config.send_daily_digest({})
            mock_boto.client.assert_not_called()
