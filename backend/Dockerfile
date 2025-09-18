FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY db/ ./db
COPY main.py .

EXPOSE 8000

# uvicorn main:app --reload --host 0.0.0.0 --port 8000
CMD ["uvicorn", "main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
