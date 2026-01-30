FROM python:3.11-alpine

# Arbeitsverzeichnis
WORKDIR /app

# Abhängigkeiten installieren
RUN pip install --no-cache-dir flask paho-mqtt

# App kopieren
COPY app.py .

# Port freigeben
EXPOSE 80

# Startbefehl
CMD ["python", "app.py"]

