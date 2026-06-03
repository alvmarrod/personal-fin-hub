import unittest
from datetime import date, datetime

from pydantic import ValidationError

from models import (
    AssetClass,
    AssetType,
    Currency,
    DcaStatus,
    DistributionType,
    DividendType,
    EntityCreate,
    EntityResponse,
    EntityType,
    FeeNature,
    FeeType,
    FiscalExemptionCreate,
    FiscalExemptionResponse,
    Layer,
    MarketAsset,
    PeriodicityType,
    PortfolioAssetCreate,
    PortfolioAssetResponse,
    PriceCreate,
    PriceResponse,
    ScheduleCreate,
    ScheduleResponse,
    TrackingMode,
    TransactionCategory,
    TransactionCreate,
    TransactionFeeCreate,
    TransactionFeeResponse,
    TransactionResponse,
    TransactionTaxCreate,
    TransactionTaxResponse,
    TransactionType,
)


class TestEnums(unittest.TestCase):
    def test_asset_type_values(self):
        self.assertEqual(AssetType.STOCK.value, "STOCK")
        self.assertEqual(AssetType.INDEX_FUND.value, "INDEX FUND")
        self.assertEqual(AssetType.CRYPTO.value, "CRYPTO")

    def test_asset_class_values(self):
        self.assertEqual(AssetClass.CORP_FI.value, "corp FI")
        self.assertEqual(AssetClass.SOVEREIGN_FI.value, "Sovereign FI")
        self.assertEqual(AssetClass.MIX_FI.value, "mix FI")

    def test_distribution_type_values(self):
        self.assertEqual(DistributionType.ACCUMULATION.value, "accumulation")
        self.assertEqual(DistributionType.N_A.value, "N/A")

    def test_dca_status_values(self):
        self.assertEqual(DcaStatus.ONGOING.value, "ongoing")
        self.assertEqual(DcaStatus.PAUSED.value, "paused")

    def test_layer_values(self):
        self.assertEqual(Layer.CORE.value, "core")
        self.assertEqual(Layer.RESERVE.value, "reserve")

    def test_tracking_mode_values(self):
        self.assertEqual(TrackingMode.AUTO.value, "auto")
        self.assertEqual(TrackingMode.MANUAL.value, "manual")

    def test_transaction_type_values(self):
        self.assertEqual(TransactionType.INVESTMENT_BUY.value, "INVESTMENT_BUY")
        self.assertEqual(TransactionType.DIVIDEND.value, "DIVIDEND")

    def test_transaction_category_values(self):
        self.assertEqual(TransactionCategory.NORMAL.value, "NORMAL")
        self.assertEqual(TransactionCategory.DCA.value, "DCA")
        self.assertEqual(TransactionCategory.REBALANCE.value, "REBALANCE")

    def test_dividend_type_values(self):
        self.assertEqual(DividendType.REGULAR.value, "regular")
        self.assertEqual(DividendType.SPECIAL.value, "special")

    def test_fee_type_values(self):
        self.assertEqual(FeeType.BROKER.value, "BROKER")
        self.assertEqual(FeeType.FX.value, "FX")

    def test_fee_nature_values(self):
        self.assertEqual(FeeNature.FIXED.value, "FIXED")
        self.assertEqual(FeeNature.PERCENTAGE.value, "PERCENTAGE")
        self.assertEqual(FeeNature.BOTH.value, "BOTH")
        self.assertEqual(FeeNature.MIN.value, "MIN")

    def test_entity_type_values(self):
        self.assertEqual(EntityType.BROKER.value, "BROKER")
        self.assertEqual(EntityType.BANK.value, "BANK")

    def test_periodicity_type_values(self):
        self.assertEqual(PeriodicityType.ONE_OFF.value, "ONE_OFF")
        self.assertEqual(PeriodicityType.MONTHLY.value, "MONTHLY")
        self.assertEqual(PeriodicityType.CUSTOM.value, "CUSTOM")

    def test_enum_string_coercion(self):
        self.assertEqual(TransactionType("INVESTMENT_SELL"), TransactionType.INVESTMENT_SELL)
        self.assertEqual(AssetType("ETF"), AssetType.ETF)

    def test_enum_rejects_invalid(self):
        with self.assertRaises(ValueError):
            AssetType("INVALID")


