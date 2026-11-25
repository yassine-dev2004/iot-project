"""
Simulator and Seeder Script:
Generates synthetic camera snapshots and uploads realistic door events
directly to the Spring Boot backend via HTTP POST /api/events.
Demonstrates the entire pipeline without requiring a physical camera or Pi.
"""

import time
import json
import requests
import numpy as np
import cv2
import uuid
from datetime import datetime

BACKEND_URL = "http://localhost:8080/api/events"
DEVICE_KEY = "sk_device_secret_door_key_12345"

SCENARIOS = [
    {
        "personLabel": "courier",
        "caption": "Package delivered at 14:20 by postal carrier and left on porch",
        "color": (240, 180, 50)
    },
    {
        "personLabel": "Alice",
        "caption": "Alice arrived home at 14:35 and door unlocked automatically",
        "color": (50, 200, 100)
    },
    {
        "personLabel": "unknown",
        "caption": "Unknown visitor approached porch and rang the doorbell",
        "color": (50, 50, 220)
    }
]

def create_synthetic_image(text, color):
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.rectangle(img, (180, 120), (460, 480), (60, 60, 60), -1)
    cv2.circle(img, (320, 240), 70, color, -1)
    cv2.putText(img, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    _, encoded = cv2.imencode(".jpg", img)
    return encoded.tobytes()

def seed_events():
    print(f"Connecting to Backend at {BACKEND_URL}...")
    headers = {"X-Device-Api-Key": DEVICE_KEY}

    for scenario in SCENARIOS:
        evt_id = str(uuid.uuid4())
        payload = {
            "id": evt_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "personLabel": scenario["personLabel"],
            "caption": scenario["caption"],
            "deviceId": "pi-front-door-01"
        }

        img_bytes = create_synthetic_image(scenario["personLabel"], scenario["color"])
        files = {
            "image": (f"{evt_id}.jpg", img_bytes, "image/jpeg"),
            "data": (None, json.dumps(payload), "application/json")
        }

        try:
            res = requests.post(BACKEND_URL, headers=headers, files=files, timeout=5)
            print(f"Uploaded event '{scenario['personLabel']}': HTTP {res.status_code}")
        except Exception as e:
            print(f"Could not connect to backend: {e}. (Make sure Spring Boot backend is running)")

if __name__ == "__main__":
    seed_events()
