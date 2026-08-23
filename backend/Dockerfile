FROM python:3.13-slim
WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv
RUN apt-get update && apt-get install -y --no-install-recommends curl tzdata && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml and install dependencies (excluding dev/test groups)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy the full runtime source — the image is self-contained and never
# relies on a bind-mounted working tree.
COPY main.py .
COPY db/ ./db
COPY models/ ./models
COPY routes/ ./routes
COPY scheduler/ ./scheduler
COPY scripts/ ./scripts
COPY services/ ./services

# Immediate log output; no __pycache__ writes inside the container
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
