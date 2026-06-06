from datetime import date, datetime
from pydantic import BaseModel, ConfigDict

from models.enums import (
    AssetClass,
    AssetType,
    DcaStatus,
    DistributionType,
    DividendType,
    EntityType,
    FeeNature,
    FeeType,
    Layer,
    PeriodicityType,
    TrackingMode,
    TransactionCategory,
    TransactionType,
)


class Currency(BaseModel):
    code: str
    base_code: str
    rate: float
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)


class CurrencyCodeCreate(BaseModel):
    code: str


class CurrencyRateCreate(BaseModel):
    code: str
    base_code: str
    rate: float
    timestamp: datetime


class CurrencyRateResponse(BaseModel):
    code: str
    base_code: str
    rate: float
    timestamp: datetime
    inverted: bool = False


class CurrencyPair(BaseModel):
    code: str
    base_code: str


class CurrencyRateBulkUpsert(BaseModel):
    timestamps: list[datetime]
    rates: list[float]

    def model_post_init(self, _ctx):
        if len(self.timestamps) != len(self.rates):
            raise ValueError("timestamps and rates must have the same length")
        if not self.timestamps:
            raise ValueError("at least one rate entry is required")


class CurrencyHoldingSeries(BaseModel):
    currency: str
    values: list[float]


class CurrencyHoldingHistory(BaseModel):
    dates: list[str]
    series: list[CurrencyHoldingSeries]
    latest_raw: dict[str, float]


class RateChartDataset(BaseModel):
    label: str
    data: list[float]
    axis: str
    color: str


class RateChartResponse(BaseModel):
    labels: list[str]
    datasets: list[RateChartDataset]


class EntityCreate(BaseModel):
    name: str
    entity_type: EntityType
    country: str | None = None
    description: str | None = None


class EntityResponse(BaseModel):
    id: int
    name: str
    entity_type: EntityType
    country: str | None = None
    description: str | None = None
    model_config = ConfigDict(from_attributes=True)


class EntityDependentsResponse(BaseModel):
    has_transactions: bool
    has_balance_snapshots: bool
    has_schedules: bool


class FiscalExemptionCreate(BaseModel):
    exemption_type: str
    description: str | None = None
    exemption_amount: float = 0
    exemption_rate: float = 100
    exemption_rate_limit: float | None = None


class FiscalExemptionResponse(BaseModel):
    id: int
    exemption_type: str
    description: str | None = None
    exemption_amount: float = 0
    exemption_rate: float = 100
    exemption_rate_limit: float | None = None
    model_config = ConfigDict(from_attributes=True)


class MarketAsset(BaseModel):
    market_code: str
    ticker: str | None = None
    asset_type: AssetType
    asset_class: AssetClass | None = None
    currency_code: str
    name: str | None = None
    description: str | None = None
    exchange: str | None = None
    model_config = ConfigDict(from_attributes=True)


class PortfolioAssetCreate(BaseModel):
    market_code: str
    distribution_type: DistributionType | None = None
    dca_status: DcaStatus | None = None
    layer: Layer | None = None
    tactic: bool = False
    desired_weight: float | None = None
    ter: float | None = None
    tracking_mode: TrackingMode = TrackingMode.AUTO
    current_value_manual: float | None = None
    is_active: bool = True
    closing_date: date | None = None
    purchase_date: date | None = None
    notes: str | None = None


class PortfolioAssetResponse(BaseModel):
    id: int
    market_code: str
    distribution_type: DistributionType | None = None
    dca_status: DcaStatus | None = None
    layer: Layer | None = None
    tactic: bool = False
    desired_weight: float | None = None
    ter: float | None = None
    tracking_mode: TrackingMode = TrackingMode.AUTO
    current_value_manual: float | None = None
    is_active: bool = True
    closing_date: date | None = None
    purchase_date: date | None = None
    notes: str | None = None
    model_config = ConfigDict(from_attributes=True)


