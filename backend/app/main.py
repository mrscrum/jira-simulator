from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routers.dependencies import router as deps_router
from app.api.routers.dysfunctions import router as dysf_router
from app.api.routers.jira_proxy import router as jira_router
from app.api.routers.members import router as members_router
from app.api.routers.simulation import router as sim_router
from app.api.routers.teams import router as teams_router
from app.api.routers.workflow import router as workflow_router
from app.database import create_engine_from_url, create_session_factory
from app.models.base import Base


@asynccontextmanager
async def lifespan(application: FastAPI):
    engine = create_engine_from_url("sqlite:///./data/simulator.db")
    Base.metadata.create_all(engine)
    application.state.session_factory = create_session_factory(engine)
    yield
    engine.dispose()


app = FastAPI(title="Jira Team Simulator", version="0.1.0", lifespan=lifespan)
app.include_router(teams_router)
app.include_router(members_router)
app.include_router(workflow_router)
app.include_router(dysf_router)
app.include_router(deps_router)
app.include_router(sim_router)
app.include_router(jira_router)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "stage": "2"}
