import asyncio
import enum
import logging

import boto3

logger = logging.getLogger(__name__)


class AlertEvent(enum.StrEnum):
    JIRA_OFFLINE = "JIRA_OFFLINE"
    JIRA_RECOVERED = "JIRA_RECOVERED"
    ENGINE_CRASH = "ENGINE_CRASH"
    BOOTSTRAP_INCOMPLETE = "BOOTSTRAP_INCOMPLETE"
    DAILY_DIGEST = "DAILY_DIGEST"
    EVENT_DISPATCH_FAILED = "EVENT_DISPATCH_FAILED"
    EVENT_AUDIT_TIMEOUT = "EVENT_AUDIT_TIMEOUT"


SUBJECT_MAP = {
    AlertEvent.JIRA_OFFLINE: "[Simulator] Jira connection lost",
    AlertEvent.JIRA_RECOVERED: "[Simulator] Jira connection restored",
    AlertEvent.ENGINE_CRASH: "[Simulator] Engine error — simulation paused",
    AlertEvent.BOOTSTRAP_INCOMPLETE: "[Simulator] Bootstrap warnings for {team}",
    AlertEvent.DAILY_DIGEST: "[Simulator] Daily activity digest",
    AlertEvent.EVENT_DISPATCH_FAILED: "[Simulator] Scheduled event failed — {event_type}",
    AlertEvent.EVENT_AUDIT_TIMEOUT: "[Simulator] Scheduled event timed out — {event_type}",
}


class AlertingService:
    def __init__(self, email_from: str, email_to: str, ses_region: str):
        self._email_from = email_from
        self._email_to = email_to
        self._ses_region = ses_region

    def _is_configured(self) -> bool:
        return bool(self._email_from and self._email_to)

    async def send_alert(self, event: AlertEvent, context: dict) -> None:
        if not self._is_configured():
            logger.warning("Alerting not configured, skipping %s", event)
            return

        subject = self._build_subject(event, context)
        body = self._build_body(event, context)
        await self._send_email(subject, body)

    async def send_daily_digest(self, digest_data: dict) -> None:
        if not self._is_configured():
            logger.warning("Alerting not configured, skipping digest")
            return

        subject = SUBJECT_MAP[AlertEvent.DAILY_DIGEST]
        body = self._format_digest(digest_data)
        await self._send_email(subject, body)

    def _build_subject(self, event: AlertEvent, context: dict) -> str:
        template = SUBJECT_MAP[event]
        return template.format(**context) if "{" in template else template

    def _build_body(self, event: AlertEvent, context: dict) -> str:
        if event == AlertEvent.JIRA_OFFLINE:
            return "Jira connectivity lost. Writes are being queued."
        if event == AlertEvent.JIRA_RECOVERED:
            return "Jira connectivity restored. Recovery writes in progress."
        if event == AlertEvent.ENGINE_CRASH:
            error = context.get("error", "Unknown error")
            return f"Simulation engine encountered an error: {error}"
        if event == AlertEvent.BOOTSTRAP_INCOMPLETE:
            team = context.get("team", "Unknown")
            return f"Bootstrap for team '{team}' completed with warnings."
        if event == AlertEvent.EVENT_DISPATCH_FAILED:
            event_id = context.get("event_id", "?")
            reason = context.get("reason", "Unknown")
            return f"Scheduled event {event_id} failed to write to Jira: {reason}"
        if event == AlertEvent.EVENT_AUDIT_TIMEOUT:
            event_id = context.get("event_id", "?")
            return f"Scheduled event {event_id} was not processed within the timeout window."
        return ""

    def _format_digest(self, data: dict) -> str:
        lines = [
            f"Simulation status: {data.get('simulation_status', 'N/A')}",
            f"Active teams: {data.get('active_teams', 0)}",
            f"Current sprint: {data.get('current_sprint', 'N/A')}",
            "",
        ]
        for summary in data.get("team_summaries", []):
            lines.append(f"  {summary}")
        lines.append("")
        lines.append(f"Writes completed: {data.get('writes_completed', 0)}")
        lines.append(f"Writes failed: {data.get('writes_failed', 0)}")
        lines.append(f"Queue depth: {data.get('queue_depth', 0)}")
        lines.append("")
        for dysfunction in data.get("recent_dysfunctions", []):
            lines.append(f"  {dysfunction}")
        return "\n".join(lines)

    async def _send_email(self, subject: str, body: str) -> None:
        await asyncio.to_thread(self._send_email_sync, subject, body)

    def _send_email_sync(self, subject: str, body: str) -> None:
        ses = boto3.client("ses", region_name=self._ses_region)
        ses.send_email(
            Source=self._email_from,
            Destination={"ToAddresses": [self._email_to]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": body, "Charset": "UTF-8"},
                },
            },
        )
        logger.info("Alert sent: %s", subject)
