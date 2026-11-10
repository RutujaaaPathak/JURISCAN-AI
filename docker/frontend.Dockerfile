# JURISCAN-AI frontend image: build the Vite SPA, serve it with nginx.
#
# Build context is the repository root (see docker-compose.yml) because the
# nginx config in this directory is copied into the image as well.
FROM node:22-alpine AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ .

# Same-origin API: nginx (below) serves the SPA and proxies /api (including
# WebSocket upgrades) to the backend container, so no absolute backend URL
# is baked into the client bundle. Relative WebSocket URLs resolve against
# the page origin (wss:// on https pages).
ENV VITE_API_BASE_URL=/api
RUN npm run build


FROM nginx:1.27-alpine

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
