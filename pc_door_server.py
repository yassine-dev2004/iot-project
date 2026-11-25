"""
Sentinel Home — Live PC Webcam, Local YuNet/SFace Face Recognition, Remote Lock & Mobile API Server.
Runs on http://0.0.0.0:8080 so your Android APK and Web Dashboard can:
- Watch the live PC webcam feed (/api/camera/frame & /api/camera/stream)
- See who is standing in front of the door in real time (/api/door/status)
- Remotely UNLOCK (10s), LOCK, or trigger ALARM (/api/door/unlock, /lock, /alarm)
- Enroll real people directly from the PC webcam or uploaded photos (/api/people/enroll-live, /enroll-photo)
- View real-life visitor snapshots & Gemini captions (/api/events, /api/events/{id}/image)
"""

import os
import cv2
import time
import uuid
import json
import sqlite3
import threading
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

import numpy as np
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import Response, StreamingResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from edge.config import (
    DEVICE_ID, DATABASE_PATH, GEMINI_API_KEY, GEMINI_MODEL, EVENT_COOLDOWN_SECONDS
)
from edge.storage import EdgeStorage
from edge.faces import FaceManager
from edge.llm import EventCaptioner
from edge.mqtt_client import EdgeMQTTClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (DoorServer) %(message)s")
logger = logging.getLogger("pc_door_server")

SNAPSHOTS_DIR = os.path.join("edge", "snapshots")
os.makedirs(SNAPSHOTS_DIR, exist_ok=True)

