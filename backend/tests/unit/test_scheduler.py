from unittest.mock import MagicMock

from app.integrations.scheduler import create_scheduler


class TestCreateScheduler:
    def test_returns_scheduler_instance(self):
        health_monitor = MagicMock()
        alerting = MagicMock()
        write_queue = MagicMock()
        scheduler = create_scheduler(health_monitor, alerting, write_queue)
        assert scheduler is not None

    def test_registers_health_check_job(self):
        health_monitor = MagicMock()
        alerting = MagicMock()
        write_queue = MagicMock()
        scheduler = create_scheduler(health_monitor, alerting, write_queue)
        job_ids = [job.id for job in scheduler.get_jobs()]
        assert "jira_health_check" in job_ids

    def test_registers_daily_digest_job(self):
        health_monitor = MagicMock()
        alerting = MagicMock()
        write_queue = MagicMock()
        scheduler = create_scheduler(health_monitor, alerting, write_queue)
        job_ids = [job.id for job in scheduler.get_jobs()]
        assert "daily_digest" in job_ids
