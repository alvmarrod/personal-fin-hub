from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from models.enums import (
    AssetClass,
    AssetType,
    BalanceMode,
    DcaStatus,
    DistributionType,
    DividendType,
    EntityType,
    FeeNature,
    FeeType,
    IncomeCategory,
    InvestmentTransactionCategory,
    Layer,
    PeriodicityType,
    TrackingMode,
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
    main_currency: str | None = None
    country: str | None = None
    description: str | None = None


class EntityResponse(BaseModel):
    id: int
    name: str
    entity_type: EntityType
    main_currency: str | None = None
    country: str | None = None
    description: str | None = None
    model_config = ConfigDict(from_attributes=True)


class EntityDependentsResponse(BaseModel):
    has_transactions: bool
    has_balance_snapshots: bool
    has_schedules: bool


class ProfileCreate(BaseModel):
    name: str
    password: str | None = None


class ProfileRename(BaseModel):
    name: str


class ProfileUnlock(BaseModel):
    password: str | None = None


class ProfileResponse(BaseModel):
    id: int
    name: str
    has_password: bool
    default_fiscal_rule: str | None = None
    timezone: str = "Asia/Tokyo"
    created_at: str
    model_config = ConfigDict(from_attributes=True)


class ProfileUpdate(BaseModel):
    name: str | None = None
    default_fiscal_rule: str | None = None
    timezone: str | None = None


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


class FiscalPeriodCreate(BaseModel):
    rule_key: Literal["spain", "japan", "default", "latest", "none"]
    start_date: date
    end_date: date | None = None


class FiscalPeriodResponse(BaseModel):
    id: int
    rule_key: Literal["spain", "japan", "default", "latest", "none"]
    start_date: date
    end_date: date | None = None
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
    effective_date: date | None = None
    is_active: bool = True
    closing_date: date | None = None
    notes: str | None = None


class PortfolioAssetTransaction(BaseModel):
    id: int
    timestamp: datetime
    type: TransactionType
    investment_transaction_category: InvestmentTransactionCategory | None = None
    entity_id: int
    entity_name: str | None = None
    quantity: float
    unit_price: float
    total_value: float
    currency: str
    payment_currency: str | None = None
    fx_rate: float | None = None
    display_value: float | None = None


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
    notes: str | None = None
    current_value: float | None = None
    unrealized_pl_pct: float | None = None
    dividend_yield_pct: float | None = None
    price_source: Literal["market-api", "transaction-fallback", "manual", "none"] = "none"
    price_as_of: str | None = None
    transactions: list[PortfolioAssetTransaction] = []
    model_config = ConfigDict(from_attributes=True)


class TransactionCreate(BaseModel):
    timestamp: datetime
    type: TransactionType
    investment_transaction_category: InvestmentTransactionCategory | None = None
    income_category: IncomeCategory | None = None
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
    cash_handling: BalanceMode | None = None

    @model_validator(mode="after")
    def _validate_income_model(self):
        if self.income_category is not None and self.type != TransactionType.INCOME:
            raise ValueError("income_category is only valid for type=INCOME")
        if self.investment_transaction_category is not None and self.type not in (
            TransactionType.INVESTMENT_BUY,
            TransactionType.INVESTMENT_SELL,
        ):
            raise ValueError("investment_transaction_category is only valid for type=INVESTMENT_BUY/INVESTMENT_SELL")
        dividend_fields = (
            self.dividend_type,
            self.record_date,
            self.payment_date,
            self.dividend_currency,
            self.dividend_payment_currency,
            self.dividend_fx_rate,
        )
        if any(f is not None for f in dividend_fields) and self.income_category != IncomeCategory.DIVIDENDS:
            raise ValueError("dividend fields require income_category='dividends'")
        return self


class TransactionResponse(BaseModel):
    id: int
    timestamp: datetime
    type: TransactionType
    investment_transaction_category: InvestmentTransactionCategory | None = None
    income_category: IncomeCategory | None = None
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
    fiscal_rule: str | None = None
    dividend_type: DividendType | None = None
    record_date: date | None = None
    payment_date: date | None = None
    dividend_currency: str | None = None
    dividend_payment_currency: str | None = None
    dividend_fx_rate: float | None = None
    notes: str | None = None
    cash_handling: BalanceMode | None = None
    cash_handling_effective: BalanceMode | None = None
    attached_transaction_ids: list[int] | None = None
    model_config = ConfigDict(from_attributes=True)


class TransactionFeeCreate(BaseModel):
    transaction_id: int
    broker_fee_definition_id: int | None = None
    fee_type: FeeType
    nature: FeeNature
    fixed_amount: float = 0.0
    percentage: float = 0.0
    currency: str


class TransactionFeeResponse(BaseModel):
    id: int
    transaction_id: int
    broker_fee_definition_id: int | None = None
    fee_name: str | None = None
    fee_type: FeeType
    nature: FeeNature
    fixed_amount: float = 0.0
    percentage: float = 0.0
    currency: str
    model_config = ConfigDict(from_attributes=True)


class TransactionTaxCreate(BaseModel):
    transaction_id: int
    tax_definition_id: int
    tax_rate: float | None = None
    tax_amount: float
    currency: str


class TransactionTaxResponse(BaseModel):
    id: int
    transaction_id: int
    tax_definition_id: int
    tax_name: str | None = None
    tax_rate: float | None = None
    tax_amount: float
    currency: str
    model_config = ConfigDict(from_attributes=True)


class TransactionFeeInner(BaseModel):
    broker_fee_definition_id: int | None = None
    fee_type: FeeType
    nature: FeeNature
    fixed_amount: float = 0.0
    percentage: float = 0.0
    currency: str


class TransactionTaxInner(BaseModel):
    tax_definition_id: int
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
    cash_handling: BalanceMode | None = None

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
    income_category: IncomeCategory | None = None
    total_value: float | None = None
    portfolio_asset_id: int | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _validate_income_category(self):
        if self.income_category is not None and self.type != TransactionType.INCOME:
            raise ValueError("income_category is only valid for type=INCOME")
        return self


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
    income_category: IncomeCategory | None = None
    total_value: float | None = None
    portfolio_asset_id: int | None = None
    notes: str | None = None
    model_config = ConfigDict(from_attributes=True)


class ScheduleFullCreate(BaseModel):
    schedule: ScheduleCreate


class ScheduleFullResponse(BaseModel):
    schedule: ScheduleResponse
    transaction: TransactionResponse | None = None


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
    price_source: Literal["market-api", "transaction-fallback", "manual", "none"] = "none"
    price_as_of: str | None = None


class HoldingByEntityLine(BaseModel):
    entity_id: int | None = None
    entity_name: str | None = None
    asset_class: str | None = None
    current_value: float = 0.0
    currency: str | None = None


class DashboardSummary(BaseModel):
    display_currency: str = "USD"
    total_portfolio_value: float
    total_invested: float
    investment_value: float
    cash_balance: float
    total_return: float
    total_return_pct: float
    num_holdings: int
    unrealized_pl: float
    realized_pl: float


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
    category: str | None = None


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
    # Sum converted to the requested display currency (per-payment date rates,
    # §16.4); None when no display_currency was requested.
    total_dividends_display: float | None = None


class FeeSummaryLine(BaseModel):
    fee_type: str
    currency: str
    total_amount: float
    count: int


class TaxSummaryLine(BaseModel):
    tax_name: str
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


class PerformanceRateFallback(BaseModel):
    currency: str
    scope: Literal["realized_pl", "invested_historic", "dividends", "interest"]
    reason: Literal["closest-in-time", "no-rate"]
    requested_date: str | None = None
    used_timestamp: str | None = None
    count: int = 1


class PerformanceSummary(BaseModel):
    display_currency: str
    total_realized_pl: float
    total_unrealized_pl: float
    total_return: float
    total_invested_now: float
    total_invested_historic: float
    total_return_pct: float
    total_portfolio_value: float
    unrealized_pl_pct: float
    realized_pl_pct: float
    total_dividends: float = 0.0
    dividend_yield_pct: float = 0.0
    total_interest: float = 0.0
    rule_key: str = "default"
    rate_fallbacks: list[PerformanceRateFallback] = []


class TaxablePnlFiscalYear(BaseModel):
    fiscal_year: int
    start_date: date
    end_date: date
    realized_gains_taxable: float
    dividends_taxable: float
    total_taxable: float
    num_sells: int
    num_dividends: int


class TaxablePnlSummary(BaseModel):
    ruleset: str
    display_currency: str
    fiscal_years: list[TaxablePnlFiscalYear]
    total_taxable: float
    rate_fallbacks: list[PerformanceRateFallback] = []


class IncomeBySourceLine(BaseModel):
    period: str
    entity_id: int
    entity_name: str
    type: str
    income_category: str = "other"
    total_value: float
    count: int
    currency: str


class HistoricalValuePoint(BaseModel):
    date: str
    total_value: float
    investment_value: float = 0.0


class RateMetadata(BaseModel):
    rates: dict[str, float]
    latest_timestamp: str
    stale: bool = False


class CashFlowSummaryWithRates(BaseModel):
    lines: list[CashFlowLine]
    total_in: float
    total_out: float
    net: float
    rate_info: RateMetadata | None = None


class CashFlowTransactionLine(BaseModel):
    id: int
    date: str
    description: str
    amount: float
    currency: str
    source: str | None = None
    display_amount: float | None = None
    rate: float | None = None


class CashFlowTransactionsResponse(BaseModel):
    transactions: list[CashFlowTransactionLine]
    total_count: int


class IncomeBySourceWithRates(BaseModel):
    data: list[IncomeBySourceLine]
    rate_info: RateMetadata | None = None


class StockSplitCreate(BaseModel):
    market_code: str
    split_date: str
    ratio: int


class StockSplitResponse(BaseModel):
    id: int
    market_code: str
    split_date: str
    ratio: int
    created_at: str


class FlaggedSplit(BaseModel):
    market_code: str
    buy_date: str
    inferred_ratio: int
    buy_price: float
    market_price: float


class PortfolioValueChartResponse(BaseModel):
    data: dict[str, list[dict]]
    flagged_splits: list[FlaggedSplit]


class ManualValueCreate(BaseModel):
    value: float
    effective_date: date
    notes: str | None = None


class ManualValueResponse(BaseModel):
    id: int
    portfolio_asset_id: int
    value: float
    effective_date: date
    recorded_at: str
    notes: str | None = None


# ---------------------------------------------------------------------------
# Tax catalogs (§17.7-§17.8)
# ---------------------------------------------------------------------------


class TaxBaseRate(BaseModel):
    from_amount: float
    to_amount: float | None = None
    rate: float


class TaxBaseCreate(BaseModel):
    ruleset_key: str
    name: str
    computation: Literal["progressive", "flat"]
    flat_rate: float | None = None
    year_start: int | None = None
    categories: list[Literal["capital_gains", "dividends", "interest"]] = []
    rates: list[TaxBaseRate] = []


class TaxBaseResponse(BaseModel):
    id: int
    ruleset_key: str
    name: str
    computation: Literal["progressive", "flat"]
    flat_rate: float | None = None
    year_start: int | None = None
    categories: list[str]
    rates: list[TaxBaseRate]
    model_config = ConfigDict(from_attributes=True)


class TaxDefinitionCreate(BaseModel):
    slug: str
    ruleset_key: str | None = None
    name: str
    rate: float | None = None
    year_start: int | None = None


class TaxDefinitionResponse(BaseModel):
    id: int
    slug: str
    ruleset_key: str | None = None
    name: str
    rate: float | None = None
    year_start: int | None = None
    model_config = ConfigDict(from_attributes=True)


class BrokerFeeDefinitionCreate(BaseModel):
    name: str


class BrokerFeeDefinitionResponse(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Taxable P&L (§17)
# ---------------------------------------------------------------------------


class TaxDefinitionLine(BaseModel):
    """Per-definition computed/confirmed resolution on one item (§17.12)."""

    tax_definition_id: int
    slug: str
    name: str
    computed: float
    confirmed: float | None = None


class TaxablePnlItem(BaseModel):
    """One item in the expanded per-year detail (§17.12)."""

    transaction_id: int
    market_code: str | None = None
    ticker: str | None = None
    name: str | None = None
    category: str  # capital_gains | dividends
    date: str
    native_amount: float  # gross amount in native currency
    display_amount: float  # plain FX conversion of native_amount at transaction date
    taxable_amount: float  # rule-converted (§16.2) then reduced by exemption (§17.4), display currency
    tax_owed: float | None = None  # own bracket-attributed core tax (§17.12); null when no base configured
    fiscal_rule: str | None = None  # rule applied to this row (frozen for sells, per-date for dividends)
    tax_policy: str | None = None  # linked exemption policy name (e.g. NISA)
    currency: str
    taxes: list[TaxDefinitionLine] = []  # per-definition breakdown (§17.11/§17.12)


class TaxablePnlFiscalYearExtended(BaseModel):
    """Extended fiscal year with tax computation (§17.9)."""

    fiscal_year: int
    start_date: date
    end_date: date
    realized_gains_taxable: float
    dividends_taxable: float
    total_taxable: float
    num_sells: int
    num_dividends: int
    tax_owed: dict[str, float] = {}
    total_tax_owed: float | None = None  # year-level post-withholding total (§17.9); null when no base configured
    confirmed: dict[str, float] = {}  # per-category confirmed amounts, display currency (§17.9/decision 5)
    total_confirmed: float = 0.0
    items: list[TaxablePnlItem] = []


class TaxablePnlSummaryExtended(BaseModel):
    """Extended summary with per-category tax owed (§17.9)."""

    ruleset: str
    display_currency: str
    fiscal_years: list[TaxablePnlFiscalYearExtended]
    total_taxable: float
    total_tax_owed: float | None = None
    total_confirmed: float | None = None  # null when no transaction_taxes rows exist
    combined_base: float | None = None
    rate_fallbacks: list[PerformanceRateFallback] = []
    default_ruleset: str | None = None


class MarketCycleStateRef(BaseModel):
    """A market-cycle state reference (id + display name)."""

    id: int
    name: str


class MarketCycleFormula(BaseModel):
    """How a metric or signal value is computed (structured; the view localizes)."""

    code: str
    inputs: list[dict] = []
    delta: float | None = None
    result: float | str | None = None


class MarketCycleCondition(BaseModel):
    """The condition a signal compares a value against."""

    op: str
    target: float | str | list[str] | None = None
    window: int | None = None


class MarketCycleMetric(BaseModel):
    """One engine input with its current value and direction (state_engine.md §9)."""

    kpi: str
    kind: str
    value: float | str | None = None
    unit: str | None = None
    prev_value: float | None = None
    delta: float | None = None
    formula: MarketCycleFormula | None = None


class MarketCycleSignalPart(BaseModel):
    """One sub-condition of a combination signal."""

    metric: str
    kind: str
    met: bool
    value: float | str | None = None
    unit: str | None = None
    condition: MarketCycleCondition | None = None
    formula: MarketCycleFormula | None = None


class MarketCycleSignal(BaseModel):
    """One signal that drives a transition (state_engine.md §4)."""

    code: str
    metric: str
    kind: str
    met: bool
    value: float | str | None = None
    unit: str | None = None
    condition: MarketCycleCondition | None = None
    formula: MarketCycleFormula | None = None
    parts: list[MarketCycleSignalPart] = []


class MarketCycleTransition(BaseModel):
    """One outgoing transition of the current state."""

    source: str
    target: str
    status: str
    direction: str
    priority: int
    held_months: int = 0
    required_months: int = 0
    signals: list[MarketCycleSignal] = []


class MarketCycleStatus(BaseModel):
    """Investment Market Cycle status object (state_engine.md §9)."""

    scope: str
    current_state: MarketCycleStateRef
    current_state_since: str
    active_transitions: list[MarketCycleTransition]
    entry_signals: str
    ambiguous_confirmation: bool
    last_update: str
    metrics: list[MarketCycleMetric] = []
