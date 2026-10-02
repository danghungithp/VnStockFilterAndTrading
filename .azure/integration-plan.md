# Integration hand-off

## Backend
- Project folder: `app/`
- Entrypoint: `run.py` / `app/main.py`
- Run command: `python run.py`
- Port: `5000`
- Health endpoint: `/api/health`
- Build/test command: `python -m pytest -q`

## Frontend
- Stack: Flask + Jinja templates + Pico.css
- Project folder: `app/templates/`
- Dev/runtime command: `python run.py`
- API seam: `app/routes.py` and `app/services/screening_service.py`
- Mock files to keep for demo UI: `app/data/mock_market_data.py`
- Live-data wiring note: swap the service layer to a real data provider without rewriting templates; keep page contract stable

## API routes
- `GET /` — dashboard page
- `GET /recommendations` — recommendation page
- `GET /api/health` — health check
- `GET /api/overview` — overview summary
- `GET /api/recommendations` — ranked recommendations payload
- `GET /api/strategy/<strategy>` — per-strategy scoring payload

## Data
- Type: in-memory mock data only
- Migration tool: none required
- Database: none
- No seed data required

## Shared types
- Local app modules provide the contract; no separate shared package

## Services
- Essential: screening service, strategy evaluators, Flask routes
- Enhancement: UI styling and recommendation score formatting
