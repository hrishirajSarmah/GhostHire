from fastapi import FastAPI
from routers.health import router as health_router

app = FastAPI(
    title="InterviewRAG API",
    version="0.4.0",
)

app.include_router(health_router)