class TestEntityModels(unittest.TestCase):
    def test_create_minimal(self):
        entity = EntityCreate(name="IBKR", entity_type="BROKER")
        self.assertEqual(entity.name, "IBKR")
        self.assertEqual(entity.entity_type, EntityType.BROKER)
        self.assertIsNone(entity.country)
        self.assertIsNone(entity.description)

    def test_create_all_fields(self):
        entity = EntityCreate(
            name="Interactive Brokers",
            entity_type=EntityType.BROKER,
            country="US",
            description="Main brokerage account",
        )
        self.assertEqual(entity.name, "Interactive Brokers")
        self.assertEqual(entity.country, "US")
        self.assertEqual(entity.description, "Main brokerage account")

    def test_create_string_enum_coercion(self):
        entity = EntityCreate(name="Test", entity_type="BANK")
        self.assertEqual(entity.entity_type, EntityType.BANK)

    def test_create_missing_required(self):
        with self.assertRaises(ValidationError):
            EntityCreate(name="IBKR")

    def test_response_requires_id(self):
        with self.assertRaises(ValidationError):
            EntityResponse(name="IBKR", entity_type="BROKER", country="US")

    def test_response_all_fields(self):
        entity = EntityResponse(
            id=1,
            name="IBKR",
            entity_type="BROKER",
            country="US",
            description="desc",
        )
        self.assertEqual(entity.id, 1)
        self.assertEqual(entity.name, "IBKR")
        self.assertEqual(entity.description, "desc")

    def test_response_from_attributes_config(self):
        self.assertTrue(
            EntityResponse.model_config.get("from_attributes"),
        )


class TestFiscalExemptionModels(unittest.TestCase):
    def test_create_minimal(self):
        fe = FiscalExemptionCreate(exemption_type="NISA")
        self.assertEqual(fe.exemption_type, "NISA")
        self.assertEqual(fe.exemption_amount, 0)
        self.assertEqual(fe.exemption_rate, 100)
        self.assertIsNone(fe.description)
        self.assertIsNone(fe.exemption_rate_limit)

    def test_create_custom_values(self):
        fe = FiscalExemptionCreate(
            exemption_type="ISA",
            description="UK ISA",
            exemption_amount=20000,
            exemption_rate=0,
            exemption_rate_limit=100,
        )
        self.assertEqual(fe.exemption_amount, 20000)
        self.assertEqual(fe.exemption_rate, 0)
        self.assertEqual(fe.exemption_rate_limit, 100)

    def test_response_requires_id(self):
        with self.assertRaises(ValidationError):
            FiscalExemptionResponse(exemption_type="NISA")

    def test_response_all_fields(self):
        fe = FiscalExemptionResponse(
            id=1,
            exemption_type="NISA",
            exemption_amount=10000,
        )
        self.assertEqual(fe.id, 1)


