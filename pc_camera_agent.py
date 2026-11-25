"""
Sentinel Home — PC Camera Edge Sync Agent
Runs on your Windows PC / Raspberry Pi with the physical webcam:
1. Runs OpenCV YuNet + SFace 100% locally (embeddings NEVER leave your PC).
2. Streams live annotated camera frames to your VPS (POST /api/camera/push).
3. Receives remote Unlock / Lock / Alarm / Enroll commands from your Android APK & Web Dashboard on the VPS.
4. Uploads event snapshots + Gemini captions to your VPS (/api/events).

Usage:
  python pc_camera_agent.py --vps http://<YOUR_VPS_IP>:8080
"""

import argparse
import os
import cv2
import time
import json
import sqlite3
import requests
import logging
from datetime import datetime

from edge.config import DEVICE_ID, DATABASE_PATH, GEMINI_API_KEY, GEMINI_MODEL, EVENT_COOLDOWN_SECONDS
from edge.storage import EdgeStorage
from edge.faces import FaceManager
from edge.llm import EventCaptioner

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (PC-Agent) %(message)s")
logger = logging.getLogger("pc_camera_agent")


def run_agent(vps_url: str, camera_idx: int = 0):
    vps_url = vps_url.rstrip("/")
    storage = EdgeStorage(DATABASE_PATH)
    face_mgr = FaceManager(storage)
    captioner = EventCaptioner(api_key=GEMINI_API_KEY, model_name=GEMINI_MODEL)

    cap = cv2.VideoCapture(camera_idx, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(camera_idx)
    if not cap.isOpened():
        cap = cv2.VideoCapture(camera_idx)
    if not cap.isOpened():
        logger.error("Could not open PC webcam!")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    logger.info(f"PC Webcam active! Syncing live with VPS: {vps_url}")

    last_event_ts = 0.0
    last_event_person = ""
    remote_unlocked = False
    remote_alarm = False
    frame_idx = 0

    while True:
        ok, raw = cap.read()
        if not ok or raw is None:
            time.sleep(0.1)
            continue

        annotated = raw.copy()
        current_person = "none"
        auto_unlock = False

        # Local face detection & recognition (100% private on PC)
        label, liveness_ok, _ = face_mgr.detect_and_recognize(raw)
        current_person = "none" if label == "motion" else label

        is_known = label not in ("motion", "unknown", "none") and not label.startswith("spoof_") and liveness_ok
        if is_known:
            auto_unlock = True

        # Draw bounding box on face
        fbox = getattr(face_mgr, "last_face_box", None)
        if fbox and current_person != "none":
            fx, fy, fw, fh = fbox
            is_unk = current_person == "unknown"
            col = (68, 68, 239) if is_unk else (129, 185, 16)
            cv2.rectangle(annotated, (fx, fy), (fx + fw, fy + fh), col, 2)
            tag = "UNKNOWN VISITOR" if is_unk else f"{current_person.upper()} (VERIFIED)"
            cv2.rectangle(annotated, (fx, max(42, fy - 24)), (fx + max(fw, 175), max(42, fy)), col, -1)
            cv2.putText(annotated, tag, (fx + 6, max(58, fy - 7)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Top HUD banner
        if remote_unlocked or auto_unlock:
            cv2.rectangle(annotated, (0, 0), (640, 42), (16, 115, 70), -1)
            cv2.putText(annotated, f"DOOR UNLOCKED - {current_person.upper()}", (14, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2)
        elif remote_alarm:
            cv2.rectangle(annotated, (0, 0), (640, 42), (35, 35, 200), -1)
            cv2.putText(annotated, "SECURITY ALARM ACTIVE", (14, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2)
        else:
            cv2.rectangle(annotated, (0, 0), (640, 38), (15, 15, 18), -1)
            cv2.putText(annotated, f"VPS SYNC LIVE | {datetime.now().strftime('%H:%M:%S')}", (14, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (240, 240, 245), 2)

        ok_enc, jpg = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        if ok_enc:
            known_list = [{"id": p["id"], "name": p["name"]} for p in storage.load_known_faces()]
            try:
                res = requests.post(
                    f"{vps_url}/api/camera/push",
                    files={"image": ("frame.jpg", jpg.tobytes(), "image/jpeg")},
                    data={
                        "current_person": current_person,
                        "known_people": json.dumps(known_list),
                        "auto_unlock": "true" if auto_unlock else "false",
                    },
                    timeout=3.0,
                )
                if res.status_code == 200:
                    cmd = res.json()
                    remote_unlocked = cmd.get("unlocked", False)
                    remote_alarm = cmd.get("alarmActive", False)
                    if cmd.get("enrollName"):
                        ok_en = face_mgr.enroll_face(cmd["enrollName"], raw)
                        logger.info(f"Remote enroll '{cmd['enrollName']}': {'SUCCESS' if ok_en else 'NO FACE'}")
                    if cmd.get("deleteName"):
                        with sqlite3.connect(DATABASE_PATH) as conn:
                            conn.execute("DELETE FROM known_faces WHERE name = ?", (cmd["deleteName"],))
                            conn.commit()
                        logger.info(f"Remote deleted profile '{cmd['deleteName']}'")
            except Exception as e:
                if frame_idx % 10 == 0:
                    logger.warning(f"Waiting for VPS {vps_url}: {e}")

        # Upload event snapshot to VPS when someone arrives
        now = time.time()
        if current_person != "none" and ((now - last_event_ts) > min(EVENT_COOLDOWN_SECONDS, 15.0) or current_person != last_event_person):
            last_event_ts = now
            last_event_person = current_person
            ok_raw, raw_jpg = cv2.imencode(".jpg", raw, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if ok_raw:
                cap_txt = captioner.generate_caption(raw_jpg.tobytes(), current_person)
                if cap_txt.strip().upper() != "IGNORE":
                    try:
                        requests.post(
                            f"{vps_url}/api/events",
                            data={"data": json.dumps({
                                "id": f"evt-{int(now)}",
                                "timestamp": datetime.utcnow().isoformat() + "Z",
                                "personLabel": current_person,
                                "caption": cap_txt,
                                "deviceId": DEVICE_ID,
                            })},
                            files={"image": ("snapshot.jpg", raw_jpg.tobytes(), "image/jpeg")},
                            timeout=5.0,
                        )
                        logger.info(f"Event synced to VPS: {current_person} -> {cap_txt}")
                    except Exception:
                        pass

        frame_idx += 1
        time.sleep(0.35)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="PC Camera Edge Agent syncing to VPS Hub")
    p.add_argument("--vps", required=True, help="VPS Hub URL, e.g. http://1.2.3.4:8080")
    p.add_argument("--camera", type=int, default=0, help="Webcam index (default 0)")
    args = p.parse_args()
    run_agent(args.vps, args.camera)