class TransactionCreate(BaseModel):
    timestamp: datetime
    type: TransactionType
    transaction_category: TransactionCategory | None = None
    entity_id: int
    portfolio_asset_id: int | None = None
    quantity: float | None = None
    unit_price: float | None = None
    currency: str
    total_value: float | None = None
    gross_amount: float | None = None
    net_amount: float | None = None
    payment_currency: str | None = None
    fx_rate: float | None = None
    settlement_date: date | None = None
    fiscal_exemption_id: int | None = None
    dividend_type: DividendType | None = None
    record_date: date | None = None
    payment_date: date | None = None
    dividend_currency: str | None = None
    dividend_payment_currency: str | None = None
    dividend_fx_rate: float | None = None
    notes: str | None = None


class TransactionResponse(BaseModel):
    id: int
    timestamp: datetime
    type: TransactionType
    transaction_category: TransactionCategory | None = None
    entity_id: int
    portfolio_asset_id: int | None = None
    quantity: float | None = None
    unit_price: float | None = None
    currency: str
    total_value: float | None = None
    gross_amount: float | None = None
    net_amount: float | None = None
    payment_currency: str | None = None
    fx_rate: float | None = None
    settlement_date: date | None = None
    fiscal_exemption_id: int | None = None
    dividend_type: DividendType | None = None
    record_date: date | None = None
    payment_date: date | None = None
    dividend_currency: str | None = None
    dividend_payment_currency: str | None = None
    dividend_fx_rate: float | None = None
    notes: str | None = None
    model_config = ConfigDict(from_attributes=True)


class TransactionFeeCreate(BaseModel):
    transaction_id: int
    fee_type: FeeType
    nature: FeeNature
    fixed_amount: float = 0.0
    percentage: float = 0.0
    currency: str


class TransactionFeeResponse(BaseModel):
    id: int
    transaction_id: int
    fee_type: FeeType
    nature: FeeNature
    fixed_amount: float = 0.0
    percentage: float = 0.0
    currency: str
    model_config = ConfigDict(from_attributes=True)


class TransactionTaxCreate(BaseModel):
    transaction_id: int
    tax_type: str
    tax_rate: float | None = None
    tax_amount: float
    currency: str


class TransactionTaxResponse(BaseModel):
    id: int
    transaction_id: int
    tax_type: str
    tax_rate: float | None = None
    tax_amount: float
    currency: str
    model_config = ConfigDict(from_attributes=True)


class TransactionFeeInner(BaseModel):
    fee_type: FeeType
    nature: FeeNature
    fixed_amount: float = 0.0
    percentage: float = 0.0
    currency: str


class TransactionTaxInner(BaseModel):
    tax_type: str
    tax_rate: float | None = None
    tax_amount: float
    currency: str


class FullTransactionCreate(BaseModel):
    transaction: TransactionCreate
    fees: list[TransactionFeeInner] = []
    taxes: list[TransactionTaxInner] = []


class FullTransactionResponse(BaseModel):
    transaction: TransactionResponse
    fees: list[TransactionFeeResponse]
    taxes: list[TransactionTaxResponse]


class BatchCreate(BaseModel):
    transactions: list[TransactionCreate]

    def model_post_init(self, _ctx):
        if not self.transactions:
            raise ValueError("at least one transaction is required")


class BatchResponse(BaseModel):
    transactions: list[TransactionResponse]


class TransferCreate(BaseModel):
    from_entity_id: int
    to_entity_id: int
    amount: float
    currency: str
    timestamp: datetime
    notes: str | None = None
    fees: list[TransactionFeeInner] = []

    def model_post_init(self, _ctx):
        if self.amount <= 0:
            raise ValueError("amount must be positive")
        if self.from_entity_id == self.to_entity_id:
            raise ValueError("from and to entities must be different")


class TransferResponse(BaseModel):
    from_transaction: TransactionResponse
    to_transaction: TransactionResponse
    fees: list[TransactionFeeResponse]


class PriceCreate(BaseModel):
    market_code: str
    timestamp: datetime
    price: float
    provider: str | None = None


