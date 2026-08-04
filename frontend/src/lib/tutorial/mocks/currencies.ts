const currencies = ['EUR', 'USD', 'JPY', 'GBP', 'CHF'];

const now = new Date();
const dates = [];
for (let i = 11; i >= 0; i--) {
  dates.push(new Date(now.getFullYear(), now.getMonth() - i, 1).toISOString().split('T')[0]);
}

const latestRaw = { EUR: 1.0, USD: 1.085, JPY: 162.5, GBP: 0.855, CHF: 0.975 };

const series = [
  { currency: 'EUR', values: [75872.32, 74210.5, 73110.2, 72980.9, 74120.0, 76340.8, 75210.3, 76800.1, 78120.4, 77550.7, 76210.9, 75872.32] },
  { currency: 'USD', values: [38000.0, 39200.5, 38800.2, 39500.0, 40120.8, 39850.3, 41020.6, 41800.1, 42550.0, 43100.4, 42980.2, 43550.0] },
  { currency: 'JPY', values: [1650000.0, 1680000.5, 1720000.2, 1705000.0, 1750000.8, 1780000.3, 1800000.6, 1765000.1, 1790000.4, 1810000.9, 1800000.2, 1800000.0] },
  { currency: 'GBP', values: [6500.0, 6800.5, 7000.2, 7200.0, 7400.8, 7600.3, 7800.6, 8000.1, 8100.4, 8250.9, 8150.2, 8200.0] },
  { currency: 'CHF', values: [6000.0, 6100.5, 6300.2, 6400.0, 6600.8, 6700.3, 6900.6, 7000.1, 7100.4, 7250.9, 7150.2, 7200.0] },
];

const rateChartLabels = dates;
const rateChartDatasets = [
  { label: 'EUR', data: [1.0, 1.003, 1.007, 1.004, 0.998, 1.002, 1.005, 1.001, 0.997, 1.0, 1.002, 1.0], axis: 'y', color: '#4263eb' },
  { label: 'USD', data: [1.085, 1.092, 1.088, 1.095, 1.09, 1.083, 1.087, 1.093, 1.089, 1.086, 1.084, 1.085], axis: 'y', color: '#2f9e44' },
  { label: 'JPY', data: [162.5, 163.2, 161.8, 162.9, 164.1, 163.5, 162.7, 161.9, 162.3, 163.0, 162.8, 162.5], axis: 'y', color: '#f08c00' },
  { label: 'GBP', data: [0.855, 0.858, 0.852, 0.86, 0.857, 0.854, 0.856, 0.861, 0.858, 0.855, 0.856, 0.855], axis: 'y', color: '#e03131' },
  { label: 'CHF', data: [0.975, 0.978, 0.972, 0.98, 0.977, 0.974, 0.976, 0.981, 0.978, 0.975, 0.976, 0.975], axis: 'y', color: '#845ef7' },
];

const currenciesMock = {
  '/currencies': currencies,
  '/currencies/holdings': {
    latest_raw: latestRaw,
    series,
    dates,
  },
  '/currencies/rate-chart': {
    labels: rateChartLabels,
    datasets: rateChartDatasets,
  },
};

export default currenciesMock;
