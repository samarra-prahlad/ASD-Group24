FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY prompts/ ./prompts/

EXPOSE 5005

CMD ["python", "app.py"]