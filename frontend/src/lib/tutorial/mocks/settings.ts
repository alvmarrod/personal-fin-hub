const profiles = [
  {
    id: 1,
    name: 'Main Profile',
    has_password: false,
    default_fiscal_rule: 'spain',
  },
  {
    id: 2,
    name: 'Japan Portfolio',
    has_password: true,
    default_fiscal_rule: 'japan',
  },
];

const currencies = ['EUR', 'USD', 'JPY'];

const fiscalPeriods = [
  {
    id: 1,
    rule_key: 'spain',
    start_date: '2025-01-01',
    end_date: '2025-12-31',
  },
  {
    id: 2,
    rule_key: 'japan',
    start_date: '2024-01-01',
    end_date: null,
  },
];

const taxBases = [
  {
    id: 1,
    ruleset_key: 'spain',
    name: 'Spain savings',
    computation: 'progressive',
    flat_rate: null,
    year_start: null,
    categories: ['capital_gains', 'dividends'],
    rates: [
      { from_amount: 0, to_amount: 6000, rate: 0.19 },
      { from_amount: 6000, to_amount: 50000, rate: 0.21 },
      { from_amount: 50000, to_amount: null, rate: 0.23 },
    ],
  },
  {
    id: 2,
    ruleset_key: 'japan',
    name: 'Japan flat',
    computation: 'flat',
    flat_rate: 0.20315,
    year_start: null,
    categories: ['capital_gains', 'dividends'],
    rates: [],
  },
];

const taxDefinitions = [
  {
    id: 1,
    slug: 'stamp_duty',
    ruleset_key: 'spain',
    name: 'Tasa Tobin',
    rate: 0.002,
    year_start: null,
  },
  {
    id: 2,
    slug: 'foreign_withholding',
    ruleset_key: null,
    name: 'Foreign withholding',
    rate: null,
    year_start: null,
  },
];

const brokerFeeDefinitions = [
  { id: 1, name: 'Broker commission' },
  { id: 2, name: 'Transfer fee' },
];

const settingsMock = {
  '/profiles': profiles,
  '/currencies': currencies,
  '/fiscal-periods': fiscalPeriods,
  '/tax-bases': taxBases,
  '/tax-definitions': taxDefinitions,
  '/broker-fee-definitions': brokerFeeDefinitions,
};

export default settingsMock;