app = FastAPI(title="Sentinel Home Live PC Camera & Mobile API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage = EdgeStorage(DATABASE_PATH)
face_mgr = FaceManager(storage)
captioner = EventCaptioner(api_key=GEMINI_API_KEY, model_name=GEMINI_MODEL)

mqtt_host = os.getenv("MQTT_HOST", "")
mqtt_client = EdgeMQTTClient(broker_host=mqtt_host) if mqtt_host else None


class DoorState:
    def __init__(self):
        self.lock = threading.Lock()
        self.frame_event = threading.Condition()
        self.frame_seq: int = 0
        self.latest_raw_frame: Optional[np.ndarray] = None
        self.latest_annotated_jpg: Optional[bytes] = None
        self.camera_active: bool = False
        self.current_person: str = "none"
        self.door_unlocked: bool = False
        self.unlock_until: float = 0.0
        self.alarm_active: bool = False
        self.alarm_until: float = 0.0
        self.events: List[Dict[str, Any]] = []
        self.last_event_ts: float = 0.0
        self.last_event_person: str = ""

    def unlock(self, duration: int = 10, reason: str = "remote"):
        with self.lock:
            self.door_unlocked = True
            self.unlock_until = time.time() + duration
            self.alarm_active = False
        logger.info(f"DOOR UNLOCKED for {duration}s (reason={reason})")
        if mqtt_client:
            mqtt_client.publish_unlock(duration)

    def lock_now(self):
        with self.lock:
            self.door_unlocked = False
            self.unlock_until = 0.0
        logger.info("DOOR LOCKED manually")

    def trigger_alarm(self, duration: int = 8):
        with self.lock:
            self.alarm_active = True
            self.alarm_until = time.time() + duration
            self.door_unlocked = False
        logger.warning(f"SECURITY ALARM triggered for {duration}s")
        if mqtt_client:
            mqtt_client.publish_alert("red_alarm")

    def add_event(self, person_label: str, caption: str, jpg_bytes: Optional[bytes], device_id: str = DEVICE_ID):
        evt_id = str(uuid.uuid4())
        ts = datetime.utcnow().isoformat() + "Z"
        snap_path = None
        if jpg_bytes:
            snap_path = os.path.join(SNAPSHOTS_DIR, f"{evt_id}.jpg")
            with open(snap_path, "wb") as f:
                f.write(jpg_bytes)
        evt = {
            "id": evt_id,
            "timestamp": ts,
            "personLabel": person_label,
            "caption": caption,
            "snapshotPath": snap_path,
            "deviceId": device_id,
        }
        with self.lock:
            self.events.insert(0, evt)
            self.events = self.events[:100]
        if mqtt_client:
            mqtt_client.publish_display(caption)
        return evt


state = DoorState()


def _make_placeholder_frame(msg: str = "Waiting for PC Webcam...") -> np.ndarray:
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[:] = (15, 15, 18)
    cv2.putText(img, "SENTINEL HOME LIVE CAMERA", (135, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (250, 250, 250), 2)
    cv2.putText(img, msg, (170, 255), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (161, 161, 170), 2)
    cv2.putText(img, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), (20, 460), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (113, 113, 122), 1)
    return img


def _draw_corner_box(img, x, y, w, h, color, thickness=2, corner_len=16):
    """Draws sleek architectural corner-bracket targeting reticle around a face."""
    cl = min(corner_len, w // 3, h // 3)
    # Top-left
    cv2.line(img, (x, y), (x + cl, y), color, thickness)
    cv2.line(img, (x, y), (x, y + cl), color, thickness)
    # Top-right
    cv2.line(img, (x + w, y), (x + w - cl, y), color, thickness)
    cv2.line(img, (x + w, y), (x + w, y + cl), color, thickness)
    # Bottom-left
    cv2.line(img, (x, y + h), (x + cl, y + h), color, thickness)
    cv2.line(img, (x, y + h), (x, y + h - cl), color, thickness)
    # Bottom-right
    cv2.line(img, (x + w, y + h), (x + w - cl, y + h), color, thickness)
    cv2.line(img, (x + w, y + h), (x + w, y + h - cl), color, thickness)


def ai_recognition_worker():
    """
    Dedicated background thread for YuNet + SFace + Smart Access State Machine:
    - Requires 2 consistent frames before auto-unlocking (prevents false triggers)
    - Smart re-entry cooldown (15s) so staying in front of PC doesn't spam unlock loops
    - Auto-resets immediately when person leaves frame for > 3s
    - Loitering Guard: unknown visitor lingering > 4s triggers alert while keeping door locked
    """
    consecutive_label = ""
    consecutive_hits = 0
    last_auto_unlock_person = ""
    last_auto_unlock_ts = 0.0
    person_absent_since = 0.0
    unknown_first_seen = 0.0
    unknown_alerted = False

    while True:
        with state.lock:
            raw_copy = state.latest_raw_frame.copy() if (state.camera_active and state.latest_raw_frame is not None) else None
        if raw_copy is None:
            time.sleep(0.2)
            continue

        now = time.time()
        label, liveness_ok, _ = face_mgr.detect_and_recognize(raw_copy)
        state.current_person = "none" if label == "motion" else label

        if label == "motion":
            consecutive_label = ""
            consecutive_hits = 0
            unknown_first_seen = 0.0
            unknown_alerted = False
            if person_absent_since == 0.0:
                person_absent_since = now
            elif (now - person_absent_since) > 3.0:
                # Person left the porch -> reset auto-unlock cooldown so next arrival unlocks immediately
                last_auto_unlock_person = ""
                last_auto_unlock_ts = 0.0
            time.sleep(0.14)
            continue

        person_absent_since = 0.0
        if label == consecutive_label:
            consecutive_hits += 1
        else:
            consecutive_label = label
            consecutive_hits = 1

        is_known = (
            label not in ("motion", "unknown", "none")
            and not label.startswith("spoof_")
            and liveness_ok
        )

        # 1. Authorized Person Verified (2 consecutive frames + smart cooldown)
        if is_known and consecutive_hits >= 2:
            unknown_first_seen = 0.0
            unknown_alerted = False
            same_person_cooldown = (label == last_auto_unlock_person) and ((now - last_auto_unlock_ts) < 15.0)
            if not state.door_unlocked and not same_person_cooldown:
                last_auto_unlock_person = label
                last_auto_unlock_ts = now
                state.unlock(10, reason=f"face_recognized:{label}")
                ok_jpg, enc = cv2.imencode(".jpg", raw_copy, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
                if ok_jpg:
                    conf_pct = int(face_mgr.last_confidence * 100)
                    cap_text = captioner.generate_caption(enc.tobytes(), label)
                    if cap_text.strip().upper() != "IGNORE":
                        state.add_event(label, f"{cap_text} (SFace {conf_pct}%)", enc.tobytes())

        # 2. Unknown Visitor Loitering Guard (> 4 seconds -> alert while keeping door strictly LOCKED)
        elif label == "unknown" and consecutive_hits >= 2:
            if unknown_first_seen == 0.0:
                unknown_first_seen = now
            elif (now - unknown_first_seen) >= 4.0 and not unknown_alerted:
                unknown_alerted = True
                if not state.door_unlocked:
                    state.trigger_alarm(duration=6)
                ok_jpg, enc = cv2.imencode(".jpg", raw_copy, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
                if ok_jpg:
                    cap_text = captioner.generate_caption(enc.tobytes(), "unknown")
                    if cap_text.strip().upper() != "IGNORE":
                        state.add_event("unknown", f"{cap_text} — Access denied", enc.tobytes())

        # 3. Anti-Spoof Attempt Detected
        elif label.startswith("spoof_") and consecutive_hits >= 2:
            if (now - state.last_event_ts) > 10.0:
                state.last_event_ts = now
                state.trigger_alarm(duration=6)
                ok_jpg, enc = cv2.imencode(".jpg", raw_copy, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
                if ok_jpg:
                    state.add_event("unknown", f"Photo spoof blocked for {label[6:]} — Door kept locked", enc.tobytes())

        time.sleep(0.14)


def webcam_worker():
    """High-speed 25-30 FPS PC webcam capture & lightweight HUD annotation loop."""
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(0)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)

    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        state.camera_active = True
        logger.info("PC Webcam opened successfully (640x480 @ 30 FPS).")
    else:
        logger.warning("No physical webcam detected on index 0. Running standby feed.")

    while True:
        now = time.time()
        if state.door_unlocked and now > state.unlock_until:
            state.door_unlocked = False
        if state.alarm_active and now > state.alarm_until:
            state.alarm_active = False

        frame = None
        if cap.isOpened():
            ok, f = cap.read()
            if ok and f is not None:
                frame = f
                state.camera_active = True

        if frame is None:
            frame = _make_placeholder_frame("Connectez une webcam PC (index 0)")
            state.camera_active = False
            time.sleep(0.25)

        annotated = frame.copy()

        # Draw sleek corner-bracket reticles around ALL detected faces with confidence %
        dets = getattr(face_mgr, "last_detections", [])
        if dets and state.camera_active and state.current_person != "none":
            for det in dets:
                fx, fy, fw, fh = det["box"]
                lbl = det["label"]
                conf_pct = int(det.get("confidence", 0.0) * 100)
                is_known_det = det.get("is_known", False)
                bcol = (129, 185, 16) if is_known_det else (68, 68, 239)
                _draw_corner_box(annotated, fx, fy, fw, fh, bcol, thickness=2, corner_len=18)
                tag = f"{lbl.upper()} {conf_pct}%" if is_known_det else "UNKNOWN • LOCKED"
                tag_w = max(fw, len(tag) * 9 + 14)
                ty0 = max(44, fy - 24)
                cv2.rectangle(annotated, (fx, ty0), (fx + tag_w, ty0 + 22), bcol, -1)
                cv2.putText(annotated, tag, (fx + 6, ty0 + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)

        # Clean matte top HUD overlay + live countdown progress bar when door is unlocked
        person_disp = state.current_person
        if state.door_unlocked:
            rem_f = max(0.0, state.unlock_until - now)
            rem = int(rem_f) + (1 if rem_f > 0 else 0)
            cv2.rectangle(annotated, (0, 0), (640, 42), (16, 115, 70), -1)
            bar_w = int(640 * min(1.0, rem_f / 10.0))
            cv2.rectangle(annotated, (0, 39), (bar_w, 42), (167, 243, 208), -1)
            cv2.putText(annotated, f"DOOR OPEN ({rem}s) - {person_disp.upper()}", (14, 27),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.68, (255, 255, 255), 2)
        elif state.alarm_active:
            cv2.rectangle(annotated, (0, 0), (640, 42), (35, 35, 200), -1)
            cv2.putText(annotated, "SECURITY ALARM • DOOR LOCKED", (14, 27),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.68, (255, 255, 255), 2)
        else:
            cv2.rectangle(annotated, (0, 0), (640, 38), (15, 15, 18), -1)
            color = (129, 185, 16) if person_disp not in ("none", "unknown") else (68, 68, 239) if person_disp == "unknown" else (240, 240, 245)
            status_txt = f"ENTRANCE: {person_disp.upper()}" if person_disp != "none" else "ENTRANCE SECURED • LOCKED"
            cv2.putText(annotated, status_txt, (14, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.60, color, 2)

        cv2.putText(annotated, datetime.now().strftime("%H:%M:%S"), (548, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.56, (180, 180, 190), 1)

        ok_enc, jpg = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 68])
        with state.lock:
            state.latest_raw_frame = frame
            if ok_enc:
                state.latest_annotated_jpg = jpg.tobytes()
                state.frame_seq += 1
        with state.frame_event:
            state.frame_event.notify_all()

        time.sleep(0.015)


@app.on_event("startup")
def on_startup():
    threading.Thread(target=webcam_worker, daemon=True).start()
    threading.Thread(target=ai_recognition_worker, daemon=True).start()


@app.get("/api/camera/frame")
def get_camera_frame():
    with state.lock:
        jpg = state.latest_annotated_jpg
    if not jpg:
        _, enc = cv2.imencode(".jpg", _make_placeholder_frame())
        jpg = enc.tobytes()
    return Response(content=jpg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.get("/api/camera/stream")
def stream_camera_mjpeg():
    def gen():
        last_seq = -1
        while True:
            with state.frame_event:
                if state.frame_seq == last_seq:
                    state.frame_event.wait(timeout=0.5)
                last_seq = state.frame_seq
            with state.lock:
                jpg = state.latest_annotated_jpg
            if jpg:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " +
                       str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
    return StreamingResponse(
        gen(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "X-Accel-Buffering": "no"},
    )


@app.get("/api/door/status")
def get_door_status():
    now = time.time()
    rem = max(0, int(state.unlock_until - now)) if state.door_unlocked else 0
    return {
        "unlocked": state.door_unlocked,
        "unlockRemainingSeconds": rem,
        "alarmActive": state.alarm_active,
        "currentPerson": state.current_person,
        "cameraActive": state.camera_active,
        "knownPeopleCount": len(storage.load_known_faces()),
        "eventsCount": len(state.events),
    }


@app.post("/api/door/unlock")
def unlock_door_remote(duration: int = 10):
    state.unlock(duration=duration, reason="mobile_app_remote")
    with state.lock:
        jpg = state.latest_annotated_jpg
    state.add_event("remote_unlock", f"Door unlocked remotely via Sentinel App ({duration}s)", jpg)
    return {"status": "unlocked", "duration": duration}


@app.post("/api/door/lock")
def lock_door_remote():
    state.lock_now()
    return {"status": "locked"}


@app.post("/api/door/alarm")
def alarm_door_remote():
    state.trigger_alarm(duration=8)
    with state.lock:
        jpg = state.latest_annotated_jpg
    state.add_event("unknown", "Security alarm triggered remotely via Sentinel App", jpg)
    return {"status": "alarm_triggered"}


@app.get("/api/people")
def list_people():
    return [{"id": p["id"], "name": p["name"]} for p in storage.load_known_faces()]


@app.post("/api/people/enroll-live")
def enroll_person_from_live_webcam(name: str = Form(...)):
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Name is required")
    with state.lock:
        frame = state.latest_raw_frame.copy() if state.latest_raw_frame is not None else None
    if frame is None:
        raise HTTPException(status_code=503, detail="PC webcam frame not available")
    ok = face_mgr.enroll_face(clean_name, frame)
    if not ok:
        raise HTTPException(status_code=422, detail="No face detected in front of PC camera. Look at the camera and try again.")
    return {"status": "enrolled", "name": clean_name}


@app.post("/api/people/enroll-photo")
async def enroll_person_from_photo(name: str = Form(...), image: UploadFile = File(...)):
    clean_name = name.strip()
    img_bytes = await image.read()
    arr = np.frombuffer(img_bytes, np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None or not face_mgr.enroll_face(clean_name, frame):
        raise HTTPException(status_code=422, detail="No clear face detected in uploaded photo.")
    return {"status": "enrolled", "name": clean_name}


@app.delete("/api/people/{name}")
def delete_person(name: str):
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute("DELETE FROM known_faces WHERE name = ?", (name,))
        conn.commit()
    return {"status": "deleted", "name": name}


@app.get("/api/events")
def get_events():
    return {"content": state.events}


@app.post("/api/events")
async def ingest_event(data: str = Form(...), image: Optional[UploadFile] = File(None)):
    payload = json.loads(data)
    img_bytes = await image.read() if image else None
    evt = state.add_event(
        payload.get("personLabel", "unknown"),
        payload.get("caption", "Activity at front entrance"),
        img_bytes,
        payload.get("deviceId", DEVICE_ID),
    )
    return evt


@app.get("/api/events/{event_id}/image")
def get_event_image(event_id: str):
    for e in state.events:
        if e["id"] == event_id and e.get("snapshotPath") and os.path.exists(e["snapshotPath"]):
            return FileResponse(e["snapshotPath"], media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Snapshot not found")


@app.get("/api/summary/today")
def get_summary_today():
    if not state.events:
        return {"summary": "No entrance events recorded yet today. Live PC camera monitoring is active."}
    lines = [f"- {e['personLabel']}: {e['caption']}" for e in state.events[:10]]
    return {"summary": f"{len(state.events)} entrance event(s) recorded today:\n" + "\n".join(lines)}


@app.get("/")
def root_redirect():
    return RedirectResponse(url="/web/index.html")


@app.get("/SentinelHome.apk")
def download_apk():
    if os.path.exists("SentinelHome.apk"):
        return FileResponse("SentinelHome.apk", media_type="application/vnd.android.package-archive", filename="SentinelHome.apk")
    raise HTTPException(status_code=404, detail="APK not found")


if os.path.isdir("web"):
    app.mount("/web", StaticFiles(directory="web", html=True), name="web")
if os.path.isdir("sim"):
    app.mount("/sim", StaticFiles(directory="sim", html=True), name="sim")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8085)