class PriceResponse(BaseModel):
    id: int
    market_code: str
    timestamp: datetime
    price: float
    provider: str | None = None
    model_config = ConfigDict(from_attributes=True)


class ScheduleCreate(BaseModel):
    description: str
    start_date: date
    end_date: date | None = None
    periodicity_type: PeriodicityType
    custom_cron: str | None = None
    entity_id: int | None = None
    currency: str | None = None
    type: TransactionType | None = None
    total_value: float | None = None
    notes: str | None = None


class ScheduleResponse(BaseModel):
    id: int
    description: str
    start_date: date
    end_date: date | None = None
    periodicity_type: PeriodicityType
    custom_cron: str | None = None
    entity_id: int | None = None
    currency: str | None = None
    type: TransactionType | None = None
    total_value: float | None = None
    notes: str | None = None
    model_config = ConfigDict(from_attributes=True)


class ScheduleFullCreate(BaseModel):
    schedule: ScheduleCreate


class ScheduleFullResponse(BaseModel):
    schedule: ScheduleResponse
    transaction: TransactionResponse


class BalanceSnapshotCreate(BaseModel):
    entity_id: int
    currency: str
    amount: float
    timestamp: datetime
    notes: str | None = None


class BalanceSnapshotResponse(BaseModel):
    id: int
    entity_id: int
    currency: str
    amount: float
    timestamp: datetime
    notes: str | None = None
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Analytics models (read-only, no from_attributes needed)
# ---------------------------------------------------------------------------


class HoldingLine(BaseModel):
    portfolio_asset_id: int
    market_code: str
    ticker: str | None = None
    name: str | None = None
    asset_type: AssetType
    asset_class: AssetClass | None = None
    layer: Layer | None = None
    currency_code: str
    tracking_mode: TrackingMode
    net_quantity: float
    avg_cost: float | None = None
    total_cost: float
    latest_price: float | None = None
    current_value: float | None = None
    unrealized_pl: float | None = None
    unrealized_pl_pct: float | None = None
    weight_pct: float = 0.0


class HoldingByEntityLine(BaseModel):
    entity_id: int | None = None
    entity_name: str | None = None
    asset_class: str | None = None
    current_value: float = 0.0


class DashboardSummary(BaseModel):
    total_portfolio_value: float
    total_invested: float
    cash_balance: float
    total_return: float
    total_return_pct: float
    num_holdings: int


class AllocationLine(BaseModel):
    category: str
    dimension: str
    value_pct: float
    value_abs: float


class CashFlowLine(BaseModel):
    period: str
    type: str
    total_value: float
    count: int
    currency: str


class CashFlowSummary(BaseModel):
    lines: list[CashFlowLine]
    total_in: float
    total_out: float
    net: float


class DividendLine(BaseModel):
    portfolio_asset_id: int | None = None
    market_code: str | None = None
    ticker: str | None = None
    name: str | None = None
    currency: str
    total_dividends: float
    count: int


class FeeSummaryLine(BaseModel):
    fee_type: str
    currency: str
    total_amount: float
    count: int


class TaxSummaryLine(BaseModel):
    tax_type: str
    currency: str
    total_amount: float
    count: int


class FeeTaxSummary(BaseModel):
    fees: list[FeeSummaryLine]
    taxes: list[TaxSummaryLine]
    total_fees: float
    total_taxes: float


class RealizedGainLine(BaseModel):
    transaction_id: int
    portfolio_asset_id: int | None = None
    market_code: str | None = None
    ticker: str | None = None
    name: str | None = None
    sell_date: str
    sell_quantity: float
    sell_price: float
    sell_total: float
    cost_basis: float
    realized_pl: float
    realized_pl_pct: float
    currency: str


class PerformanceSummary(BaseModel):
    total_realized_pl: float
    total_unrealized_pl: float
    total_return: float
    total_invested: float
    total_return_pct: float
    total_portfolio_value: float


class IncomeBySourceLine(BaseModel):
    period: str
    entity_id: int
    entity_name: str
    total_value: float
    count: int


class HistoricalValuePoint(BaseModel):
    date: str
    total_value: float
