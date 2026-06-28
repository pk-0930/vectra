# Repository Guidelines

## Project Structure & Module Organization

This repository contains two applications. `vectra-ui/` is the React 19, TypeScript, and Vite frontend; page components live in `src/pages/`, reusable UI in `src/components/`, API clients in `src/services/`, and shared domain types in `src/types/`. `mobility-ai-service/` is the FastAPI backend. Keep HTTP endpoints in `app.py`, business logic in `services/`, persistence adapters in `repositories/`, analysis pipelines in `analyzers/`, and reusable pose/video utilities in `shared/`. Squat-specific rules belong in `rules/squat/`. Backend tests live in `mobility-ai-service/tests/`. Architectural decisions and implementation plans are documented under `Specs/`.

## Build, Test, and Development Commands

Run commands from the relevant application directory.

```bash
cd mobility-ai-service
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload                 # start the API
python3 queue_worker.py                  # process queued analyses
python -m unittest discover -s tests     # run backend tests

cd vectra-ui
npm install
npm run dev                              # start Vite locally
npm run lint                             # run ESLint
npm run build                            # type-check and build production assets
```

## Coding Style & Naming Conventions

Follow existing conventions: four-space indentation and `snake_case` for Python functions/modules; two-space indentation, single quotes, and semicolon-free style for TypeScript. Use `PascalCase` for React components and exported types, `camelCase` for variables/functions, and descriptive service filenames such as `clientApi.ts`. Keep domain logic out of route handlers and UI pages. ESLint is the frontend source of truth; the backend has no configured formatter, so match nearby code and standard PEP 8 practices.

## Testing Guidelines

Backend tests use Python `unittest` with `unittest.mock`. Name files `test_<behavior>.py`, classes `<Area>Tests`, and methods `test_<expected_behavior>`. Favor in-memory repositories and mocks so tests do not require Azure or PostgreSQL. Add regression tests for service, queue lifecycle, authentication, and squat-rule changes. No frontend test framework is configured; always run `npm run lint` and `npm run build` for UI changes.

## Commit & Pull Request Guidelines

Recent commits use short, imperative summaries (for example, `Implementing PLAN.md` or `changing API Base URL in UI to azure`). Keep each commit focused and state the affected behavior. Pull requests should explain the change, list verification commands, link the relevant issue or `Specs/` document, and note configuration or schema impacts. Include screenshots for visible UI changes and never commit `.env`, `local.settings.json`, generated media, build output, or credentials.
