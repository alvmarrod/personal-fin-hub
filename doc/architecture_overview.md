# Architecture Overview

## Technology Stack
- **Runtime:** Python 3.13
- **Frontend:** Svelte 5
- **Package Manager:** Bun (frontend)
- **Database:** SQLite (denormalized)
- **Scheduler:** APScheduler (in-process)
- **Backend Framework:** FastAPI

## Architecture Pattern
Layered architecture: Routes → Services → Models → Database

## Component Diagram

```
+-------------------------------------------------------------+
|                      Frontend (Svelte 5)                   |
|                    (Bun + Vite dev server)                 |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                    FastAPI Backend (Layered)                |
+-------------------------------------------------------------+
|  Routes         |  Services      |  Models    |  Scheduler  |
|  /transactions |  currency_svc  |  pydantic  |  APScheduler|
|  /entities     |  transaction_svc            |             |
|  /assets       |  analytics_svc              |             |
|  /schedules    |  api_client                 |             |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|  SQLite (denormalized)                                     |
|  Tables: transactions, assets, entities, currencies,       |
|          prices, schedules, transaction_fees,              |
|          transaction_taxes                                  |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                   External Market API                       |
|           (http://<host>:<port>/symbol/<tag>)              |
+-------------------------------------------------------------+
```

## Component Responsibilities

| Component | Responsibility |
|-----------|-----------------|
| `routes/` | HTTP endpoints, request validation, response serialization |
| `services/` | Business logic, calculations, API client calls |
| `models/` | Pydantic schemas, database models |
| `scheduler/` | APScheduler job management for recurring operations |
| `db/` | SQLite connection, migrations, queries |

## Data Flow

1. Client -> FastAPI route -> Service -> Database
2. Scheduler -> APScheduler -> Service -> Create transaction
3. Analytics -> API Client -> External Market API -> Cache prices -> Serve to frontend