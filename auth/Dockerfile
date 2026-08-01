# syntax=docker/dockerfile:1.7

FROM node:24.18.0-bookworm-slim AS production-dependencies
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts && npm cache clean --force

FROM node:24.18.0-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY --chown=node:node . .
RUN npm run build

FROM build AS migrator
ENV NODE_ENV=production
USER node
CMD ["npm", "run", "migrate"]

FROM node:24.18.0-bookworm-slim AS runtime
ENV NODE_ENV=production
WORKDIR /app
RUN groupadd --system --gid 10001 sodai \
    && useradd --system --uid 10001 --gid sodai --home-dir /app --shell /usr/sbin/nologin sodai
COPY --from=production-dependencies --chown=sodai:sodai /app/node_modules ./node_modules
COPY --from=build --chown=sodai:sodai /app/dist ./dist
COPY --from=build --chown=sodai:sodai /app/package.json ./package.json
USER sodai
EXPOSE 13201
CMD ["node", "dist/main.js"]
