from contextlib import asynccontextmanager
from fastapi import FastAPI
from db.connection import init_db
from routes import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Personal Fin Hub API", lifespan=lifespan)

app.include_router(health.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "Personal Fin Hub API is running"}
