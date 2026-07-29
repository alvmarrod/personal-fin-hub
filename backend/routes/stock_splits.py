from fastapi import APIRouter, HTTPException

from db.connection import get_db
from models import StockSplitCreate, StockSplitResponse

router = APIRouter(prefix="/stock-splits", tags=["stock-splits"])


@router.get("", response_model=list[StockSplitResponse])
async def list_splits(market_code: str | None = None):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM stock_splits WHERE (? IS NULL OR market_code = ?) ORDER BY split_date DESC",
        (market_code, market_code),
    ).fetchall()
    return [dict(r) for r in rows]


@router.post("", response_model=StockSplitResponse, status_code=201)
async def create_split(body: StockSplitCreate):
    conn = get_db()
    year = body.split_date[:4]
    existing = conn.execute(
        "SELECT id FROM stock_splits WHERE market_code = ? AND substr(split_date, 1, 4) = ?",
        (body.market_code, year),
    ).fetchone()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"A split for {body.market_code} in {year} already exists",
        )
    cursor = conn.execute(
        "INSERT INTO stock_splits (market_code, split_date, ratio) VALUES (?, ?, ?)",
        (body.market_code, body.split_date, body.ratio),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM stock_splits WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


@router.delete("/{split_id}", status_code=204)
async def delete_split(split_id: int):
    conn = get_db()
    row = conn.execute("SELECT id FROM stock_splits WHERE id = ?", (split_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Split not found")
    conn.execute("DELETE FROM stock_splits WHERE id = ?", (split_id,))
    conn.commit()