class TestMarketAssetModel(unittest.TestCase):
    def test_minimal(self):
        ma = MarketAsset(
            market_code="AAPL.US",
            asset_type="STOCK",
            currency_code="USD",
        )
        self.assertEqual(ma.market_code, "AAPL.US")
        self.assertEqual(ma.asset_type, AssetType.STOCK)
        self.assertIsNone(ma.ticker)
        self.assertIsNone(ma.asset_class)
        self.assertIsNone(ma.name)
        self.assertIsNone(ma.exchange)

    def test_all_fields(self):
        ma = MarketAsset(
            market_code="VWCE.DE",
            ticker="VWCE.DE",
            asset_type="ETF",
            asset_class="VI",
            currency_code="EUR",
            name="Vanguard FTSE All-World UCITS ETF",
            exchange="XETRA",
        )
        self.assertEqual(ma.asset_class, AssetClass.VI)
        self.assertEqual(ma.name, "Vanguard FTSE All-World UCITS ETF")

    def test_spaced_asset_class(self):
        ma = MarketAsset(
            market_code="TEST",
            asset_type="STOCK",
            asset_class="corp FI",
            currency_code="USD",
        )
        self.assertEqual(ma.asset_class, AssetClass.CORP_FI)

    def test_invalid_asset_type(self):
        with self.assertRaises(ValidationError):
            MarketAsset(
                market_code="X",
                asset_type="INVALID",
                currency_code="USD",
            )

    def test_missing_required(self):
        with self.assertRaises(ValidationError):
            MarketAsset(market_code="X")

    def test_from_attributes_config(self):
        self.assertTrue(MarketAsset.model_config.get("from_attributes"))


class TestPortfolioAssetModels(unittest.TestCase):
    def test_create_minimal(self):
        pa = PortfolioAssetCreate(market_code="AAPL.US")
        self.assertEqual(pa.market_code, "AAPL.US")
        self.assertFalse(pa.tactic)
        self.assertEqual(pa.tracking_mode, TrackingMode.AUTO)
        self.assertTrue(pa.is_active)
        self.assertIsNone(pa.layer)
        self.assertIsNone(pa.notes)

    def test_create_all_fields(self):
        pa = PortfolioAssetCreate(
            market_code="VWCE.DE",
            distribution_type="accumulation",
            dca_status="ongoing",
            layer="core",
            tactic=True,
            desired_weight=50.0,
            ter=0.22,
            tracking_mode="manual",
            current_value_manual=10000.0,
            is_active=False,
            closing_date=date(2025, 12, 31),
            purchase_date=date(2025, 1, 1),
            notes="Main ETF",
        )
        self.assertEqual(pa.distribution_type, DistributionType.ACCUMULATION)
        self.assertEqual(pa.dca_status, DcaStatus.ONGOING)
        self.assertEqual(pa.layer, Layer.CORE)
        self.assertTrue(pa.tactic)
        self.assertEqual(pa.ter, 0.22)
        self.assertEqual(pa.tracking_mode, TrackingMode.MANUAL)
        self.assertFalse(pa.is_active)

    def test_response_requires_id(self):
        with self.assertRaises(ValidationError):
            PortfolioAssetResponse(market_code="AAPL.US")

    def test_response_from_attributes_config(self):
        self.assertTrue(PortfolioAssetResponse.model_config.get("from_attributes"))


