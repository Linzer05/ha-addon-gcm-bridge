import json
import time
from flask import Flask, request, jsonify
import paho.mqtt.client as mqtt

# =====================
# Optionen (HA Add-on Standard)
# =====================
def load_options():
    path = "/data/options.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Could not read {path}: {e}")
        return {}

opts = load_options()

MQTT_HOST = opts.get("mqtt_host", "core-mosquitto")
MQTT_PORT = int(opts.get("mqtt_port", 1883))
MQTT_USER = opts.get("mqtt_user", "")
MQTT_PASSWORD = opts.get("mqtt_password", "")
BASE_TOPIC = opts.get("mqtt_topic", "gmc500/data")

DEVICE_ID = "gmc500"
DEVICE_NAME = "GMC 500 Geiger Counter"
DISCOVERY_PREFIX = "homeassistant"
AVAILABILITY_TOPIC = f"{BASE_TOPIC}/status"

print(f"[BOOT] host={MQTT_HOST} port={MQTT_PORT} user={'set' if MQTT_USER else 'empty'} topic={BASE_TOPIC}")

# =====================
# Flask
# =====================
app = Flask(__name__)

# =====================
# Home Assistant Discovery
# =====================
def publish_discovery(mqtt_client: mqtt.Client) -> None:
    sensors = {
        "cpm": {
            "name": "CPM",
            "unit": "CPM",
            "icon": "mdi:radioactive",
            "topic": f"{BASE_TOPIC}/cpm",
            "state_class": "measurement",
        },
        "acpm": {
            "name": "Avg CPM",
            "unit": "CPM",
            "icon": "mdi:chart-line",
            "topic": f"{BASE_TOPIC}/acpm",
            "state_class": "measurement",
        },
        "usv": {
            "name": "µSv/h",
            "unit": "µSv/h",
            "icon": "mdi:radioactive-circle",
            "topic": f"{BASE_TOPIC}/usv",
            "state_class": "measurement",
        },
        "dose": {
            "name": "Dose",
            "unit": "µSv",
            "icon": "mdi:counter",
            "topic": f"{BASE_TOPIC}/dose",
            "state_class": "total_increasing",
        },
    }

    device_block = {
        "identifiers": [DEVICE_ID],
        "name": DEVICE_NAME,
        "manufacturer": "GMC",
        "model": "GMC-500",
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
            "state_class": s["state_class"],
            "device": device_block,
        }
        mqtt_client.publish(discovery_topic, json.dumps(payload), retain=True)

    print("[MQTT] Discovery published")

# =====================
# MQTT
# =====================
client = mqtt.Client(
    client_id=f"{DEVICE_ID}_bridge",
    protocol=mqtt.MQTTv311,
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
)

# Optional: paho internal logging (lass aus für
