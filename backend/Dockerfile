FROM python:3.12-slim AS base
LABEL VERSION="0.1.0"

# Install python dependencies
FROM base AS python-deps
ENV POETRY_VIRTUALENVS_CREATE=false \
    POETRY_VERSION=1.8.4
RUN pip install poetry==$POETRY_VERSION
COPY ./pyproject.toml ./poetry.lock ./
RUN poetry install

# Copy Python dependencies
FROM python-deps AS deploy
COPY ./app /app
CMD ["uvicorn", "app.main:api", "--reload", "--host", "0.0.0.0", "--port", "80"]
