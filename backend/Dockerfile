# Build with the repo root as context (see compose.yaml): the image needs
# the workspace lockfile and the schemas package, not just backend/.
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Dependencies first, so source edits don't invalidate this layer.
COPY pyproject.toml uv.lock .python-version ./
COPY backend/pyproject.toml backend/pyproject.toml
COPY schemas/pyproject.toml schemas/pyproject.toml
RUN uv sync --frozen --no-dev --package filaments-backend --no-install-workspace

# Then the workspace packages and the Django project.
COPY schemas/ schemas/
COPY backend/ backend/
RUN uv sync --frozen --no-dev --package filaments-backend --no-editable

WORKDIR /app/backend
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
