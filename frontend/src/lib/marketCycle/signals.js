// Display helpers for the market-cycle signal detail.
//
// The engine sends structured codes and numbers (state_engine.md §9); the view
// localizes the labels and formats the arithmetic. No economic logic lives
// here — thresholds and conditions arrive already evaluated from the engine.
// Every helper takes the i18n `t` function so this module stays pure.

const KPI_LABEL_KEY = {
  inflation_rate: 'marketCycle.metric.inflation_rate',
  inflation_rate_trend: 'marketCycle.metric.inflation_rate_trend',
  policy_rate: 'marketCycle.metric.policy_rate',
  policy_rate_trend: 'marketCycle.metric.policy_rate_trend',
  real_interest_rate: 'marketCycle.metric.real_interest_rate',
  real_interest_rate_trend: 'marketCycle.metric.real_interest_rate_trend',
  state: 'marketCycle.metric.state',
};

const OP_LABEL_KEY = {
  '>': 'marketCycle.op.gt',
  '<': 'marketCycle.op.lt',
  '==': 'marketCycle.op.eq',
  '!=': 'marketCycle.op.neq',
  in: 'marketCycle.op.in',
  none_within: 'marketCycle.op.none_within',
};

const FORMULA_KEY = {
  real_rate: 'marketCycle.formula.real_rate',
  slope_step: 'marketCycle.formula.slope_step',
};

export function metricLabel(kpi, t) {
  const key = KPI_LABEL_KEY[kpi];
  return key ? t(key) : kpi;
}

export function directionLabel(value, t) {
  return t(`marketCycle.direction.${value}`);
}

export function opLabel(op, t) {
  const key = OP_LABEL_KEY[op];
  return key ? t(key) : op;
}

/** A value with its unit, or a localized direction; `—` when absent. */
export function formatValue(value, unit, t) {
  if (value === null || value === undefined) return '\u2014';
  if (typeof value === 'number') return `${value.toFixed(2)}${unit ?? ''}`;
  return directionLabel(value, t);
}

/** The arithmetic behind a derived value, e.g. `4.00% − 4.00% = 0.00%`. */
export function formatFormula(formula, t) {
  if (!formula) return '';
  const key = FORMULA_KEY[formula.code];
  if (!key) return '';
  if (formula.code === 'real_rate') {
    const [a, b] = formula.inputs ?? [];
    return t(key, {
      a: formatValue(a?.value, '%', t),
      b: formatValue(b?.value, '%', t),
      result: formatValue(formula.result, '%', t),
    });
  }
  const [input] = formula.inputs ?? [];
  return t(key, {
    prev: formatValue(input?.prev_value, '%', t),
    curr: formatValue(input?.value, '%', t),
  });
}

/** The condition a signal compares against, e.g. `above 1.00%`. */
export function describeCondition(condition, t) {
  if (!condition) return '';
  const { op, target, window } = condition;
  if (op === 'none_within') {
    return t('marketCycle.op.none_within', { target: directionLabel(target, t), window });
  }
  if (Array.isArray(target)) return `${opLabel(op, t)} ${target.join(', ')}`;
  if (typeof target === 'number') return `${opLabel(op, t)} ${target.toFixed(2)}%`;
  if (typeof target === 'string') return `${opLabel(op, t)} ${directionLabel(target, t)}`;
  return opLabel(op, t);
}

/** One line for a top-level signal (threshold or direction). */
export function describeSignal(signal, t) {
  const label = metricLabel(signal.metric, t);
  if (signal.kind === 'threshold') {
    return `${label}: ${formatFormula(signal.formula, t)} \u00b7 ${describeCondition(signal.condition, t)}`;
  }
  const value = formatValue(signal.value, null, t);
  const formula = formatFormula(signal.formula, t);
  const extra = formula ? ` (${formula})` : '';
  return `${label}: ${value} \u00b7 ${t('marketCycle.needs')} ${describeCondition(signal.condition, t)}${extra}`;
}

/** One line for a sub-condition of a combination signal. */
export function describePart(part, t) {
  if (part.kind === 'state') {
    return `${metricLabel('state', t)}: ${part.value} \u00b7 ${describeCondition(part.condition, t)}`;
  }
  if (part.kind === 'history') {
    return describeCondition(part.condition, t);
  }
  const label = metricLabel(part.metric, t);
  const value = formatValue(part.value, null, t);
  const formula = formatFormula(part.formula, t);
  const extra = formula ? ` (${formula})` : '';
  return `${label}: ${value}${extra}`;
}
