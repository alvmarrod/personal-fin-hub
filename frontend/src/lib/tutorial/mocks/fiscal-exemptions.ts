const exemptions = [
  {
    id: 1,
    exemption_type: 'Dividend Exemption',
    description: 'Ireland DWT exemption for accumulating ETFs',
    exemption_amount: null,
    exemption_rate: 100,
    exemption_rate_limit: 5000,
  },
  {
    id: 2,
    exemption_type: 'Interest Allowance',
    description: 'Personal savings allowance under Spanish tax law',
    exemption_amount: 1000,
    exemption_rate: 100,
    exemption_rate_limit: null,
  },
  {
    id: 3,
    exemption_type: 'US Dividend Treaty',
    description: 'Reduced withholding under US-ES tax treaty (15% instead of 30%)',
    exemption_amount: null,
    exemption_rate: 50,
    exemption_rate_limit: null,
  },
  {
    id: 4,
    exemption_type: 'Capital Gains Allowance',
    description: 'Annual tax-free allowance for realized gains',
    exemption_amount: 2000,
    exemption_rate: 100,
    exemption_rate_limit: null,
  },
];

const fiscalExemptionsMock = {
  '/fiscal-exemptions': exemptions,
};

export default fiscalExemptionsMock;
