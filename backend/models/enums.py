from enum import StrEnum


class AssetType(StrEnum):
    STOCK = "STOCK"
    ETF = "ETF"
    ETC = "ETC"
    FUND = "FUND"
    INDEX_FUND = "INDEX FUND"
    CURRENCY = "CURRENCY"
    CRYPTO = "CRYPTO"
    OTHER = "OTHER"


class AssetClass(StrEnum):
    FI = "FI"
    VI = "VI"
    CORP_FI = "corp FI"
    SOVEREIGN_FI = "Sovereign FI"
    MIX_FI = "mix FI"
    REIT = "REIT"
    GOLD = "Gold"
    MONETARY = "Monetary"


class StrategyBucket(StrEnum):
    """Policy buckets for the investment strategy. Asset classes map to these."""

    EQUITIES = "equities"
    BONDS = "bonds"
    CASH = "cash"
    REAL_ESTATE = "real_estate"
    GOLD = "gold"


class DistributionType(StrEnum):
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    N_A = "N/A"


class DcaStatus(StrEnum):
    ONGOING = "ongoing"
    PAUSED = "paused"
    CLOSED = "closed"


class Layer(StrEnum):
    CORE = "core"
    RESERVE = "reserve"
    SATELLITE = "satellite"


class TrackingMode(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"


class TransactionType(StrEnum):
    INCOME = "INCOME"
    MONEY_OUT = "MONEY_OUT"
    INVESTMENT_BUY = "INVESTMENT_BUY"
    INVESTMENT_SELL = "INVESTMENT_SELL"
    TRANSFER = "TRANSFER"  # Reserved legacy value; never written by the app
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    BALANCE_ADJUSTMENT = "BALANCE_ADJUSTMENT"
    FX_CONVERSION = "FX_CONVERSION"
    DEBT_IN = "DEBT_IN"
    DEBT_OUT = "DEBT_OUT"


class DebtDirection(StrEnum):
    PAYABLE = "payable"
    RECEIVABLE = "receivable"


class DebtStatus(StrEnum):
    ACTIVE = "active"
    SETTLED = "settled"
    CANCELLED = "cancelled"


class InstallmentMode(StrEnum):
    EQUAL_PAYMENT = "equal_payment"
    EQUAL_PRINCIPAL = "equal_principal"
    INTEREST_ONLY = "interest_only"
    MANUAL = "manual"


class DayCount(StrEnum):
    MONTHLY = "monthly"
    ACTUAL_365 = "actual_365"
    ACTUAL_360 = "actual_360"
    THIRTY_360 = "thirty_360"


class RateResetMode(StrEnum):
    RECALCULATE_INSTALLMENT = "recalculate_installment"
    KEEP_INSTALLMENT = "keep_installment"


class DisbursementMode(StrEnum):
    POCKET = "pocket"
    NONE = "none"


class DebtPaymentKind(StrEnum):
    REGULAR = "regular"
    EXTRA = "extra"
    SETTLEMENT = "settlement"


class InvestmentTransactionCategory(StrEnum):
    NORMAL = "NORMAL"
    DCA = "DCA"
    REBALANCE = "REBALANCE"


class BalanceMode(StrEnum):
    """Cash handling for a spend.

    ``inject`` / ``debit`` keep their meaning for non-buy spends. For
    ``INVESTMENT_BUY`` the four explicit funding modes are:
    ``debit`` (pocket only), ``inject`` (pocket + inject the rest),
    ``debit_pocket_main`` (pocket + main-currency conversion) and
    ``inject_pocket_main`` (pocket + main + inject the rest).
    """

    INJECT = "inject"
    DEBIT = "debit"
    DEBIT_POCKET_MAIN = "debit_pocket_main"
    INJECT_POCKET_MAIN = "inject_pocket_main"


class CashEffect(StrEnum):
    """What a spend actually did to its cash pocket (read model)."""

    INJECT = "inject"
    DEBIT = "debit"
    ABSORBED = "absorbed"


class IncomeCategory(StrEnum):
    SALARY = "salary"
    OTHER = "other"
    DIVIDENDS = "dividends"
    INTEREST = "interest"
    CASHBACK = "cashback"


class DividendType(StrEnum):
    REGULAR = "regular"
    SPECIAL = "special"
    QUALIFIED = "qualified"


class FeeType(StrEnum):
    BROKER = "BROKER"
    FX = "FX"
    PLATFORM = "PLATFORM"
    OTHER = "OTHER"


class FeeNature(StrEnum):
    FIXED = "FIXED"
    PERCENTAGE = "PERCENTAGE"
    BOTH = "BOTH"
    MIN = "MIN"


class EntityType(StrEnum):
    BROKER = "BROKER"
    BANK = "BANK"
    EMPLOYER = "EMPLOYER"
    EXCHANGE = "EXCHANGE"
    OTHER = "OTHER"


class PeriodicityType(StrEnum):
    ONE_OFF = "ONE_OFF"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    ANNUALLY = "ANNUALLY"
    CUSTOM = "CUSTOM"