class TestTransactionModels(unittest.TestCase):
    def test_create_minimal(self):
        t = TransactionCreate(
            timestamp="2025-09-17T09:00:00Z",
            type="INVESTMENT_BUY",
            entity_id=1,
            currency="USD",
        )
        self.assertEqual(t.type, TransactionType.INVESTMENT_BUY)
        self.assertEqual(t.entity_id, 1)
        self.assertIsNone(t.portfolio_asset_id)
        self.assertIsNone(t.quantity)
        self.assertIsNone(t.unit_price)
        self.assertIsNone(t.dividend_type)
        self.assertIsNone(t.payment_currency)

    def test_create_investment_buy(self):
        t = TransactionCreate(
            timestamp="2025-09-17T09:00:00Z",
            type="INVESTMENT_BUY",
            entity_id=1,
            portfolio_asset_id=10,
            quantity=10,
            unit_price=100.5,
            currency="USD",
            payment_currency="JPY",
            fx_rate=150.5,
        )
        self.assertEqual(t.quantity, 10)
        self.assertEqual(t.unit_price, 100.5)
        self.assertEqual(t.payment_currency, "JPY")
        self.assertEqual(t.fx_rate, 150.5)

    def test_create_dividend(self):
        t = TransactionCreate(
            timestamp="2025-09-17T09:00:00Z",
            type="DIVIDEND",
            entity_id=1,
            portfolio_asset_id=10,
            quantity=100,
            unit_price=0.25,
            currency="USD",
            dividend_type="regular",
            record_date="2025-09-01",
            payment_date="2025-09-15",
            gross_amount=25.0,
            dividend_currency="USD",
            dividend_payment_currency="JPY",
            dividend_fx_rate=150.5,
        )
        self.assertEqual(t.dividend_type, DividendType.REGULAR)
        self.assertEqual(t.gross_amount, 25.0)

    def test_create_total_value_default_none(self):
        t = TransactionCreate(
            timestamp="2025-09-17T09:00:00Z",
            type="MONEY_IN",
            entity_id=1,
            currency="USD",
        )
        self.assertIsNone(t.total_value)

    def test_create_missing_required(self):
        with self.assertRaises(ValidationError):
            TransactionCreate(type="MONEY_IN", entity_id=1)

    def test_response_has_total_value(self):
        t = TransactionResponse(
            id=1,
            timestamp="2025-09-17T09:00:00Z",
            type="INVESTMENT_BUY",
            entity_id=1,
            quantity=10,
            unit_price=100.5,
            currency="USD",
            total_value=1005.0,
        )
        self.assertEqual(t.total_value, 1005.0)

    def test_response_total_value_none(self):
        t = TransactionResponse(
            id=1,
            timestamp="2025-09-17T09:00:00Z",
            type="MONEY_IN",
            entity_id=1,
            currency="USD",
            total_value=None,
        )
        self.assertIsNone(t.total_value)

    def test_response_requires_id(self):
        with self.assertRaises(ValidationError):
            TransactionResponse(
                timestamp="2025-09-17T09:00:00Z",
                type="MONEY_IN",
                entity_id=1,
                currency="USD",
            )

    def test_response_from_attributes_config(self):
        self.assertTrue(TransactionResponse.model_config.get("from_attributes"))

    def test_create_invalid_type(self):
        with self.assertRaises(ValidationError):
            TransactionCreate(
                timestamp="2025-09-17T09:00:00Z",
                type="INVALID",
                entity_id=1,
                currency="USD",
            )


class TestTransactionFeeModels(unittest.TestCase):
    def test_create_minimal(self):
        tf = TransactionFeeCreate(
            transaction_id=1,
            fee_type="BROKER",
            nature="FIXED",
            currency="USD",
        )
        self.assertEqual(tf.fixed_amount, 0.0)
        self.assertEqual(tf.percentage, 0.0)

    def test_create_fixed_fee(self):
        tf = TransactionFeeCreate(
            transaction_id=1,
            fee_type="BROKER",
            nature="FIXED",
            fixed_amount=10.0,
            currency="USD",
        )
        self.assertEqual(tf.fixed_amount, 10.0)

    def test_create_percentage_fee(self):
        tf = TransactionFeeCreate(
            transaction_id=1,
            fee_type="PLATFORM",
            nature="PERCENTAGE",
            percentage=0.05,
            currency="USD",
        )
        self.assertEqual(tf.percentage, 0.05)

    def test_response_requires_id(self):
        with self.assertRaises(ValidationError):
            TransactionFeeResponse(
                transaction_id=1,
                fee_type="BROKER",
                nature="FIXED",
                currency="USD",
            )

    def test_response_from_attributes_config(self):
        self.assertTrue(TransactionFeeResponse.model_config.get("from_attributes"))


