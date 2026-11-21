## 1. Workspace and tooling

- [ ] 1.1 Add `.python-version` (3.13) and the root `pyproject.toml` as a virtual uv workspace with members `backend` and `schemas`, and dev dependencies pytest, pytest-django and Ruff
- [ ] 1.2 Add Ruff config (rules `E`, `F`, `I`, `UP`, `B`, `DJ`) and pytest config (`DJANGO_SETTINGS_MODULE`, `pythonpath = ["backend"]`) to the root `pyproject.toml`
- [ ] 1.3 Create the `schemas` member (`filaments-schemas`, src layout, import name `schemas`) with pydantic as its only dependency and an empty `__init__.py`
- [ ] 1.4 Create the `backend` member (`filaments-backend`) depending on Django 5.2, django-ninja, psycopg[binary], gunicorn and `filaments-schemas` (workspace source)
- [ ] 1.5 Run `uv lock` and `uv sync`, and commit `uv.lock`

## 2. Django project

- [ ] 2.1 Generate the Django project in `backend/` with the config package `config`
- [ ] 2.2 Rewrite `config/settings.py` to read `DJANGO_SECRET_KEY` (required, fails fast), `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` and the `POSTGRES_*` keys from the environment; set `USE_TZ = True`, `TIME_ZONE = "UTC"`, and logging to the console and a file
- [ ] 2.3 Add `.env.example` with every key from 2.2, with comments showing dev vs. laptop values
- [ ] 2.4 Create `backend/api/` with a single `NinjaAPI` instance mounted at `/api/` in `config/urls.py`

## 3. Health route

- [ ] 3.1 Add `GET /api/health` (no auth) that runs `SELECT 1`, returning 200 `{"status": "ok"}` on success and 503 `{"detail": "Database unavailable"}` on failure, and logging the exception
- [ ] 3.2 Add pytest-django tests: 200 with the expected body, 200 with no `Authorization` header, and 503 when the database cursor raises (mocked)

## 4. Docker Compose

- [ ] 4.1 Add `backend/Dockerfile` (`python:3.13-slim`, uv copied from its official image, `uv sync --frozen --no-dev --package filaments-backend`), built with the repo root as context
- [ ] 4.2 Add `compose.yaml` with `db` (`postgres:17`, named volume, `pg_isready` healthcheck, `127.0.0.1:5432`) and `web` (env from `.env`, `POSTGRES_HOST=db`, waits for `db` healthy, runs `migrate` then gunicorn, `127.0.0.1:8000`, healthcheck on `/api/health`)
- [ ] 4.3 Verify by hand: `docker compose up` from a fresh `.env`, then `curl http://127.0.0.1:8000/api/health` returns 200; stopping `db` makes it return 503

## 5. Docs and checks

- [ ] 5.1 Update `CLAUDE.md`: add the real setup, run (Compose and `runserver`), test and lint commands, describe the workspace layout, and remove the "Pre-code" note
- [ ] 5.2 Update the README "Status" line and "Getting started" section to match
- [ ] 5.3 Run `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest`, and confirm all pass
