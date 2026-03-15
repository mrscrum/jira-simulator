from fastapi import FastAPI

app = FastAPI(title="Jira Team Simulator", version="0.1.0")


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "stage": "0"}
