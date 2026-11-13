# Affiche IA: the API, the built frontend and Chromium in one image (D-HOSTED-PILOT-005).
# Built on the box by deploy/deploy.py from a git archive of HEAD. Layers go from rarely to often changed:
# dependencies, browser, then the source, so a code change does not download 1 GB again.

FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
# The type check and the build peak near 480 MB (measured 2026-11-13); the box has no swap.
ENV NODE_OPTIONS=--max-old-space-size=512
RUN npm run build

FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /bin/uv
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PATH=/app/backend/.venv/bin:$PATH \
    UV_PYTHON_DOWNLOADS=never UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HOME=/tmp
# In place, not as a wheel: the code finds alembic.ini, the migrations and ../frontend/dist from its own folder.
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-dev --no-install-project --no-cache
# The renderer runs headless only: the headless shell and its system libraries, not the full browser.
RUN playwright install --with-deps --only-shell chromium && rm -rf /var/lib/apt/lists/*
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/src ./src
RUN uv sync --frozen --no-dev --no-cache
COPY --from=frontend /build/dist /app/frontend/dist
# A new named volume takes its owner from the image folder: without this the application could not create
# its database or its lock in /data.
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app \
    && install -d -o 10001 -g 10001 /data /backups
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/session', timeout=3)"
CMD ["python", "-m", "affiche.api"]
# Last, so a new revision only changes these metadata layers. deploy/deploy.py sets it; /api/status reports it.
ARG REVISION=unknown
ENV REVISION=$REVISION
LABEL app=affiche-ia org.opencontainers.image.revision=$REVISION
