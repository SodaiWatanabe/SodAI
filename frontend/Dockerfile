# syntax=docker/dockerfile:1.7

FROM node:24.18.0-bookworm-slim AS dependencies
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

FROM node:24.18.0-bookworm-slim AS build
WORKDIR /app
ARG NEXT_PUBLIC_API_BASE_URL=https://app.sodai.me
ARG SODAI_DEPLOYMENT_ID=local
ENV NEXT_TELEMETRY_DISABLED=1
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV SODAI_DEPLOYMENT_ID=${SODAI_DEPLOYMENT_ID}
COPY --from=dependencies /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:24.18.0-bookworm-slim AS runtime
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOSTNAME=0.0.0.0
ENV PORT=13200
WORKDIR /app
RUN groupadd --system --gid 10001 sodai \
    && useradd --system --uid 10001 --gid sodai --home-dir /app --shell /usr/sbin/nologin sodai
COPY --from=build --chown=sodai:sodai /app/public ./public
COPY --from=build --chown=sodai:sodai /app/.next-build/standalone ./
COPY --from=build --chown=sodai:sodai /app/.next-build/static ./.next-build/static
USER sodai
EXPOSE 13200
CMD ["node", "server.js"]
