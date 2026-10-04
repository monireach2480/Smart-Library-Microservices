from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_db
from app.routes import router


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Review Service", version="1.0.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health", tags=["ops"])
def health():
    return {"status": "ok", "service": "review-service"}
