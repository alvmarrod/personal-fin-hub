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
    linked_transaction_id: int | None = None


class ScheduleResponse(BaseModel):
    id: int
    description: str
    start_date: date
    end_date: date | None = None
    periodicity_type: PeriodicityType
    custom_cron: str | None = None
    linked_transaction_id: int | None = None
    model_config = ConfigDict(from_attributes=True)
