FROM node:22-alpine AS frontend-build
WORKDIR /src/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS backend
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    EMAIL_ENVIRONMENT=production \
    EMAIL_DATABASE_URL=sqlite:////app/data/database.sqlite \
    EMAIL_DATA_DIR=/app/data \
    EMAIL_NAMES_DIR=/app/data/names \
    EMAIL_LOG_DIR=/app/logs \
    EMAIL_OUTBOUND_WORKER_ENABLED=false
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend /app/backend
COPY data/names /app/data/names
COPY --from=frontend-build /src/frontend/dist /app/frontend/dist
EXPOSE 18083
CMD ["uvicorn", "app.main:app", "--app-dir", "/app/backend", "--host", "0.0.0.0", "--port", "18083"]

FROM nginx:1.27-alpine AS web
COPY frontend/nginx.docker.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /src/frontend/dist /usr/share/nginx/html
