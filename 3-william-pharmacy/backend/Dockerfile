FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt


COPY backend/app.py .
COPY database/init_db.py .

EXPOSE 5103

  CMD ["sh", "-c", "python /app/init_db.py && python app.py"]
