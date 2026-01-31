import json
import os
import socket
import threading
import time
from flask import Flask, request, jsonify
import paho.mqtt.client as mqtt

# =====================
# Optionen laden
# =====================
def load_options():
    path = "/data/options.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[OPTIONS] Could not read {path}: {e}")
        return {}

opts = load_options()

def opt(name, default=None):
    env_key = f"ADDON_OPTION_{name.upper()}"
    return os.getenv(env_key, opts.get(name, default))

MQTT_HOST = opt("mqtt_host", "core-mosquitto")
MQTT_PORT = int(opt("mqtt_port", 1883))
MQTT_USER = opt("mqtt_user", "")
MQTT_PASSWORD = opt("mqtt_password", "")
BASE_TOPIC = opt("mqtt_topic", "gmc500/data")

DEVICE_ID = "gmc500"
DEVICE_NAME = "GMC 500 Geiger Counter"
DISCOVERY_PREFIX = "homeassistant"
AVAILABILITY_TOPIC = f"{BASE_TOPIC}/status"

print(f"[BOOT] MQTT host={MQTT_HOST} port={MQTT_PORT} user={'set' if MQTT_USER else 'empty'} pass={'set' if MQTT_PASSWORD else 'empty'} topic={BASE_TOPIC}")
print(f"[BOOT] options.json keys={list(opts.keys())}")

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

        res = mqtt_client.publish(discovery_topic, json.dumps(payload), qos=0, retain=True)
        print(f"[DISCOVERY] publish {discovery_topic} -> rc={res.rc}")

# =====================
# MQTT Client (Callback API v2)
# =====================
client = mqtt.Client(
    client_id=f"{DEVICE_ID}_bridge",
    protocol=mqtt.MQTTv311,
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2
)
client.enable_logger()

if MQTT_USER and MQTT_PASSWORD:
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
else:
    print("[MQTT] WARNING: mqtt_user/mqtt_password empty -> will connect without auth")

client.will_set(AVAILABILITY_TOPIC, payload="offline", qos=1, retain=True)

# v2: (client, userdata, connect_flags, reason_code, properties)
def on_connect(client, userdata, connect_flags, reason_code, properties):
    print(f"[MQTT] on_connect called, reason_code={reason_code}")
    if reason_code == 0:
        print(f"[MQTT] Connected to {MQTT_HOST}:{MQTT_PORT}")
        client.publish(AVAILABILITY_TOPIC, "online", qos=1, retain=True)
        publish_discovery(client)
    else:
        print(f"[MQTT] Connect failed, reason_code={reason_code}")

def on_connect_fail(client, userdata):
    print("[MQTT] on_connect_fail called")

# v2: (client, userdata, disconnect_flags, reason_code, properties)
def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    print(f"[MQTT] Disconnected, reason_code={reason_code}")

def on_log(client, userdata, level, buf):
    print(f"[MQTT-LOG] {buf}")

client.on_connect = on_connect
client.on_connect_fail = on_connect_fail
client.on_disconnect = on_disconnect
client.on_log = on_log

# If something crashes in any thread, print it
def thread_excepthook(args):
    print(f"[THREAD-EXC] in {args.thread.name}: {args.exc_type.__name__}: {args.exc_value}")

threading.excepthook = thread_excepthook

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
