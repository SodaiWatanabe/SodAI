# syntax=docker/dockerfile:1.7

FROM pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY packages/contracts ./packages/contracts
COPY inference ./inference
RUN python -m pip install --upgrade "pip>=25.1" "setuptools>=78.1.1" \
    && python -m pip install ./packages/contracts ./inference \
    && groupadd --gid 1000 sodai \
    && useradd --uid 1000 --gid sodai --home-dir /app --shell /usr/sbin/nologin sodai \
    && rm -rf /app/packages /app/inference
USER sodai
CMD ["sodai-inference"]