class TestTransactionTaxModels(unittest.TestCase):
    def test_create_minimal(self):
        tt = TransactionTaxCreate(
            transaction_id=1,
            tax_type="STAMP_DUTY",
            tax_amount=1.0,
            currency="USD",
        )
        self.assertEqual(tt.tax_type, "STAMP_DUTY")
        self.assertEqual(tt.tax_amount, 1.0)
        self.assertIsNone(tt.tax_rate)

    def test_create_withholding(self):
        tt = TransactionTaxCreate(
            transaction_id=1,
            tax_type="WITHHOLDING",
            tax_rate=15.0,
            tax_amount=3.75,
            currency="USD",
        )
        self.assertEqual(tt.tax_rate, 15.0)
        self.assertEqual(tt.tax_amount, 3.75)

    def test_response_requires_id(self):
        with self.assertRaises(ValidationError):
            TransactionTaxResponse(
                transaction_id=1,
                tax_type="STAMP_DUTY",
                tax_amount=1.0,
                currency="USD",
            )

    def test_response_from_attributes_config(self):
        self.assertTrue(TransactionTaxResponse.model_config.get("from_attributes"))


class TestPriceModels(unittest.TestCase):
    def test_create_minimal(self):
        p = PriceCreate(
            market_code="AAPL.US",
            timestamp="2025-09-17T09:00:00Z",
            price=150.25,
        )
        self.assertEqual(p.price, 150.25)
        self.assertIsNone(p.provider)

    def test_create_with_provider(self):
        p = PriceCreate(
            market_code="AAPL.US",
            timestamp="2025-09-17T09:00:00Z",
            price=150.25,
            provider="MARKET_API",
        )
        self.assertEqual(p.provider, "MARKET_API")

    def test_create_missing_required(self):
        with self.assertRaises(ValidationError):
            PriceCreate(market_code="AAPL.US")

    def test_response_requires_id(self):
        with self.assertRaises(ValidationError):
            PriceResponse(
                market_code="AAPL.US",
                timestamp="2025-09-17T09:00:00Z",
                price=150.25,
            )

    def test_response_from_attributes_config(self):
        self.assertTrue(PriceResponse.model_config.get("from_attributes"))


class TestScheduleModels(unittest.TestCase):
    def test_create_minimal(self):
        s = ScheduleCreate(
            description="Monthly ETF contribution",
            start_date="2025-01-01",
            periodicity_type="MONTHLY",
        )
        self.assertEqual(s.description, "Monthly ETF contribution")
        self.assertIsInstance(s.start_date, date)
        self.assertIsNone(s.end_date)
        self.assertIsNone(s.custom_cron)
        self.assertIsNone(s.linked_transaction_id)

    def test_create_one_off(self):
        s = ScheduleCreate(
            description="One-time buy",
            start_date="2025-06-01",
            end_date="2025-06-01",
            periodicity_type="ONE_OFF",
        )
        self.assertEqual(s.periodicity_type, PeriodicityType.ONE_OFF)

    def test_create_with_linked_transaction(self):
        s = ScheduleCreate(
            description="Linked schedule",
            start_date="2025-01-01",
            periodicity_type="MONTHLY",
            linked_transaction_id=42,
        )
        self.assertEqual(s.linked_transaction_id, 42)

    def test_create_missing_required(self):
        with self.assertRaises(ValidationError):
            ScheduleCreate(description="Test")

    def test_response_requires_id(self):
        with self.assertRaises(ValidationError):
            ScheduleResponse(
                description="Test",
                start_date="2025-01-01",
                periodicity_type="MONTHLY",
            )

    def test_response_from_attributes_config(self):
        self.assertTrue(ScheduleResponse.model_config.get("from_attributes"))


class TestCurrencyModel(unittest.TestCase):
    def test_minimal(self):
        c = Currency(
            code="JPY",
            base_code="USD",
            rate=150.5,
            timestamp="2025-09-17T09:00:00Z",
        )
        self.assertEqual(c.code, "JPY")
        self.assertEqual(c.base_code, "USD")
        self.assertEqual(c.rate, 150.5)

    def test_missing_required(self):
        with self.assertRaises(ValidationError):
            Currency(code="JPY", base_code="USD")

    def test_from_attributes_config(self):
        self.assertTrue(Currency.model_config.get("from_attributes"))


if __name__ == "__main__":
    unittest.main()
