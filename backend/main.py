import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI
from db.connection import init_db
from routes import analytics, health, market, currencies, entities, fiscal_exemptions, market_assets, portfolio_assets, prices, schedules, transactions, transaction_fees, transaction_taxes, transfers, balance_snapshots
from scheduler.scheduler import init_scheduler, shutdown_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        init_scheduler()
    except Exception as e:
        logger.warning("Scheduler init skipped: %s", e)
    yield
    shutdown_scheduler()


app = FastAPI(title="Personal Fin Hub API", lifespan=lifespan)

app.include_router(health.router, prefix="/api/v1")
app.include_router(market.router, prefix="/api/v1")
app.include_router(currencies.router, prefix="/api/v1")
app.include_router(entities.router, prefix="/api/v1")
app.include_router(fiscal_exemptions.router, prefix="/api/v1")
app.include_router(market_assets.router, prefix="/api/v1")
app.include_router(portfolio_assets.router, prefix="/api/v1")
app.include_router(prices.router, prefix="/api/v1")
app.include_router(schedules.router, prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")
app.include_router(transaction_fees.router, prefix="/api/v1")
app.include_router(transaction_taxes.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(transfers.router, prefix="/api/v1")
app.include_router(balance_snapshots.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "Personal Fin Hub API is running"}
