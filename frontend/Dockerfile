FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

# Self-serving web tier: serves the built SPA and reverse-proxies /api to the
# backend, so the central Caddy reaches the whole app at a single upstream (:80).
# (Replaces the old split of a dist-holder container + a separate proxy service.)
FROM caddy:2-alpine
COPY --from=build /app/dist /srv/www
COPY Caddyfile /etc/caddy/Caddyfile
EXPOSE 80
