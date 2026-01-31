import json
import socket
import threading
import time
from datetime import datetime, timezone
from flask import Flask, request, jsonify
import paho.mqtt.client as mqtt

# =====================
# Optionen laden (HA Add-on Standard)
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

MQTT_HOST = opts.get("mqtt_host", "core-mosquitto")
MQTT_PORT = int(opts.get("mqtt_port", 1883))
MQTT_USER = opts.get("mqtt_user", "")
MQTT_PASSWORD = opts.get("mqtt_password", "")
BASE_TOPIC = opts.get("mqtt_topic", "gmc500/data")

DEVICE_ID = "gmc500"
DEVICE_NAME = "GMC-500"
DISCOVERY_PREFIX = "homeassistant"
AVAILABILITY_TOPIC = f"{BASE_TOPIC}/status"

LAST_UPDATE_TOPIC = f"{BASE_TOPIC}/last_update"
LAST_UPDATE_ISO_TOPIC = f"{BASE_TOPIC}/last_update_iso"

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
            "name": "Total Dose",
            "unit": "µSv",
            "icon": "mdi:counter",
            "topic": f"{BASE_TOPIC}/dose",
            "state_class": "total_increasing",
        },

        # Schritt 3.1: Last update (Unix time)
        "last_update": {
            "name": "Last Update",
            "unit": "s",
            "icon": "mdi:clock-outline",
            "topic": LAST_UPDATE_TOPIC,
            "state_class": "measurement",
        },

        # Schritt 3.1: Last update ISO (Text)
        "last_update_iso": {
            "name": "Last Update (ISO)",
            "unit": None,
            "icon": "mdi:clock-check-outline",
            "topic": LAST_UPDATE_ISO_TOPIC,
            "state_class": None,
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
            "icon": s["icon"],
            "unique_id": f"{DEVICE_ID}_{key}",
            "device": device_block,
        }

        # unit + state_class nur setzen, wenn vorhanden
        if s.get("unit"):
            payload["unit_of_measurement"] = s["unit"]
        if s.get("state_class"):
            payload["state_class"] = s["state_class"]

        mqtt_client.publish(discovery_topic, json.dumps(payload), retain=True)

    print("[MQTT] Discovery published")

# =====================
# MQTT Client (Callback API v2)
# =====================
client = mqtt.Client(
    client_id=f"{DEVICE_ID}_bridge",
    protocol=mqtt.MQTTv311,
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2
)

# client.enable_logger()  # bei Debug aktivieren

if MQTT_USER and MQTT_PASSWORD:
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
else:
    print("[MQTT] WARNING: mqtt_user/mqtt_password empty -> will connect without auth")

client.will_set(AVAILABILITY_TOPIC, payload="offline", qos=1, retain=True)

def on_connect(client, userdata, connect_flags, reason_code, properties):
    print(f"[MQTT] on_connect reason_code={reason_code}")
    if reason_code == 0:
        print(f"[MQTT] Connected to {MQTT_HOST}:{MQTT_PORT}")
        client.publish(AVAILABILITY_TOPIC, "online", qos=1, retain=True)
        publish_discovery(client)
    else:
        print(f"[MQTT] Connect failed: {reason_code}")

def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    print(f"[MQTT] Disconnected: {reason_code}")

client.on_connect = on_connect
client.on_disconnect = on_disconnect

def thread_excepthook(args):
    print(f"[THREAD-EXC] in {args.thread.name}: {args.exc_type.__name__}: {args.exc_value}")

threading.excepthook = thread_excepthook

client.reconnect_delay_set(min_delay=1, max_delay=60)

try:
    print("[MQTT] connecting...")
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    print("[MQTT] connect() returned, starting loop")
    client.loop_start()
except Exception as e:
    print(f"[MQTT] connect() exception: {e}")

# =====================
# Helper: Values publishen
# =====================
def publish_value(topic: str, value_str: str):
    client.publish(topic, value_str, retain=True)

def publish_last_update():
    # Unix seconds + ISO timestamp (UTC)
    ts = int(time.time())
    iso = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    client.publish(LAST_UPDATE_TOPIC, str(ts), retain=True)
    client.publish(LAST_UPDATE_ISO_TOPIC, iso, retain=True)

# =====================
# HTTP Endpoint /gmc
# =====================
@app.route("/gmc", methods=["GET"])
def gmc():
    args = request.args

    if "CPM" in args:
        publish_value(f"{BASE_TOPIC}/cpm", args["CPM"])
    if "ACPM" in args:
        publish_value(f"{BASE_TOPIC}/acpm", args["ACPM"])
    if "uSV" in args:
        publish_value(f"{BASE_TOPIC}/usv", args["uSV"])
    if "dose" in args:
        publish_value(f"{BASE_TOPIC}/dose", args["dose"])

    # Schritt 3.1: Update-Timestamp bei jedem Request
    publish_last_update()

    return jsonify({"status": "ok"}), 200

# =====================
# Main
# =====================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
