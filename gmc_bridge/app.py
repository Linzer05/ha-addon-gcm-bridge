from flask import Flask, request
import paho.mqtt.client as mqtt
import json
import os

# ===== MQTT Konfiguration =====
MQTT_HOST = os.getenv("MQTT_HOST", "core-mosquitto")  # HA interner Broker
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "gmc500/data")

# ===== Flask App =====
app = Flask(__name__)

# ===== MQTT Client Setup =====
client = mqtt.Client(client_id="", protocol=mqtt.MQTTv311)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Connected to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
    else:
        print(f"Failed to connect, return code {rc}")

client.on_connect = on_connect

try:
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()  # MQTT läuft im Hintergrund
except Exception as e:
    print(f"ERROR: Could not connect to MQTT broker: {e}")

# ===== Test Route =====
@app.route('/')
def index():
    return "GMC500 MQTT Bridge läuft!"

# ===== /gmc Route =====
@app.route('/gmc')
def gmc():
    data = request.args.to_dict()
    if not data:
        return "No data provided", 400
    try:
        client.publish(MQTT_TOPIC, json.dumps(data))
        return "OK"
    except Exception as e:
        return f"MQTT publish failed: {e}", 500

# ===== Start Flask =====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=False)




