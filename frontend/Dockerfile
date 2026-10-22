# Stage 1: Build Flutter Web App
FROM ghcr.io/cirruslabs/flutter:stable AS build
WORKDIR /app
COPY pubspec.yaml pubspec.lock analysis_options.yaml ./
RUN flutter pub get --enforce-lockfile
COPY lib ./lib
COPY web ./web
RUN flutter build web --release

# Stage 2: Serve with Caddy (usuário não-privilegiado com cap_net_bind_service nas portas 80/443)
FROM caddy:2-alpine
RUN adduser -D -u 1000 caddy && \
    chown -R caddy:caddy /config /data /usr/share/caddy
COPY --from=build --chown=caddy:caddy /app/build/web /usr/share/caddy
COPY --chown=caddy:caddy Caddyfile /etc/caddy/Caddyfile
USER caddy
