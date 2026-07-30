# Tutorial System — High-Level Design

## Overview

An interactive, step-by-step tutorial system that guides users through each page of the application. Tutorials auto-play on first visit to a page and can be replayed on demand. Each page has its own tutorial definition. Tutorials are localized (en-US / es-ES) and can inject mock API data so widgets render with sample content even before the user has entered real data.

---

## Architecture

```
$lib/tutorial/
├── TutorialStore.svelte.ts     # global reactive state
├── TutorialOverlay.svelte      # driver.js wrapper, renders per-step
├── definitions/
│   ├── dashboard.ts            # step definitions for /dashboard
│   ├── transactions.ts         # step definitions for /transactions
│   ├── entities.ts             # etc.
│   └── index.ts                # registry of all page tutorials
├── mocks/
│   ├── dashboard.ts            # mock API interceptor for dashboard page
│   ├── transactions.ts         # mock interceptor for transactions page
│   └── ...
└── replay/
    └── ReplayButton.svelte     # single button component, placed on each page
```

---

## Component Breakdown

### 1. TutorialStore (`$lib/tutorial/TutorialStore.svelte.ts`)

```ts
// Reactive state (Svelte 5 runes)
let active: boolean = $state(false)           // is any tutorial currently playing?
let currentPage: string = $state('')          // which page definition is active
let currentStepIndex: number = $state(0)      // which step within that page
let shownPages: Set<string> = $state(new Set()) // pages the user has already seen

// Persistence
function init() {
  const saved = localStorage.getItem('tutorial_seen_pages')
  if (saved) shownPages = new Set(JSON.parse(saved))
}
function markPageSeen(page: string) {
  shownPages.add(page)
  localStorage.setItem('tutorial_seen_pages', JSON.stringify([...shownPages]))
}

// API
function start(page: string)        // begin tutorial for a page
function next()                      // advance to next step
function prev()                      // go back one step
function skip()                      // skip the rest of the tutorial
function finish()                    // mark page as seen, tear down
```

### 2. TutorialOverlay (`$lib/tutorial/TutorialOverlay.svelte`)

Imports `driver.js`. Receives a tutorial page definition (array of steps). Wraps driver.js lifecycle:

- On mount: initializes driver.js with steps, starts highlighting
- On step change: checks if step requires page navigation → pauses driver, tells user to click target, waits for `currentPage` store update → resumes
- On finish: calls `TutorialStore.finish()`, destroys driver.js instance

### 3. Page Definition (`$lib/tutorial/definitions/dashboard.ts`)

```ts
export default [
  {
    element: '.metric-grid',
    title: 'tutorial.dashboard.step1.title',
    body: 'tutorial.dashboard.step1.body',
    position: 'bottom',
  },
  {
    element: '.charts-grid',
    title: 'tutorial.dashboard.step2.title',
    body: 'tutorial.dashboard.step2.body',
  },
  {
    // Cross-page: tells user to navigate
    element: 'a[href="/transactions"]',
    title: 'tutorial.dashboard.stepLast.title',
    body: 'tutorial.dashboard.stepLast.body',
    action: 'navigate',              // special: waits for page change
    target_page: '/transactions',
  },
  // ...
]
```

Each step has:

- `element`: CSS selector for the highlighted DOM element
- `title` / `body`: i18n keys
- `position`: tooltip placement (`top`, `bottom`, `left`, `right`)
- `action` (optional): `navigate` → wait for page change before advancing
- `target_page` (optional): expected route after navigation

### 4. Mock Data (`$lib/tutorial/mocks/dashboard.ts`)

Intercepts API calls during tutorial mode. Each page mock exports a function that patches the `api` client:

```ts
export function enable() {
  // Intercept fetch calls matching dashboard analytics endpoints
  // Return pre-baked data so all widgets render with sample content
}
export function disable() { /* restore original fetch */ }
```

Mocks are activated when `TutorialStore.start()` is called for a page and deactivated on `TutorialStore.finish()`.

### 5. ReplayButton (`$lib/tutorial/replay/ReplayButton.svelte`)

Small button (question-mark icon, or label "Tutorial"). Placed in each page's header or a fixed corner. On click: calls `TutorialStore.start(currentPage)`. Does NOT reset the "already seen" flag — it replays silently without marking.

