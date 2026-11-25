"""
Sentinel Home — VPS Cloud Sync Hub (Port 8080)
Serves:
- Web Dashboard       : http://<VPS_IP>:8080/web/index.html
- 3D Full-House Twin  : http://<VPS_IP>:8080/sim/index.html
- Android APK Download: http://<VPS_IP>:8080/SentinelHome.apk
- Live PC Camera Relay: POST /api/camera/push (from PC) -> GET /api/camera/frame (to Phone & Web)
- Door Remote Control : POST /api/door/unlock, /lock, /alarm <-> synced live across Phone, Web, 3D & PC
- Events & Snapshots  : GET/POST /api/events, /api/events/{id}/image, /api/summary/today
"""

import os
import time
import uuid
import json
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import Response, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

SNAPSHOTS_DIR = "vps_snapshots"
os.makedirs(SNAPSHOTS_DIR, exist_ok=True)

app = FastAPI(title="Sentinel Home VPS Sync Hub", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HubState:
    def __init__(self):
        self.lock = threading.Lock()
        self.latest_jpg: Optional[bytes] = None
        self.last_frame_ts: float = 0.0
        self.current_person: str = "none"
        self.door_unlocked: bool = False
        self.unlock_until: float = 0.0
        self.alarm_active: bool = False
        self.alarm_until: float = 0.0
        self.known_people: List[Dict[str, Any]] = []
        self.pending_enroll_name: Optional[str] = None
        self.pending_delete_name: Optional[str] = None
        self.events: List[Dict[str, Any]] = []

    def check_timers(self):
        now = time.time()
        if self.door_unlocked and now > self.unlock_until:
            self.door_unlocked = False
        if self.alarm_active and now > self.alarm_until:
            self.alarm_active = False

    def add_event(self, person_label: str, caption: str, jpg_bytes: Optional[bytes], device_id: str = "pc-front-door-01"):
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
            self.events = self.events[:150]
        return evt


hub = HubState()


# ----------------- PC EDGE CAMERA PUSH & SYNC -----------------
@app.post("/api/camera/push")
async def push_camera_frame(
    image: UploadFile = File(...),
    current_person: str = Form("none"),
    known_people: str = Form("[]"),
    auto_unlock: str = Form("false"),
):
    jpg = await image.read()
    with hub.lock:
        hub.latest_jpg = jpg
        hub.last_frame_ts = time.time()
        hub.current_person = current_person
        try:
            hub.known_people = json.loads(known_people)
        except Exception:
            pass
        if auto_unlock.lower() == "true" and not hub.door_unlocked:
            hub.door_unlocked = True
            hub.unlock_until = time.time() + 10
            hub.alarm_active = False

        # Deliver any pending remote enroll/delete command to the PC Edge
        enroll_cmd = hub.pending_enroll_name
        delete_cmd = hub.pending_delete_name
        hub.pending_enroll_name = None
        hub.pending_delete_name = None

    hub.check_timers()
    return {
        "unlocked": hub.door_unlocked,
        "alarmActive": hub.alarm_active,
        "enrollName": enroll_cmd,
        "deleteName": delete_cmd,
    }


@app.get("/api/camera/frame")
def get_camera_frame():
    with hub.lock:
        jpg = hub.latest_jpg
    if not jpg:
        raise HTTPException(status_code=503, detail="Waiting for PC camera agent to connect...")
    return Response(content=jpg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


# ----------------- DOOR STATUS & REMOTE CONTROLS -----------------
@app.get("/api/door/status")
def get_door_status():
    hub.check_timers()
    now = time.time()
    rem = max(0, int(hub.unlock_until - now)) if hub.door_unlocked else 0
    cam_online = (now - hub.last_frame_ts) < 6.0
    return {
        "unlocked": hub.door_unlocked,
        "unlockRemainingSeconds": rem,
        "alarmActive": hub.alarm_active,
        "currentPerson": hub.current_person if cam_online else "none",
        "cameraActive": cam_online,
        "knownPeopleCount": len(hub.known_people),
        "eventsCount": len(hub.events),
    }


@app.post("/api/door/unlock")
def unlock_door(duration: int = 10):
    with hub.lock:
        hub.door_unlocked = True
        hub.unlock_until = time.time() + duration
        hub.alarm_active = False
        jpg = hub.latest_jpg
    hub.add_event("remote_unlock", f"Door unlocked remotely via Mobile/Web ({duration}s)", jpg)
    return {"status": "unlocked", "duration": duration}


@app.post("/api/door/lock")
def lock_door():
    with hub.lock:
        hub.door_unlocked = False
        hub.unlock_until = 0.0
    return {"status": "locked"}


@app.post("/api/door/alarm")
def trigger_alarm(duration: int = 8):
    with hub.lock:
        hub.alarm_active = True
        hub.alarm_until = time.time() + duration
        hub.door_unlocked = False
        jpg = hub.latest_jpg
    hub.add_event("unknown", "Security alarm triggered remotely via Mobile/Web", jpg)
    return {"status": "alarm_triggered"}


# ----------------- PEOPLE MANAGEMENT (RELAYED TO PC EDGE) -----------------
@app.get("/api/people")
def list_people():
    return hub.known_people


@app.post("/api/people/enroll-live")
def request_remote_enroll(name: str = Form(...)):
    clean = name.strip()
    if not clean:
        raise HTTPException(status_code=400, detail="Name required")
    with hub.lock:
        hub.pending_enroll_name = clean
    return {"status": "queued_for_pc_camera", "name": clean}


@app.delete("/api/people/{name}")
def request_remote_delete(name: str):
    with hub.lock:
        hub.pending_delete_name = name
        hub.known_people = [p for p in hub.known_people if p.get("name") != name]
    return {"status": "deleted", "name": name}


# ----------------- EVENTS, SNAPSHOTS & SUMMARY -----------------
@app.get("/api/events")
def get_events():
    return {"content": hub.events}


@app.post("/api/events")
async def ingest_event(data: str = Form(...), image: Optional[UploadFile] = File(None)):
    payload = json.loads(data)
    img_bytes = await image.read() if image else None
    return hub.add_event(
        payload.get("personLabel", "unknown"),
        payload.get("caption", "Activity at front entrance"),
        img_bytes,
        payload.get("deviceId", "pc-front-door-01"),
    )


@app.get("/api/events/{event_id}/image")
def get_event_image(event_id: str):
    for e in hub.events:
        if e["id"] == event_id and e.get("snapshotPath") and os.path.exists(e["snapshotPath"]):
            return FileResponse(e["snapshotPath"], media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Snapshot not found")


@app.get("/api/summary/today")
def get_summary_today():
    if not hub.events:
        return {"summary": "No entrance events yet today. VPS hub is waiting for PC camera activity."}
    lines = [f"- {e['personLabel']}: {e['caption']}" for e in hub.events[:10]]
    return {"summary": f"{len(hub.events)} entrance event(s) synced today:\n" + "\n".join(lines)}


@app.get("/")
def root_redirect():
    return RedirectResponse(url="/web/index.html")


# Serve Web Dashboard (/web), 3D Twin (/sim), and APK (/SentinelHome.apk) directly from VPS!
if os.path.isdir("web"):
    app.mount("/web", StaticFiles(directory="web", html=True), name="web")
if os.path.isdir("sim"):
    app.mount("/sim", StaticFiles(directory="sim", html=True), name="sim")


@app.get("/SentinelHome.apk")
def download_apk():
    if os.path.exists("SentinelHome.apk"):
        return FileResponse("SentinelHome.apk", media_type="application/vnd.android.package-archive", filename="SentinelHome.apk")
    raise HTTPException(status_code=404, detail="APK not uploaded to VPS yet")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
