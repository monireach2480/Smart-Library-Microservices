from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.database import init_db
from app.core.observability import INSTANCE_ID, install
from app.routers import router


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Registration Service", version="1.0.0", lifespan=lifespan)
install(app, "registration-service")
app.include_router(router)


@app.get("/health", tags=["ops"])
def health():
    return {"status": "ok", "service": "registration-service", "instance": INSTANCE_ID}
