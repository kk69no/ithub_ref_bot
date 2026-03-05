FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создать директорию для данных
RUN mkdir -p /app/data

ENV DATABASE_PATH=/app/data/ithub_ref.db

CMD ["python", "main.py"]
