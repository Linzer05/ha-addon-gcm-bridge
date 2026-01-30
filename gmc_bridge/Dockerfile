# Base Image: leicht, HA-kompatibel
FROM python:3.12-slim

# Arbeitsverzeichnis
WORKDIR /app

# Python Abhängigkeiten
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App kopieren
COPY app.py .

# Port exposed
EXPOSE 80

# Start Command
CMD ["python", "app.py"]


