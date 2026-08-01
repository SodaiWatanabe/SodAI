# syntax=docker/dockerfile:1.7

FROM python:3.12.11-slim-bookworm AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:${PATH}
WORKDIR /build
COPY packages/contracts ./packages/contracts
COPY backend ./backend
RUN pip install --upgrade "pip>=25.1" "setuptools>=78.1.1" \
    && pip install ./packages/contracts ./backend

FROM python:3.12.11-slim-bookworm AS runtime
ENV PATH=/opt/venv/bin:${PATH}
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /app/backend
RUN groupadd --system --gid 10001 sodai \
    && useradd --system --uid 10001 --gid sodai --home-dir /app --shell /usr/sbin/nologin sodai
COPY --from=build /opt/venv /opt/venv
COPY --chown=sodai:sodai backend/alembic.ini ./alembic.ini
COPY --chown=sodai:sodai backend/alembic ./alembic
USER sodai
EXPOSE 13202
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "13202", "--no-access-log", "--proxy-headers", "--forwarded-allow-ips", "*"]
