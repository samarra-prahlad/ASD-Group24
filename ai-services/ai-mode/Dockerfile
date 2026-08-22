FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY plan.py act.py observe.py adapt.py app.py .

CMD ["python", "app.py"]