import json
import os
from flask import Flask, request, jsonify
import paho.mqtt.client as mqtt

# =====================
# Add-on Options / Konfiguration
# =====================
MQTT_HOST = os.getenv("ADDON_OPTION_MQTT_HOST", "core-mosquitto")
MQTT_PORT = int(os.getenv("ADDON_OPTION_MQTT_PORT", 1883))
MQTT_USER = os.getenv("ADDON_OPTION_MQTT_USER", "")
MQTT_PASSWORD = os.getenv("ADDON_OPTION_MQTT_PASSWORD", "")
BASE_TOPIC = os.getenv("ADDON_OPTION_MQTT_TOPIC", "gmc500/data")

DEVICE_ID = "gmc500"
DEVICE_NAME = "GMC 500 Geiger Counter"
DISCOVERY_PREFIX = "homeassistant"
AVAILABILITY_TOPIC = f"{BASE_TOPIC}/status"

print(f"[BOOT] MQTT host={MQTT_HOST} port={MQTT_PORT} user={'set' if MQTT_USER else 'empty'} topic={BASE_TOPIC}")

# =====================
# Flask App
# =====================
app = Flask(__name__)

# =====================
# Home Assistant Discovery
# =====================
def publish_discovery(client):
    sensors = {
        "cpm": {"name": "CPM", "unit": "CPM", "icon": "mdi:radioactive", "topic": f"{BASE_TOPIC}/cpm"},
        "acpm": {"name": "Avg CPM", "unit": "CPM", "icon": "mdi:chart-line", "topic": f"{BASE_TOPIC}/acpm"},
        "usv": {"name": "µSv/h", "unit": "µSv/h", "icon": "mdi:radioactive-circle", "topic": f"{BASE_TOPIC}/usv"},
        "dose": {"name": "Dose", "unit": "µSv", "icon": "mdi:counter", "topic": f"{BASE_TOPIC}/dose"},
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
        client.publish(discovery_topic, json.dumps(payload), retain=True)
        print(f"[DISCOVERY] published {discovery_topic}")

# =====================
# MQTT Client
# =====================
client = mqtt.Client(protocol=mqtt.MQTTv311, callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
client.enable_logger()

if MQTT_USER and MQTT_PASSWORD:
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

client.will_set(AVAILABILITY_TOPIC, payload="offline", qos=1, retain=True)

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"[MQTT] Connected to {MQTT_HOST}:{MQTT_PORT}")
        client.publish(AVAILABILITY_TOPIC, "online", retain=True)
        publish_discovery(client)
    else:
        print(f"[MQTT] Connect failed, reason_code={reason_code}")

client.on_connect = on_connect

client.connect(MQTT_HOST, MQTT_PORT)
client.loop_start()

# =====================
# HTTP Endpoint /gmc
# =====================
@app.route("/gmc", methods=["GET"])
def gmc():
    args = request.args
    if "CPM" in args:
        client.publish(f"{BASE_TOPIC}/cpm", args["CPM"], retain=True)
    if "ACPM" in args:
        client.publish(f"{BASE_TOPIC}/acpm", args["ACPM"], retain=True)
    if "uSV" in args:
        client.publish(f"{BASE_TOPIC}/usv", args["uSV"], retain=True)
    if "dose" in args:
        client.publish(f"{BASE_TOPIC}/dose", args["dose"], retain=True)
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
