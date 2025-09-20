FROM python:3.12-slim AS base

FROM base AS python-deps
RUN pip install virtualenv poetry==1.6.1
COPY poetry.lock pyproject.toml ./
RUN poetry config virtualenvs.create false
RUN poetry install --only main --no-root

WORKDIR /app

# COPY db/ ./db
COPY main.py .

EXPOSE 8000

# uvicorn main:app --reload --host 0.0.0.0 --port 8000
CMD ["uvicorn", "main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
