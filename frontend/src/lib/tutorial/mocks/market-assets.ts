const marketAssets = [
  {
    market_code: 'IWDA.AS',
    name: 'iShares Core MSCI World UCITS ETF',
    asset_type: 'ETF',
    currency_code: 'EUR',
    country: 'IE',
    isin: 'IE00B4L5Y983',
  },
  {
    market_code: 'EMIM.AS',
    name: 'iShares Core MSCI EM IMI UCITS ETF',
    asset_type: 'ETF',
    currency_code: 'EUR',
    country: 'IE',
    isin: 'IE00BKM4GZ66',
  },
  {
    market_code: 'VWCE.DE',
    name: 'Vanguard FTSE All-World UCITS ETF',
    asset_type: 'ETF',
    currency_code: 'EUR',
    country: 'IE',
    isin: 'IE00BK5BQT80',
  },
  {
    market_code: 'AAPL.US',
    name: 'Apple Inc.',
    asset_type: 'STOCK',
    currency_code: 'USD',
    country: 'US',
    isin: 'US0378331005',
  },
  {
    market_code: 'NVDA.US',
    name: 'NVIDIA Corporation',
    asset_type: 'STOCK',
    currency_code: 'USD',
    country: 'US',
    isin: 'US67066G1040',
  },
  {
    market_code: 'SAP.DE',
    name: 'SAP SE',
    asset_type: 'STOCK',
    currency_code: 'EUR',
    country: 'DE',
    isin: 'DE0007164600',
  },
  {
    market_code: 'AGGU.L',
    name: 'iShares Core Global Aggregate Bond UCITS ETF',
    asset_type: 'BOND',
    currency_code: 'USD',
    country: 'IE',
    isin: 'IE00BDBRDM35',
  },
];

const currencies = ['EUR', 'USD', 'JPY', 'GBP'];

const marketAssetsMock = {
  '/market-assets': marketAssets,
  '/currencies': currencies,
};

export default marketAssetsMock;
