import json
import os
import socket
import time
from flask import Flask, request, jsonify
import paho.mqtt.client as mqtt

# =====================
# Add-on Options / Konfiguration
# =====================
MQTT_HOST = os.getenv("ADDON_OPTION_MQTT_HOST", "core-mosquitto")
MQTT_PORT = int(os.getenv("ADDON_OPTION_MQTT_PORT", "1883"))
MQTT_USER = os.getenv("ADDON_OPTION_MQTT_USER", "")
MQTT_PASSWORD = os.getenv("ADDON_OPTION_MQTT_PASSWORD", "")
BASE_TOPIC = os.getenv("ADDON_OPTION_MQTT_TOPIC", "gmc500/data")

DEVICE_ID = "gmc500"
DEVICE_NAME = "GMC 500 Geiger Counter"

# Home Assistant Auto-Discovery Prefix
DISCOVERY_PREFIX = "homeassistant"

AVAILABILITY_TOPIC = f"{BASE_TOPIC}/status"

# =====================
# Debug: show effective configuration
# =====================
print(f"[BOOT] MQTT host={MQTT_HOST} port={MQTT_PORT} user={'set' if MQTT_USER else 'empty'} topic={BASE_TOPIC}")

# DNS debug (important when host_network is true)
try:
    resolved_ip = socket.gethostbyname(MQTT_HOST)
    print(f"[DNS] {MQTT_HOST} -> {resolved_ip}")
except Exception as e:
    print(f"[DNS] resolve failed for {MQTT_HOST}: {e}")

# =====================
# Flask App
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

        res = mqtt_client.publish(discovery_topic, json.dumps(payload), qos=0, retain=True)
        print(f"[DISCOVERY] publish {discovery_topic} -> rc={res.rc}")

# =====================
# MQTT Client (Callback API v2)
# =====================
client = mqtt.Client(
    protocol=mqtt.MQTTv311,
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2
)

# Enable paho internal logging into stdout (shows helpful details)
client.enable_logger()

# Optional: credentials
if MQTT_USER and MQTT_PASSWORD:
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

# Availability LWT
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
        print(f"[MQTT] Connected to {MQTT_HOST}:{MQTT_PORT}")
        client.publish(AVAILABILITY_TOPIC, "online", qos=1, retain=True)
        publish_discovery(client)
    else:
        print(f"[MQTT] Connect failed, reason_code={reason_code}")

def on_disconnect(client, userdata, reason_code, properties):
    print(f"[MQTT] Disconnected, reason_code={reason_code}")

def on_log(client, userdata, level, buf):
    # This is very chatty, but great for debugging.
    # You can comment it out later.
    print(f"[MQTT-LOG] {buf}")

client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_log = on_log

# =====================
# Connect starten (safe)
# =====================
try:
    print("[MQTT] connecting...")
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    print("[MQTT] connect() returned, starting loop")
    client.loop_start()
except Exception as e:
    print(f"[MQTT] connect() exception: {e}")

# =====================
# HTTP Endpoint /gmc
# =====================
@app.route("/gmc", methods=["GET"])
def gmc():
    args = request.args

    # publish raw values; retain makes HA show last value after restart
    if "CPM" in args:
        client.publish(f"{BASE_TOPIC}/cpm", args["CPM"], retain=True)
        print(f"[PUB] {BASE_TOPIC}/cpm = {args['CPM']}")
    if "ACPM" in args:
        client.publish(f"{BASE_TOPIC}/acpm", args["ACPM"], retain=True)
        print(f"[PUB] {BASE_TOPIC}/acpm = {args['ACPM']}")
    if "uSV" in args:
        client.publish(f"{BASE_TOPIC}/usv", args["uSV"], retain=True)
        print(f"[PUB] {BASE_TOPIC}/usv = {args['uSV']}")
    if "dose" in args:
        client.publish(f"{BASE_TOPIC}/dose", args["dose"], retain=True)
        print(f"[PUB] {BASE_TOPIC}/dose = {args['dose']}")

    return jsonify({"status": "ok"}), 200

# =====================
# Main
# =====================
if __name__ == "__main__":
    # Tip: Wenn du später einen produktiven Server willst: gunicorn statt Flask dev server.
    app.run(host="0.0.0.0", port=80)
