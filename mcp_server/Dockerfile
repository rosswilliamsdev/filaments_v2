# Build with the repo root as context (see compose.yaml): the image needs the workspace
# lockfile and the schemas package. Never Django.
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
COPY mcp_server/pyproject.toml mcp_server/pyproject.toml
RUN uv sync --frozen --no-dev --package filaments-mcp --no-install-workspace

COPY schemas/ schemas/
COPY mcp_server/ mcp_server/
RUN uv sync --frozen --no-dev --package filaments-mcp --no-editable

EXPOSE 8000
CMD ["python", "-m", "filaments_mcp", "--http"]
