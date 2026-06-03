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
    MONEY_IN = "MONEY_IN"
    MONEY_OUT = "MONEY_OUT"
    INVESTMENT_BUY = "INVESTMENT_BUY"
    INVESTMENT_SELL = "INVESTMENT_SELL"
    DIVIDEND = "DIVIDEND"
    INTEREST = "INTEREST"
    TRANSFER = "TRANSFER"


class TransactionCategory(StrEnum):
    NORMAL = "NORMAL"
    DCA = "DCA"
    REBALANCE = "REBALANCE"


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
