# Project Plan

**Status**: In Progress
**Created**: 2026-10-01
**Mode**: NEW

---

## 1. Project Overview

**Goal**: Build a Vietnamese-language stock screening dashboard that demonstrates mock OHLCV analysis for roughly 15 stocks across 100 sessions, compares Trend Following vs Mean Reversion strategies, and highlights capital-sizing guidance with fixed 20% and Quarter-Kelly alternatives. The project is designed so that every module is independently testable.

**App Type**: SPA + API

**API Login**: No

**Mode**: NEW

**Deployment Plan**: No deployment plan found

---

## 2. Flask Stock Screening Backend — backend

| Component | Technology |
|-----------|-----------|
| **Language** | Python |
| **Runtime** | CPython |
| **Package Manager** | pip |
| **Test Runner** | pytest |
| **Mocking Library** | unittest.mock |
| **Test Command** | pytest |
| **Orchestration** | docker-compose |

> **Language vs Runtime**: `Language` is the source language the user picked in this service's `language` question. `Runtime` is the execution runtime — default `Node` for TypeScript/JavaScript, `CPython` for Python, `.NET` for C#. Only deviate from the default (e.g. `Bun`, `Deno`, `PyPy`) when the user explicitly asks. **Package Manager and Test Runner are language-dependent** — match them to this service's Language (e.g. C# → `dotnet (NuGet)` + `xUnit`/`NUnit`/`MSTest`). The `Orchestration` row is recorded for the scaffold step but hidden in the plan UI — always keep it set to `docker-compose`.

---

## 3. Vietnamese Stock Screening Dashboard — frontend

| Component | Technology |
|-----------|-----------|
| **Language** | JavaScript |
| **Framework** | Bootstrap 5 with Flask/Jinja server-rendered templates and vanilla JavaScript |
| **Package Manager** | npm |
| **Test Runner** | vitest |
| **Mocking Library** | vi.mock |
| **Test Command** | npm test |

---

## 4. Services Required

| Azure Service | Role in App | Environment Variable | Default Value (Local) | Classification |
|---------------|------------|---------------------|----------------------|----------------|
| Azure App Service | Host the Flask backend and serve the dashboard UI | `PORT` | `5000` | Essential |
| Azure Monitor / Application Insights | Capture runtime logs and health signals for the screening app | `APPLICATIONINSIGHTS_CONNECTION_STRING` | `""` | Recommended |

---

## 5. Prerequisites

Identify the required tools, then inventory them by following [prerequisites.md](../shared-references/prerequisites.md). Always produce **both** groups — `### Run` and `### Debug` — as two sub-tables under this section. The plan webview shows the Run group always and the Debug group only when the user turns on the Autopilot toggle, so do not omit either group yourself.

### Run

| Tool | Service(s) | Installed | Version |
|------|------------|-----------|---------|
| Python 3 | Flask Stock Screening Backend | ✅ | 3.14.2 |
| pip | Flask Stock Screening Backend | ✅ | 26.2.1 |
| Node.js | Vietnamese Stock Screening Dashboard | ✅ | 24.21.0 |
| npm | Vietnamese Stock Screening Dashboard | ✅ | 11.19.0 |
| Docker | * | ✅ | 29.8.0-1 |
| Docker Compose | * | ✅ | v5.5.1 |
| Git | * | ✅ | 2.55.0 |

### Debug

| Tool | Service(s) | Installed | Version |
|------|------------|-----------|---------|
| ms-python.python | Flask Stock Screening Backend | ✅ | detected |
| ms-azuretools.vscode-docker | * | ✅ | detected |

---

## 6. Design System & UI

**Component Library**: Pico.css
**Style Direction**: Modern dark trading dashboard with data-dense cards, strong contrast, and quick scanning for stock signals, recommendations, and capital-allocation guidance.
**Typography**: Inter, system-ui

### Color Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `primary` | `#22c55e` | Brand color for active strategy tabs, positive performance, and primary actions |
| `accent` | `#f59e0b` | Secondary highlights for allocations, watchlist momentum, and attention cues |
| `surface` | `#0f172a` | Page and card backgrounds for the dark trading console |
| `text` | `#e2e8f0` | Main body text for stock names, metrics, and descriptions |
| `muted` | `#94a3b8` | Secondary labels, timestamps, and non-critical statuses |
| `border` | `#334155` | Dividers, inputs, and card borders |

### Pages

| Page | Route | Purpose | Layout |
|------|-------|---------|--------|
| Dashboard | `/` | Monitor strategy scores, stock screening results, and overall demo performance | `header + nav + hero + card-list + table` |
| Recommendations | `/recommendations` | Review the top-ranked stock ideas and their recommended capital sizing | `header + nav + table + action-bar` |

### Sample Content

```
Dashboard — stock signals:
| Ticker | Strategy | Signal | Momentum | Status |
| VIC    | Trend Following | Bullish | +6.4% | Strong |
| FPT    | Mean Reversion | Reversal | +2.9% | Watch |
| HPG    | Trend Following | Bullish | +5.1% | Strong |
| MWG    | Mean Reversion | Oversold | +3.8% | Candidate |
| TCB    | Trend Following | Neutral | +1.1% | Monitor |

Recommendations — equity ideas:
| Rank | Ticker | Fixed 20% | Quarter-Kelly | Thesis |
| 1    | VIC    | 12.8%      | 18.5%         | Strong trend continuation with stable liquidity |
| 2    | FPT    | 11.1%      | 16.0%         | Quality momentum with improving earnings trend |
| 3    | HPG    | 9.6%       | 13.8%         | Price strength after a healthy breakout |
| 4    | MWG    | 8.4%       | 12.2%         | Mean reversion setup with improving operating signals |
| 5    | TCB    | 7.8%       | 10.9%         | Balanced risk-adjusted opportunity |

Demo note: All prices, OHLCV values, and portfolio outputs are mock data for educational screening only.
```

---

## 7. Project Structure

```
VnStockFilterAndTrading/
├── .azure/
│   ├── project-plan.md
│   └── .preview-temp/
│       ├── manifest.json
│       └── theme.css
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── routes.py
│   ├── data/
│   │   └── mock_market_data.py
│   ├── strategies/
│   │   ├── trend_following.py
│   │   └── mean_reversion.py
│   ├── services/
│   │   └── screening_service.py
│   └── templates/
│       ├── base.html
│       ├── dashboard.html
│       └── recommendations.html
├── tests/
│   ├── test_strategies.py
│   ├── test_screening_service.py
│   └── test_routes.py
├── README.md
├── requirements.txt
├── .gitignore
└── run.py
```

---

## 8. Route Definitions

| # | Method | Path | Description | Request Body | Response Body | Status Codes |
|---|--------|------|-------------|-------------|--------------|-------------|
| 1 | GET | `/api/health` | Health check for the Flask backend | — | `{ status, services }` | 200, 503 |
| 2 | GET | `/api/overview` | Return the latest mock screening summary for all tracked stocks | — | `{ generated_at, symbols, strategy_summary, total_positions }` | 200 |
| 3 | GET | `/api/recommendations` | Retrieve the ranked investment ideas and position-sizing suggestions | — | `{ recommendations, fixed_allocation, quarter_kelly }` | 200 |
| 4 | GET | `/api/strategy/:strategy` | Return trend-following or mean-reversion results for one strategy view | — | `{ strategy, rows, metrics }` | 200 |

---

## 9. Next Steps

1. Run **azure-project-scaffold** to execute this plan
2. Run **azure-project-integrate** to wire the frontend to live data, smoke-test the backend, and create the migrations
3. Run **azure-debug-plan** → **azure-debug-generate** for Docker emulators and VS Code debugging
4. Run the **azure-deploy** agent when ready; it uses **azure-app-onboard** for architecture, cost estimation, IaC generation, provisioning, and health verification
