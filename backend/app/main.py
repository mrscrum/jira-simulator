from contextlib import asynccontextmanager

from fastapi import FastAPI

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


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "stage": "1"}
