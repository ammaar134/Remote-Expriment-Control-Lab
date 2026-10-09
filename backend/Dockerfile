FROM node:24-bookworm-slim@sha256:d6aa754f16b3197301076f047b5def2f02ea1dbbc2ca920407d46d7ec7f87b20 AS frontend
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS base
WORKDIR /app
COPY backend/requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY backend/ .
RUN useradd --create-home --uid 10002 lab
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
FROM base AS test
COPY backend/requirements-dev.lock .
RUN pip install --no-cache-dir -r requirements-dev.lock
CMD ["pytest", "-q"]
FROM base AS runtime
COPY --from=frontend /ui/dist ./static
USER 10002
EXPOSE 8000
CMD ["uvicorn", "lab.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--limit-concurrency", "64", "--timeout-keep-alive", "5"]
