// The six fixed market-cycle states. `name` matches the engine's state names
// (doc/systems/market_cycle/state_engine.md §3) and is used to key transition
// source/target; display names come from i18n (`marketCycle.state.<id>`).

export const STATES = [
  { id: 1, name: 'Low Real Rates', tone: 'red', star: false },
  { id: 2, name: 'Rising Inflation', tone: 'amber', star: false },
  { id: 3, name: 'Hiking Cycle', tone: 'blue', star: false },
  { id: 4, name: 'High Real Rates', tone: 'green', star: false },
  { id: 5, name: 'First Rate Cut', tone: 'green', star: true },
  { id: 6, name: 'Cutting Cycle', tone: 'green', star: false },
];

export const STATE_NAMES = Object.fromEntries(STATES.map((s) => [s.id, s.name]));
export const NAME_TO_ID = Object.fromEntries(STATES.map((s) => [s.name, s.id]));

export function stateNameKey(id) {
  return `marketCycle.state.${id}`;
}
