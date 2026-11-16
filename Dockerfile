FROM node:22-bookworm-slim AS frontend
WORKDIR /build
RUN npm install --global pnpm@9.15.9
COPY web/frontend/ web/frontend/
COPY docs/guides/ docs/guides/
WORKDIR /build/web/frontend
ENV VITE_API_BASE_URL=/api VITE_USE_MOCK=false
RUN pnpm install --frozen-lockfile --ignore-scripts && pnpm build

FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=7860
WORKDIR /app
COPY web/backend/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt
COPY web/backend/ web/backend/
COPY deploy/ deploy/
COPY --from=frontend /build/web/frontend/dist/ web/frontend/dist/
EXPOSE 7860
CMD ["python", "deploy/serve.py"]
