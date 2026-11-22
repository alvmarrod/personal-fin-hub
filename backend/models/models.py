from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from models.enums import (
    AssetClass,
    AssetType,
    BalanceMode,
    CashEffect,
    DayCount,
    DcaStatus,
    DebtDirection,
    DebtPaymentKind,
    DebtStatus,
    DisbursementMode,
    DistributionType,
    DividendType,
    EntityType,
    FeeNature,
    FeeType,
    IncomeCategory,
    InstallmentMode,
    InvestmentTransactionCategory,
    Layer,
    PeriodicityType,
    RateResetMode,
    StrategyBucket,
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
    supports_multi_currency: bool = True
    country: str | None = None
    description: str | None = None

    @model_validator(mode="after")
    def _validate_currency_mode(self):
        if not self.supports_multi_currency and not self.main_currency:
            raise ValueError("main_currency is required when supports_multi_currency is false")
        return self


class EntityResponse(BaseModel):
    id: int
    name: str
    entity_type: EntityType
    main_currency: str | None = None
    supports_multi_currency: bool = True
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


class StrategySetBody(BaseModel):
    """A full target set. All five buckets are required and must sum to 100."""

    effective_from: date
    targets: dict[str, float]

    @model_validator(mode="after")
    def _validate_targets(self):
        if set(self.targets) != {bucket.value for bucket in StrategyBucket}:
            raise ValueError("targets must define all five buckets")
        for bucket, pct in self.targets.items():
            if pct < 0 or pct > 100:
                raise ValueError(f"target for {bucket} must be between 0 and 100")
        if abs(sum(self.targets.values()) - 100) > 0.01:
            raise ValueError("targets must sum to 100")
        return self


class StrategyTargetSet(BaseModel):
    effective_from: date
    targets: dict[str, float]
    updated_at: str | None = None


class StrategyDriftBucket(BaseModel):
    bucket: str
    target_pct: float
    value: float
    share_pct: float
    drift_pp: float
    amount_to_move: float
    rate_missing: bool = False


class StrategyDriftResidual(BaseModel):
    value: float
    share_pct: float
    rate_missing: bool = False


class StrategyHistoryPoint(BaseModel):
    date: str
    bucket: str
    value: float
    share_pct: float
    target_pct: float | None = None


class StrategyHistory(BaseModel):
    points: list[StrategyHistoryPoint]


class StrategyDrift(BaseModel):
    effective_from: date | None = None
    as_of: date
    total: float
    rate_missing: bool = False
    buckets: list[StrategyDriftBucket]
    unassigned: StrategyDriftResidual


class DebtRateBody(BaseModel):
    effective_from: date
    annual_rate: float

    @model_validator(mode="after")
    def _validate_rate(self):
        if not 0 <= self.annual_rate <= 100:
            raise ValueError("annual_rate must be between 0 and 100")
        return self


class DebtRate(DebtRateBody):
    id: int


class DebtPayment(BaseModel):
    id: int
    paid_at: date
    amount: float
    principal_amount: float
    interest_amount: float
    fees_amount: float
    insurance_amount: float
    other_amount: float
    kind: DebtPaymentKind
    transaction_id: int | None = None
    plan_entry_id: int | None = None
    notes: str | None = None


class DebtPaymentBody(BaseModel):
    paid_at: date
    entity_id: int
    amount: float
    principal_amount: float | None = None
    interest_amount: float | None = None
    fees_amount: float = 0
    insurance_amount: float = 0
    other_amount: float = 0
    kind: DebtPaymentKind = DebtPaymentKind.REGULAR
    principal_only: bool = False
    notes: str | None = None

    @model_validator(mode="after")
    def _validate_split(self):
        if self.amount <= 0:
            raise ValueError("amount must be positive")
        for name in ("fees_amount", "insurance_amount", "other_amount"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative")
        explicit = self.principal_amount is not None or self.interest_amount is not None
        if explicit:
            if self.principal_amount is None or self.interest_amount is None:
                raise ValueError("provide both principal_amount and interest_amount")
            if self.principal_only:
                raise ValueError("principal_only cannot be combined with an explicit split")
            if self.principal_amount < 0 or self.interest_amount < 0:
                raise ValueError("principal_amount and interest_amount cannot be negative")
            total = (
                self.principal_amount
                + self.interest_amount
                + self.fees_amount
                + self.insurance_amount
                + self.other_amount
            )
            if abs(total - self.amount) > 0.01:
                raise ValueError("the split must add up to amount")
        return self


class DebtPlanEntryBody(BaseModel):
    due_date: date
    payment_amount: float
    principal_amount: float
    interest_amount: float
    fees_amount: float = 0
    insurance_amount: float = 0
    other_amount: float = 0

    @model_validator(mode="after")
    def _validate_entry(self):
        for name in (
            "payment_amount",
            "principal_amount",
            "interest_amount",
            "fees_amount",
            "insurance_amount",
            "other_amount",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative")
        total = (
            self.principal_amount + self.interest_amount + self.fees_amount + self.insurance_amount + self.other_amount
        )
        if abs(total - self.payment_amount) > 0.01:
            raise ValueError("the split must add up to payment_amount")
        return self


class DebtPlanEntry(DebtPlanEntryBody):
    id: int
    period_no: int


class DebtPlanImport(BaseModel):
    replace_from: date | None = None
    entries: list[DebtPlanEntryBody]

    @model_validator(mode="after")
    def _validate_entries(self):
        if not self.entries:
            raise ValueError("the plan needs at least one entry")
        return self


class DebtCreate(BaseModel):
    direction: DebtDirection
    counterparty_name: str
    description: str | None = None
    currency: str
    principal: float
    start_date: date
    annual_rate: float
    term_months: int | None = None
    maturity_date: date | None = None
    installment_mode: InstallmentMode = InstallmentMode.MANUAL
    installment_amount: float | None = None
    principal_per_installment: float | None = None
    day_count: DayCount = DayCount.MONTHLY
    rate_reset_mode: RateResetMode = RateResetMode.RECALCULATE_INSTALLMENT
    review_period_months: int | None = None
    disbursement_mode: DisbursementMode = DisbursementMode.NONE
    disbursement_entity_id: int | None = None
    disbursement_date: date | None = None
    payment_entity_id: int | None = None
    payment_periodicity: PeriodicityType | None = None
    first_payment_date: date | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _validate(self):
        if not self.counterparty_name.strip():
            raise ValueError("counterparty_name is required")
        if self.principal <= 0:
            raise ValueError("principal must be positive")
        if not 0 <= self.annual_rate <= 100:
            raise ValueError("annual_rate must be between 0 and 100")
        if self.term_months is not None and self.term_months < 1:
            raise ValueError("term_months must be positive")
        if self.review_period_months not in (None, 1, 3, 6, 12):
            raise ValueError("review_period_months must be 1, 3, 6 or 12")
        if self.installment_mode == InstallmentMode.EQUAL_PRINCIPAL:
            if not self.principal_per_installment or self.principal_per_installment <= 0:
                raise ValueError("principal_per_installment is required for equal_principal")
        if self.installment_mode == InstallmentMode.EQUAL_PAYMENT and self.installment_amount is not None:
            if self.installment_amount <= 0:
                raise ValueError("installment_amount must be positive")
        if self.disbursement_mode == DisbursementMode.POCKET:
            if self.disbursement_entity_id is None:
                raise ValueError("disbursement_entity_id is required for pocket")
            if self.disbursement_date is None:
                raise ValueError("disbursement_date is required for pocket")
        if self.payment_periodicity is not None and self.payment_entity_id is None:
            raise ValueError("payment_entity_id is required with a payment periodicity")
        return self


class DebtUpdate(BaseModel):
    direction: DebtDirection | None = None
    counterparty_name: str | None = None
    description: str | None = None
    currency: str | None = None
    principal: float | None = None
    start_date: date | None = None
    term_months: int | None = None
    maturity_date: date | None = None
    installment_mode: InstallmentMode | None = None
    installment_amount: float | None = None
    principal_per_installment: float | None = None
    day_count: DayCount | None = None
    rate_reset_mode: RateResetMode | None = None
    review_period_months: int | None = None
    disbursement_mode: DisbursementMode | None = None
    disbursement_entity_id: int | None = None
    disbursement_date: date | None = None
    payment_entity_id: int | None = None
    payment_periodicity: PeriodicityType | None = None
    first_payment_date: date | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _validate(self):
        if self.counterparty_name is not None and not self.counterparty_name.strip():
            raise ValueError("counterparty_name cannot be empty")
        if self.principal is not None and self.principal <= 0:
            raise ValueError("principal must be positive")
        if self.term_months is not None and self.term_months < 1:
            raise ValueError("term_months must be positive")
        if self.review_period_months not in (None, 1, 3, 6, 12):
            raise ValueError("review_period_months must be 1, 3, 6 or 12")
        return self


class DebtSettleBody(BaseModel):
    settled_at: date
    entity_id: int
    amount: float | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _validate_amount(self):
        if self.amount is not None and self.amount <= 0:
            raise ValueError("amount must be positive")
        return self


class DebtCancelBody(BaseModel):
    cancelled_at: date
    notes: str | None = None


class DebtNextPayment(BaseModel):
    debt_id: int
    counterparty_name: str
    due_date: date
    amount: float


class DebtSummary(BaseModel):
    display_currency: str
    payable: float
    receivable: float
    payable_count: int
    receivable_count: int
    payable_accrued_interest: float
    receivable_accrued_interest: float
    next_payable: DebtNextPayment | None = None
    next_receivable: DebtNextPayment | None = None


class DebtResponse(BaseModel):
    id: int
    direction: DebtDirection
    counterparty_name: str
    description: str | None = None
    currency: str
    principal: float
    start_date: date
    term_months: int | None = None
    maturity_date: date | None = None
    installment_mode: InstallmentMode
    installment_amount: float | None = None
    principal_per_installment: float | None = None
    day_count: DayCount
    rate_reset_mode: RateResetMode
    review_period_months: int | None = None
    disbursement_mode: DisbursementMode
    disbursement_entity_id: int | None = None
    disbursement_date: date | None = None
    status: DebtStatus
    settled_at: date | None = None
    settled_amount: float | None = None
    settlement_adjustment: float | None = None
    notes: str | None = None
    current_rate: float = 0
    outstanding_principal: float = 0
    accrued_interest: float = 0
    total_due: float = 0
    progress_pct: float = 0
    next_payment_date: date | None = None
    next_payment_amount: float | None = None


class DebtDetail(DebtResponse):
    rates: list[DebtRate] = []
    payments: list[DebtPayment] = []
    plan: list[DebtPlanEntry] = []


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
        pocket_main_modes = (BalanceMode.DEBIT_POCKET_MAIN, BalanceMode.INJECT_POCKET_MAIN)
        if self.cash_handling in pocket_main_modes and self.type != TransactionType.INVESTMENT_BUY:
            raise ValueError("Pocket+main cash-handling modes are only valid for INVESTMENT_BUY")
        if self.type == TransactionType.FX_CONVERSION:
            if not self.payment_currency or self.payment_currency == self.currency:
                raise ValueError("FX_CONVERSION requires a different destination currency")
            if self.total_value is None or self.total_value <= 0:
                raise ValueError("FX_CONVERSION requires a positive source amount")
            if self.fx_rate is not None and self.fx_rate <= 0:
                raise ValueError("FX_CONVERSION rate must be positive")
            if self.gross_amount is not None and self.gross_amount < 0:
                raise ValueError("FX_CONVERSION destination amount cannot be negative")
            if self.portfolio_asset_id is not None or self.quantity is not None or self.unit_price is not None:
                raise ValueError("FX_CONVERSION cannot reference an asset or quantity")
            if self.cash_handling is not None or self.fiscal_exemption_id is not None:
                raise ValueError("FX_CONVERSION does not use cash handling or a fiscal exemption")
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
    cash_effect: CashEffect | None = None
    cash_pocket: str | None = None
    auto_generated: bool = False
    fx_conversion_id: int | None = None
    injection_transaction_id: int | None = None
    funding_transaction_ids: list[int] | None = None
    balance_snapshot_id: int | None = None
    balance_snapshot_timestamp: datetime | None = None
    balance_snapshot_amount: float | None = None
    attached_transaction_ids: list[int] | None = None
    model_config = ConfigDict(from_attributes=True)


class HeldAsset(BaseModel):
    """Quantity of one portfolio asset held by an entity at a point in time."""

    portfolio_asset_id: int
    quantity: float


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

    model_config = ConfigDict(extra="forbid")

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
    rate_missing: bool = False


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


class HistoricalAssetClassPoint(BaseModel):
    date: str
    asset_class: str
    value: float


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
