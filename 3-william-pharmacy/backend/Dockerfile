FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY prompts ./prompts
COPY mcp_client.py .

EXPOSE 5003

CMD ["python", "app.py"]
