import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routers.dependencies import router as deps_router
from app.api.routers.e2e_setup import router as e2e_router
from app.api.routers.jira_integration import router as jira_router
from app.api.routers.members import router as members_router
from app.api.routers.move_left import router as move_left_router
from app.api.routers.scheduled_events import router as schedule_router
from app.api.routers.simulation import router as sim_router
from app.api.routers.teams import router as teams_router
from app.api.routers.templates import router as templates_router
from app.api.routers.workflow import router as workflow_router
from app.config import get_settings
from app.database import create_engine_from_url, create_session_factory
from app.engine.event_auditor import EventAuditor
from app.engine.event_dispatcher import EventDispatcher
from app.engine.sim_clock import SimClock
from app.engine.simulation import SimulationEngine
from app.engine.sprint_cadence import SprintCadenceChecker
from app.integrations.alerting import AlertingService
from app.integrations.jira_bootstrapper import JiraBootstrapper
from app.integrations.jira_client import JiraClient
from app.integrations.jira_health import JiraHealthMonitor
from app.integrations.jira_write_queue import JiraWriteQueue
from app.integrations.scheduler import create_scheduler
from app.models.base import Base

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = get_settings()
    engine = create_engine_from_url(settings.database_url)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    application.state.session_factory = session_factory

    jira_client = JiraClient(
        settings.jira_base_url,
        settings.jira_email,
        settings.jira_api_token,
    )
    application.state.jira_client = jira_client

    alerting = AlertingService(
        settings.alert_email_from,
        settings.alert_email_to,
        settings.aws_ses_region,
    )

    health_monitor = JiraHealthMonitor(
        jira_client,
        on_status_change=_create_health_callback(alerting),
    )
    application.state.health_monitor = health_monitor

    write_queue = JiraWriteQueue(session_factory, jira_client, health_monitor)
    application.state.write_queue = write_queue

    sim_clock = SimClock(speed_multiplier=1.0)
    application.state.sim_clock = sim_clock

    simulation_engine = SimulationEngine(
        session_factory=session_factory,
        write_queue=write_queue,
        sim_clock=sim_clock,
    )
    application.state.simulation_engine = simulation_engine

    bootstrapper = JiraBootstrapper(
        jira_client, session_factory, alerting.send_alert
    )
    application.state.bootstrapper = bootstrapper

    event_dispatcher = EventDispatcher(session_factory, write_queue)
    application.state.event_dispatcher = event_dispatcher

    event_auditor = EventAuditor(session_factory, alerting)
    application.state.event_auditor = event_auditor

    cadence_checker = SprintCadenceChecker(session_factory, simulation_engine)
    application.state.cadence_checker = cadence_checker

    scheduler = create_scheduler(
        health_monitor, alerting, write_queue, simulation_engine,
        event_dispatcher=event_dispatcher,
        event_auditor=event_auditor,
        cadence_checker=cadence_checker,
    )
    scheduler.start()
    application.state.scheduler = scheduler
    logger.info("Scheduler started with health check and daily digest jobs")

    yield

    scheduler.shutdown(wait=False)
    await jira_client.close()
    engine.dispose()


def _create_health_callback(alerting: AlertingService):
    from app.integrations.alerting import AlertEvent

    async def on_status_change(old_status: str, new_status: str) -> None:
        if new_status == "OFFLINE":
            await alerting.send_alert(AlertEvent.JIRA_OFFLINE, {})
        elif new_status == "ONLINE" and old_status == "RECOVERING":
            await alerting.send_alert(AlertEvent.JIRA_RECOVERED, {})

    return on_status_change


app = FastAPI(title="Jira Team Simulator", version="0.1.0", lifespan=lifespan)
app.include_router(teams_router)
app.include_router(members_router)
app.include_router(workflow_router)
app.include_router(move_left_router)
app.include_router(deps_router)
app.include_router(sim_router)
app.include_router(jira_router)
app.include_router(e2e_router)
app.include_router(templates_router)
app.include_router(schedule_router)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "stage": "4"}