---

## Data Flow

```
User visits /dashboard for the first time
  → +page.svelte calls TutorialStore.init()
  → TutorialStore checks localStorage → not in shownPages
  → TutorialStore.start('dashboard')
    → Activates dashboard mock interceptor
    → Mounts TutorialOverlay with dashboard definition
    → driver.js highlights first element, shows tooltip

User clicks "Next" / progresses through steps
  → TutorialStore.next() → currentStepIndex++
  → TutorialOverlay updates driver.js

Step with action: 'navigate' reached
  → driver.js pauses
  → User clicks the sidebar link (natural navigation)
  → SvelteKit navigates to /transactions
  → Transactions +page.svelte mounts
  → Detects tutorial mode active (TutorialStore.active === true)
  → TutorialStore detects page changed to 'transactions'
  → TutorialOverlay switches to transactions definition, continues

User finishes (or clicks "Skip")
  → TutorialStore.finish()
  → Mark current page as seen in localStorage
  → Disable mock interceptor
  → Destroy TutorialOverlay
```

---

## Page Integration Pattern

Each page adds minimal glue code at the top:

```svelte
<script>
  import { onMount } from 'svelte';
  import tutorialStore from '$lib/tutorial/TutorialStore.svelte';
  import { t } from '$lib/i18n/index.svelte';
  import ReplayButton from '$lib/tutorial/replay/ReplayButton.svelte';
  import TutorialOverlay from '$lib/tutorial/TutorialOverlay.svelte';
  import dashboardDefinition from '$lib/tutorial/definitions/dashboard';

  // Normal page code ...

  onMount(() => {
    // If a tutorial is already active (cross-page navigation), resume it
    if (tutorialStore.active && tutorialStore.currentPage === 'dashboard') {
      tutorialStore.resume();
    }
    // Otherwise, if first visit, start tutorial
    else if (!tutorialStore.shownPages.has('dashboard')) {
      tutorialStore.start('dashboard', dashboardDefinition);
    }
  });
</script>

<!-- Page content ... -->

<ReplayButton page="dashboard" />
<TutorialOverlay definition={dashboardDefinition} />
```

---

## i18n Keys Structure

```
tutorial.dashboard.step1.title   = "Portfolio Overview"
tutorial.dashboard.step1.body    = "This card shows your total portfolio value..."
tutorial.dashboard.step2.title   = "Historical Chart"
tutorial.transactions.step1.title = "Transaction List"
// ...
```

Both `en.ts` and `es.ts` contain the full set.

---

## Implementation Roadmap

| Phase | Work | Effort |
|---|---|---|
| **1. Foundation** | Install `driver.js`, create `TutorialStore`, `TutorialOverlay`, `ReplayButton`. Wire into dashboard as proof-of-concept with 2-3 steps. | M |
| **2. Mock infrastructure** | `$lib/tutorial/mocks/` intercept pattern. Dashboard mock returning full sample data (portfolio, charts, allocation). | M |
| **3. Dashboard tutorial** | Full step definition for the dashboard page (~6-8 steps). Localized. | S |
| **4. Cross-page navigation** | TutorialStore detects page changes, TutorialOverlay switches definitions. Transactions page tutorial as second page. | M |
| **5. Remaining pages** | Step definitions for all 13 pages + settings. Mock data for each. | L |
| **6. Polish** | Smooth transitions, skip confirmation, replay from any step, "I'm done with all tutorials" dismiss. | S |

---

## Limitations

- **Navigation breakage**: If the user navigates away during a tutorial (e.g., browser back button) instead of clicking the sidebar link, the tutorial state may desync. Mitigation: TutorialOverlay listens to SvelteKit's `afterNavigate` to detect unexpected navigation and skip/restart.
- **Mock maintenance**: Mock data must match the real API response shapes. If API changes, mocks break silently. Mitigation: TypeScript types for mock data (matching Pydantic models), validation script.
- **Dynamic content**: Pages that depend on server-side state (e.g., filtered tables) may show different content in tutorial mode vs real mode. Mitigation: mock data provides a full realistic dataset; filters/searches disabled during tutorial.
- **Performance**: `driver.js` is lightweight (~5 KB gzipped, no deps). No significant impact.
