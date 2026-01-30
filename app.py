from flask import Flask, request
import paho.mqtt.client as mqtt
import json
import os

# ===== MQTT Konfiguration =====
# Standard: localhost (HA Host)
MQTT_HOST = os.getenv("MQTT_HOST", "192.168.1.xxx")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "gcm500/data")

# ===== Flask App =====
app = Flask(__name__)

# ===== MQTT Client Setup =====
client = mqtt.Client(client_id="", protocol=mqtt.MQTTv311)

# Optional: Callback bei Verbindung
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Connected to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
    else:
        print(f"Failed to connect, return code {rc}")

client.on_connect = on_connect

# Verbindung herstellen
try:
    client.connect(MQTT_HOST, MQTT_PORT, 60)
except Exception as e:
    print(f"ERROR: Could not connect to MQTT broker: {e}")

# ===== Flask Route =====
@app.route('/gcm')
def gcm():
    data = request.args.to_dict()
    try:
        client.publish(MQTT_TOPIC, json.dumps(data))
        return "OK"
    except Exception as e:
        return f"MQTT publish failed: {e}", 500

# ===== Start Flask =====
if __name__ == "__main__":
    # Host 0.0.0.0 → erreichbar von allen Interfaces
    app.run(host="0.0.0.0", port=80, debug=False)



