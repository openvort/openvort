# Stage 1: Build frontend
FROM node:20-alpine AS frontend
ARG MIRROR=default
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN if [ "$MIRROR" = "cn" ]; then \
      npm ci --registry=https://registry.npmmirror.com || (sleep 2 && npm ci --registry=https://registry.npmmirror.com); \
    else \
      npm ci || (sleep 2 && npm ci); \
    fi
COPY web/ ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.11-slim
ARG MIRROR=default

RUN if [ "$MIRROR" = "cn" ]; then \
      sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources; \
    fi && \
    apt-get update && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    curl \
    gpg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
       | gpg --dearmor -o /usr/share/keyrings/pgdg.gpg \
    && PGDG_MIRROR="http://apt.postgresql.org/pub/repos/apt" \
    && if [ "$MIRROR" = "cn" ]; then \
         PGDG_MIRROR="https://mirrors.tuna.tsinghua.edu.cn/postgresql/repos/apt"; \
       fi \
    && echo "deb [signed-by=/usr/share/keyrings/pgdg.gpg] $PGDG_MIRROR $(. /etc/os-release && echo $VERSION_CODENAME)-pgdg main" \
       > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends postgresql-client-18 \
    && rm -rf /var/lib/apt/lists/*

RUN if [ "$MIRROR" = "cn" ]; then \
      curl -fsSL https://npmmirror.com/mirrors/node/v20.18.0/node-v20.18.0-linux-x64.tar.xz \
        | tar -xJ -C /usr/local --strip-components=1; \
    else \
      curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
        && apt-get install -y --no-install-recommends nodejs \
        && rm -rf /var/lib/apt/lists/*; \
    fi

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/
RUN pip install --no-cache-dir --upgrade pip && \
    if [ "$MIRROR" = "cn" ]; then \
      pip install --no-cache-dir . -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com; \
    else \
      pip install --no-cache-dir .; \
    fi
COPY --from=frontend /app/web/dist web/dist
ENV PYTHONUNBUFFERED=1
EXPOSE 8090
ENTRYPOINT ["python", "-u", "-m", "openvort"]
CMD ["start"]
