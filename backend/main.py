import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import Depends, FastAPI

from db import queries
from db.connection import _table_exists, get_db, init_db
from routes import (
    analytics,
    balance_snapshots,
    currencies,
    entities,
    fiscal_exemptions,
    health,
    market,
    market_assets,
    portfolio_assets,
    prices,
    profiles,
    schedules,
    stock_splits,
    transaction_fees,
    transaction_taxes,
    transactions,
    transfers,
)
from routes.deps import require_profile
from scheduler.scheduler import catch_up_missed_fires, init_scheduler, shutdown_scheduler
from services.backup_svc import migration_backups, startup_daily_backup
from services.logging_config import RequestIdMiddleware, setup

setup()
logger = logging.getLogger(__name__)

SEED_CODES = ["USD", "EUR", "JPY"]


def seed_currencies():
    conn = get_db()
    existing = conn.execute("SELECT COUNT(*) FROM currencies").fetchone()[0]
    if existing > 0:
        conn.close()
        return
    ts = datetime.now(UTC)
    for code in SEED_CODES:
        if not queries.code_exists(conn, code):
            queries.create_self_rate(conn, code, ts)
    conn.commit()
    conn.close()
    logger.info("Seeded currencies: %s", ", ".join(SEED_CODES))


def seed_default_profile():
    conn = get_db()
    if _table_exists(conn, "profiles"):
        has_profile = conn.execute("SELECT 1 FROM profiles LIMIT 1").fetchone()
        if not has_profile:
            conn.execute("INSERT INTO profiles (name, password_hash) VALUES ('Default', NULL)")
            conn.commit()
    conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Daily catch-up backup FIRST — before migrations or any other work. When
    # migrations apply later this boot, this file doubles as the pre-migration
    # state.
    daily_ran = startup_daily_backup()
    fresh, applied = init_db()
    migration_backups(fresh, applied, daily_ran)
    seed_currencies()
    seed_default_profile()
    try:
        catch_up_missed_fires()
        init_scheduler()
    except Exception as e:
        logger.warning("Scheduler init skipped: %s", e)
    yield
    shutdown_scheduler()


app = FastAPI(title="Personal Fin Hub API", lifespan=lifespan)
app.add_middleware(RequestIdMiddleware)


class HealthFilter(logging.Filter):
    def filter(self, record):
        return "/api/v1/health" not in record.getMessage()


# Silence health check logs in uvicorn.access
uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.addFilter(HealthFilter())


app.include_router(health.router, prefix="/api/v1")
app.include_router(market.router, prefix="/api/v1", dependencies=[Depends(require_profile)])
app.include_router(currencies.router, prefix="/api/v1", dependencies=[Depends(require_profile)])
app.include_router(entities.router, prefix="/api/v1", dependencies=[Depends(require_profile)])
app.include_router(fiscal_exemptions.router, prefix="/api/v1", dependencies=[Depends(require_profile)])
app.include_router(market_assets.router, prefix="/api/v1", dependencies=[Depends(require_profile)])
app.include_router(portfolio_assets.router, prefix="/api/v1", dependencies=[Depends(require_profile)])
app.include_router(prices.router, prefix="/api/v1", dependencies=[Depends(require_profile)])
app.include_router(profiles.router, prefix="/api/v1")
app.include_router(schedules.router, prefix="/api/v1", dependencies=[Depends(require_profile)])
app.include_router(stock_splits.router, prefix="/api/v1", dependencies=[Depends(require_profile)])
app.include_router(transactions.router, prefix="/api/v1", dependencies=[Depends(require_profile)])
app.include_router(transaction_fees.router, prefix="/api/v1", dependencies=[Depends(require_profile)])
app.include_router(transaction_taxes.router, prefix="/api/v1", dependencies=[Depends(require_profile)])
app.include_router(analytics.router, prefix="/api/v1", dependencies=[Depends(require_profile)])
app.include_router(transfers.router, prefix="/api/v1", dependencies=[Depends(require_profile)])
app.include_router(balance_snapshots.router, prefix="/api/v1", dependencies=[Depends(require_profile)])


@app.get("/")
async def root():
    return {"message": "Personal Fin Hub API is running"}
