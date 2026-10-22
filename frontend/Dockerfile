# Stage 1: Build Flutter Web App
FROM ghcr.io/cirruslabs/flutter:stable AS build
WORKDIR /app
COPY pubspec.yaml pubspec.lock analysis_options.yaml ./
RUN flutter pub get
COPY lib ./lib
COPY web ./web
RUN flutter build web --release

# Stage 2: Serve with Caddy (usuário não-privilegiado; estáticos e Caddyfile imutáveis em runtime)
FROM caddy:2-alpine
RUN adduser -D -u 1000 caddy && \
    chown -R caddy:caddy /config /data
COPY --from=build --chmod=555 /app/build/web /usr/share/caddy
COPY --chmod=444 Caddyfile /etc/caddy/Caddyfile
USER caddy
