# Stage 1: Build frontend
FROM node:20-alpine AS frontend
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci || (sleep 2 && npm ci)
COPY web/ ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir . -i https://pypi.org/simple/ --extra-index-url https://mirrors.aliyun.com/pypi/simple/
COPY --from=frontend /app/web/dist web/dist
ENV PYTHONUNBUFFERED=1
EXPOSE 8090
ENTRYPOINT ["python", "-u", "-m", "openvort"]
CMD ["start"]
