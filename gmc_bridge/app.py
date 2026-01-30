import json
import os
from flask import Flask, request, jsonify
import paho.mqtt.client as mqtt

# =====================
# Konfiguration
# =====================
MQTT_HOST = os.getenv("MQTT_HOST", "homeassistant")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

BASE_TOPIC = "gmc500"
DEVICE_ID = "gmc500"
DEVICE_NAME = "GMC 500 Geiger Counter"

# Home Assistant Auto-Discovery Prefix
DISCOVERY_PREFIX = "homeassistant"

AVAILABILITY_TOPIC = f"{BASE_TOPIC}/status"

# =====================
# Flask App
# =====================
app = Flask(__name__)

# =====================
# MQTT Client (Callback API v2)
# =====================
client = mqtt.Client(
    protocol=mqtt.MQTTv311,
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2
)

# Last Will (falls Add-on abstürzt)
client.will_set(
    AVAILABILITY_TOPIC,
    payload="offline",
    qos=1,
    retain=True
)

# =====================
# MQTT Callbacks
# =====================
def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("MQTT connected")
        # sofort online Status senden
        client.publish(AVAILABILITY_TOPIC, "online", retain=True)
        # sofort Discovery senden, damit Sensoren direkt sichtbar sind
        publish_discovery()
    else:
        print(f"MQTT connection failed: {reason_code}")

client.on_connect = on_connect

# Verbindung starten
client.connect(MQTT_HOST, MQTT_PORT)
client.loop_start()

# =====================
# Home Assistant Discovery
# =====================
def publish_discovery():
    sensors = {
        "cpm": {
            "name": "CPM",
            "unit": "CPM",
            "icon": "mdi:radioactive",
            "topic": f"{BASE_TOPIC}/cpm"
        },
        "acpm": {
            "name": "Avg CPM",
            "unit": "CPM",
            "icon": "mdi:chart-line",
            "topic": f"{BASE_TOPIC}/acpm"
        },
        "usv": {
            "name": "µSv/h",
            "unit": "µSv/h",
            "icon": "mdi:radioactive-circle",
            "topic": f"{BASE_TOPIC}/usv"
        },
        "dose": {
            "name": "Dose",
            "unit": "µSv",
            "icon": "mdi:counter",
            "topic": f"{BASE_TOPIC}/dose"
        }
    }

    for key, s in sensors.items():
        discovery_topic = f"{DISCOVERY_PREFIX}/sensor/{DEVICE_ID}/{key}/config"

        payload = {
            "name": f"{DEVICE_NAME} {s['name']}",
            "state_topic": s["topic"],
            "availability_topic": AVAILABILITY_TOPIC,
            "payload_available": "online",
            "payload_not_available": "offline",
            "unit_of_measurement": s["unit"],
            "icon": s["icon"],
            "unique_id": f"{DEVICE_ID}_{key}",
            "state_class": "total_increasing" if key == "dose" else "measurement",
            "device": {
                "identifiers": [DEVICE_ID],
                "name": DEVICE_NAME,
                "manufacturer": "GMC",
                "model": "GMC-500"
            }
        }

        client.publish(
            discovery_topic,
            json.dumps(payload),
            retain=True
        )

# =====================
# HTTP Endpoint /gmc
# =====================
@app.route("/gmc", methods=["GET"])
def gmc():
    args = request.args

    if "CPM" in args:
        client.publish(f"{BASE_TOPIC}/cpm", args["CPM"])
    if "ACPM" in args:
        client.publish(f"{BASE_TOPIC}/acpm", args["ACPM"])
    if "uSV" in args:
        client.publish(f"{BASE_TOPIC}/usv", args["uSV"])
    if "dose" in args:
        client.publish(f"{BASE_TOPIC}/dose", args["dose"])

    return jsonify({"status": "ok"}), 200

# =====================
# Main
# =====================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
