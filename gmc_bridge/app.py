from flask import Flask, request
import paho.mqtt.client as mqtt
import json
import os
import threading
from waitress import serve

# ===============================
# MQTT KONFIGURATION (HA-Official)
# ===============================
MQTT_HOST = os.getenv("MQTT_HOST", "core-mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

BASE_TOPIC = "gmc500"
DISCOVERY_PREFIX = "homeassistant"

DEVICE_ID = "gmc500"
DEVICE_NAME = "GMC500 Geiger Counter"

# ===============================
# FLASK APP
# ===============================
app = Flask(__name__)

# ===============================
# MQTT CLIENT
# ===============================
client = mqtt.Client(protocol=mqtt.MQTTv311)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("MQTT connected")
        publish_discovery()
    else:
        print(f"MQTT connection failed: {rc}")

client.on_connect = on_connect

client.connect(MQTT_HOST, MQTT_PORT, 60)
client.loop_start()

# ===============================
# MQTT AUTO DISCOVERY
# ===============================
def publish_discovery():
    sensors = {
        "cpm": {
            "name": "CPM",
            "unit": "CPM",
            "icon": "mdi:radioactive",
            "topic": f"{BASE_TOPIC}/cpm"
        },
        "acpm": {
            "name": "ACPM",
            "unit": "CPM",
            "icon": "mdi:radioactive",
            "topic": f"{BASE_TOPIC}/acpm"
        },
        "usv": {
            "name": "Radiation",
            "unit": "µSv/h",
            "icon": "mdi:radioactive",
            "topic": f"{BASE_TOPIC}/usv"
        },
        "dose": {
            "name": "Total Dose",
            "unit": "µSv",
            "icon": "mdi:counter",
            "topic": f"{BASE_TOPIC}/dose"
        }
    }

    for key, s in sensors.items():
        payload = {
            "name": f"{DEVICE_NAME} {s['name']}",
            "state_topic": s["topic"],
            "unit_of_measurement": s["unit"],
            "icon": s["icon"],
            "unique_id": f"{DEVICE_ID}_{key}",
            "state_class": "measurement" if key != "dose" else "total_increasing",
            "device_class": "radiation" if key in ["cpm", "acpm", "usv"] else None,
            "device": {
                "identifiers": [DEVICE_ID],
                "name": DEVICE_NAME,
                "manufacturer": "GMC",
                "model": "GMC500"
            }
        }

        topic = f"{DISCOVERY_PREFIX}/sensor/{DEVICE_ID}/{key}/config"
        client.publish(topic, json.dumps(payload), retain=True)

# ===============================
# GMC ENDPOINT
# ===============================
@app.route("/gmc", methods=["GET"], strict_slashes=False)
@app.route("/gmc/", methods=["GET"], strict_slashes=False)
def gmc():
    data = request.args

    if "CPM" in data:
        client.publish(f"{BASE_TOPIC}/cpm", data["CPM"])
    if "ACPM" in data:
        client.publish(f"{BASE_TOPIC}/acpm", data["ACPM"])
    if "uSV" in data:
        client.publish(f"{BASE_TOPIC}/usv", data["uSV"])
    if "dose" in data:
        client.publish(f"{BASE_TOPIC}/dose", data["dose"])

    return "OK", 200

# ===============================
# START SERVER (PRODUCTION SAFE)
# ===============================
if __name__ == "__main__":
    print("GMC Bridge started")
    serve(app, host="0.0.0.0", port=80)
