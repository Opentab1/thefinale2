import os
import time
import json
import random
import threading
from flask import Flask, render_template, jsonify

from rpi.aws_sync import start_aws_sync

# Compute template folder relative to this file so it works from any CWD
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
app = Flask(__name__, template_folder=TEMPLATES_DIR)

# Shared data (simulated for now)
_data_lock = threading.Lock()
_data = {
    "decibels": 0,
    "light": 0,
    "indoorTemp": 0,
    "outdoorTemp": 0,
    "humidity": 0,
    "song": "None",
    "comfort": 0,
}

VENUE_ID = os.environ.get("PULSE_VENUE_ID", "fergs-stpete")
LOCATION_ID = os.environ.get("PULSE_LOCATION_ID", "main-floor")


def _update_data_loop():
    global _data
    while True:
        new_snapshot = {
            "decibels": round(random.uniform(60, 85), 1),
            "light": random.randint(200, 800),
            "indoorTemp": round(random.uniform(68, 76), 1),
            "outdoorTemp": round(random.uniform(50, 75), 1),
            "humidity": random.randint(40, 60),
            "song": random.choice([
                "Sweet Caroline",
                "Bohemian Rhapsody",
                "Don't Stop Believin'",
                "Mr. Brightside",
                "Livin' on a Prayer",
            ]),
            "comfort": random.randint(90, 100),
        }
        with _data_lock:
            _data = new_snapshot
        time.sleep(2)


# Start simulated sensors
threading.Thread(target=_update_data_loop, daemon=True, name="sim-data-thread").start()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/data")
def get_data():
    with _data_lock:
        snapshot = dict(_data)
    return jsonify(snapshot)


def _safe_record_provider():
    with _data_lock:
        snapshot = dict(_data)
    snapshot.update(
        {
            "venueId": VENUE_ID,
            "locationId": LOCATION_ID,
            "timestamp": int(time.time() * 1000),
        }
    )
    return snapshot

# Start AWS sync in background (single thread)
start_aws_sync(record_provider=_safe_record_provider, interval_seconds=30)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
