FROM node:22.23.3-bookworm-slim AS build

WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.29-alpine

USER root
RUN rm -f /etc/nginx/conf.d/default.conf /etc/nginx/templates/default.conf.template
COPY infra/docker/gateway/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html
RUN chown -R nginx:nginx /usr/share/nginx/html /etc/nginx/conf.d/default.conf
USER nginx
