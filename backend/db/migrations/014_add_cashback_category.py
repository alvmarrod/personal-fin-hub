"""Add 'cashback' to income_category CHECK constraints on transactions and schedules."""


def up(conn):
    fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("""
            CREATE TABLE transactions_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('INCOME', 'MONEY_OUT', 'INVESTMENT_BUY', 'INVESTMENT_SELL', 'TRANSFER', 'TRANSFER_IN', 'TRANSFER_OUT', 'BALANCE_ADJUSTMENT')),
                investment_transaction_category TEXT CHECK (investment_transaction_category IN ('NORMAL', 'DCA', 'REBALANCE')),
                income_category TEXT CHECK (income_category IN ('salary', 'other', 'dividends', 'interest', 'cashback')),
                entity_id INTEGER NOT NULL REFERENCES entities(id),
                portfolio_asset_id INTEGER REFERENCES portfolio_assets(id),
                quantity REAL,
                unit_price REAL,
                currency TEXT NOT NULL REFERENCES currencies(code),
                total_value REAL,
                gross_amount REAL,
                net_amount REAL,
                payment_currency TEXT REFERENCES currencies(code),
                fx_rate REAL,
                settlement_date DATE,
                fiscal_exemption_id INTEGER REFERENCES fiscal_exemptions(id),
                fiscal_rule TEXT,
                dividend_type TEXT CHECK (dividend_type IN ('regular', 'special', 'qualified')),
                record_date DATE,
                payment_date DATE,
                dividend_currency TEXT REFERENCES currencies(code),
                dividend_payment_currency TEXT REFERENCES currencies(code),
                dividend_fx_rate REAL,
                notes TEXT,
                profile_id INTEGER REFERENCES profiles(id)
            )
        """)
        cols = ", ".join(r["name"] for r in conn.execute("PRAGMA table_info(transactions)").fetchall())
        conn.execute(f"INSERT INTO transactions_new ({cols}) SELECT {cols} FROM transactions")
        conn.execute("DROP TABLE transactions")
        conn.execute("ALTER TABLE transactions_new RENAME TO transactions")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_profile ON transactions(profile_id)")

        conn.execute("""
            CREATE TABLE schedules_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE,
                periodicity_type TEXT NOT NULL CHECK (periodicity_type IN ('ONE_OFF', 'DAILY', 'WEEKLY', 'MONTHLY', 'QUARTERLY', 'ANNUALLY', 'CUSTOM')),
                custom_cron TEXT,
                linked_transaction_id INTEGER REFERENCES transactions(id),
                entity_id INTEGER REFERENCES entities(id),
                currency TEXT REFERENCES currencies(code),
                type TEXT,
                income_category TEXT CHECK (income_category IN ('salary', 'other', 'dividends', 'interest', 'cashback')),
                total_value REAL,
                notes TEXT,
                portfolio_asset_id INTEGER REFERENCES portfolio_assets(id),
                profile_id INTEGER REFERENCES profiles(id)
            )
        """)
        cols = ", ".join(r["name"] for r in conn.execute("PRAGMA table_info(schedules)").fetchall())
        conn.execute(f"INSERT INTO schedules_new ({cols}) SELECT {cols} FROM schedules")
        conn.execute("DROP TABLE schedules")
        conn.execute("ALTER TABLE schedules_new RENAME TO schedules")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_schedules_profile ON schedules(profile_id)")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute(f"PRAGMA foreign_keys={fk}")


def verify(conn):
    for table in ("transactions", "schedules"):
        row = conn.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'").fetchone()
        if row is None or "cashback" not in row["sql"]:
            return False
    return True
