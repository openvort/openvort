# Stage 1: Build frontend
FROM node:20-alpine AS frontend
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/
COPY alembic.ini ./
COPY alembic/ alembic/
RUN pip install --no-cache-dir .
COPY --from=frontend /app/web/dist web/dist
EXPOSE 8090
ENTRYPOINT ["openvort"]
CMD ["start", "--web"]
