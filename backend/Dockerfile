FROM python:3.13-slim
WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy pyproject.toml and install dependencies
COPY pyproject.toml .
RUN uv sync --frozen

COPY db/ ./db
COPY main.py .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
