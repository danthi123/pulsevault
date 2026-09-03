FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

# Tiny runtime image: publishes the built bundle into the shared volume that
# the Caddy proxy serves, then stays alive.
FROM alpine:3.20
COPY --from=build /app/dist /app/dist
CMD ["sh", "-c", "rm -rf /dist/* && cp -a /app/dist/. /dist/ && echo 'frontend assets published to /dist' && tail -f /dev/null"]
