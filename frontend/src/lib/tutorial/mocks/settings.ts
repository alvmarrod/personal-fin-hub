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

const taxRates = [
  {
    id: 1,
    ruleset_key: 'spain',
    category: 'capital_gains',
    from_amount: 0,
    to_amount: 6000,
    rate: 0.19,
    year_start: null,
  },
  {
    id: 2,
    ruleset_key: 'spain',
    category: 'capital_gains',
    from_amount: 6000,
    to_amount: 50000,
    rate: 0.21,
    year_start: null,
  },
  {
    id: 3,
    ruleset_key: 'spain',
    category: 'dividends',
    from_amount: 0,
    to_amount: 6000,
    rate: 0.19,
    year_start: null,
  },
  {
    id: 4,
    ruleset_key: 'japan',
    category: 'capital_gains',
    from_amount: 0,
    to_amount: null,
    rate: 0.20315,
    year_start: null,
  },
  {
    id: 5,
    ruleset_key: 'japan',
    category: 'dividends',
    from_amount: 0,
    to_amount: null,
    rate: 0.20315,
    year_start: null,
  },
];

const settingsMock = {
  '/profiles': profiles,
  '/currencies': currencies,
  '/fiscal-periods': fiscalPeriods,
  '/tax-rates': taxRates,
};

export default settingsMock;