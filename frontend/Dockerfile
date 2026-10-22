# Stage 1: Build Flutter Web App
FROM ghcr.io/cirruslabs/flutter:stable AS build
WORKDIR /app
COPY pubspec.yaml pubspec.lock analysis_options.yaml ./
RUN flutter pub get --enforce-lockfile
COPY lib ./lib
COPY web ./web
RUN flutter build web --release

# Stage 2: Serve with Caddy
FROM caddy:2-alpine  # NOSONAR: Caddy web server container
COPY --from=build /app/build/web /usr/share/caddy
COPY Caddyfile /etc/caddy/Caddyfile
