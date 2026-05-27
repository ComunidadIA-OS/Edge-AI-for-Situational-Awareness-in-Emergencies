# syntax=docker/dockerfile:1.7
# =============================================================================
# Heimdall — Ground Control · Dockerfile
# -----------------------------------------------------------------------------
# Multi-stage build that ships the dashboard as a static site served by nginx.
# - Stage 1 (deps)    : install pnpm, fetch dependencies
# - Stage 2 (builder) : run `pnpm build` (Next.js static export → out/)
# - Stage 3 (runtime) : nginx:alpine serving the static `out/` directory
#
# Build : docker build -t heimdall-ground-control .
# Run   : docker run --rm -p 3000:80 heimdall-ground-control
# =============================================================================

# ----- Stage 1: dependencies --------------------------------------------------
FROM node:20-alpine AS deps
WORKDIR /app
# corepack picks the exact pnpm version pinned in package.json ("packageManager"),
# so the build is reproducible. Do NOT use `pnpm@latest` here — it is
# non-deterministic and a frequent "works on my machine, fails in CI" trap.
RUN corepack enable

# Copy only the files needed to resolve the dependency graph so this layer
# stays cached across source-only changes.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./

RUN --mount=type=cache,id=pnpm-store,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile --prefer-offline

# ----- Stage 2: builder -------------------------------------------------------
FROM node:20-alpine AS builder
WORKDIR /app
RUN corepack enable

COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

RUN pnpm build

# ----- Stage 3: runtime -------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

# nginx config: SPA-style fallback + sensible caching for hashed assets.
RUN rm /etc/nginx/conf.d/default.conf
COPY <<'EOF' /etc/nginx/conf.d/default.conf
server {
    listen       80;
    server_name  _;
    root         /usr/share/nginx/html;
    index        index.html;

    # Long-cache Next.js hashed assets.
    location /_next/static/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # Don't cache HTML — config changes (e.g. Jetson URL) must be reflected.
    location ~* \.html$ {
        add_header Cache-Control "no-cache";
    }

    # MSW service worker — must always be fresh.
    location = /mockServiceWorker.js {
        add_header Cache-Control "no-cache";
    }

    # Trailing-slash + static-export friendly routing.
    location / {
        try_files $uri $uri.html $uri/index.html =404;
    }

    error_page 404 /404.html;
}
EOF

COPY --from=builder /app/out /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -q --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
