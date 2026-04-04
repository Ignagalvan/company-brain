from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.ask import router as ask_router
from src.api.conversations import router as conversations_router
from src.api.documents import router as documents_router
from src.api.internal import router as internal_router
from src.api.messages import router as messages_router
from src.api.retrieval import router as retrieval_router
from src.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)
app.include_router(retrieval_router)
app.include_router(ask_router)
app.include_router(conversations_router)
app.include_router(messages_router)
app.include_router(internal_router)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
