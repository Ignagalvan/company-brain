from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.documents import router as documents_router
from src.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(documents_router)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
