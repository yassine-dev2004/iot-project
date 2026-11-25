import argparse
import sys
import time
import signal
import logging
import cv2
import numpy as np

from edge.config import (
    DEVICE_ID, DEVICE_API_KEY, BACKEND_URL,
    DATABASE_PATH, EVENT_COOLDOWN_SECONDS,
    GEMINI_API_KEY, GEMINI_MODEL,
    ENABLE_GPIO, DOORBELL_GPIO_PIN
)
from edge.storage import EdgeStorage
from edge.camera import create_camera_source
from edge.faces import FaceManager
from edge.llm import EventCaptioner
from edge.notifier import EventUploader
from edge.events import EventManager
from edge.mqtt_client import EdgeMQTTClient

# Setup Structured Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] (%(name)s) %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%SZ'
)
logger = logging.getLogger("edge.main")

running = True
wake_requested = False

def sigterm_handler(signum, frame):
    global running
    logger.info("Graceful shutdown signal received.")
    running = False

signal.signal(signal.SIGINT, sigterm_handler)
signal.signal(signal.SIGTERM, sigterm_handler)

def cmd_enroll(args):
    """Enrolls a known person locally without uploading embeddings to any external server."""
    logger.info(f"Starting enrollment for: '{args.name}' using source: '{args.source}'")
    storage = EdgeStorage(DATABASE_PATH)
    face_mgr = FaceManager(storage)
    camera = create_camera_source(args.source)

    print("Looking for face... Please look at the camera.")
    attempts = 0
    enrolled = False
    while attempts < 50:
        frame = camera.read_frame()
        if frame is not None:
            if face_mgr.enroll_face(args.name, frame):
                logger.info(f"SUCCESS: Face for '{args.name}' enrolled locally in {DATABASE_PATH}")
                print(f"Face successfully enrolled for '{args.name}'!")
                enrolled = True
                break
        attempts += 1
        time.sleep(0.1)

    camera.release()
    if not enrolled:
        logger.error("Could not detect a clear face to enroll. Please try again with better lighting.")
        sys.exit(1)

def cmd_run(args):
    """Runs the main smart door edge loop."""
    global running, wake_requested
    logger.info(f"Starting Smart Door Camera Edge (Device: {DEVICE_ID})")

    storage = EdgeStorage(DATABASE_PATH)
    face_mgr = FaceManager(storage)
    captioner = EventCaptioner(api_key=GEMINI_API_KEY, model_name=GEMINI_MODEL)
    uploader = EventUploader(backend_url=BACKEND_URL, device_api_key=DEVICE_API_KEY, storage=storage)
    event_mgr = EventManager(
        device_id=DEVICE_ID,
        storage=storage,
        face_manager=face_mgr,
        captioner=captioner,
        uploader=uploader,
        cooldown_seconds=EVENT_COOLDOWN_SECONDS
    )
    camera = create_camera_source(args.source)

    # Optional IoT MQTT Bridge
    def on_motion_detected(data):
        global wake_requested
        logger.info(f"IoT PIR Motion sensor triggered: {data}")
        wake_requested = True

    def on_doorbell_pressed(data):
        logger.info("IoT Doorbell button pressed!")
        frame = camera.read_frame()
        if frame is not None:
            evt = event_mgr.trigger_event(frame, person_label="visitor", reason="doorbell_press")
            if evt and mqtt_bridge:
                mqtt_bridge.publish_display(evt["caption"])

    mqtt_bridge = None
    if args.mqtt:
        mqtt_bridge = EdgeMQTTClient(
            broker_host=args.mqtt_host,
            on_motion_callback=on_motion_detected,
            on_bell_callback=on_doorbell_pressed
        )

    # Optional Physical GPIO Button (Raspberry Pi native)
    if ENABLE_GPIO:
        try:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(DOORBELL_GPIO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            logger.info(f"GPIO Doorbell configured on pin {DOORBELL_GPIO_PIN}")
        except Exception as e:
            logger.warning(f"Could not initialize RPi.GPIO: {e}")

    logger.info("Edge pipeline loop active. Monitoring doorstep...")
    last_outbox_drain = time.time()

    while running:
        frame = camera.read_frame()
        if frame is not None:
            event = event_mgr.process_frame(frame)
            if event:
                logger.info(f"EVENT PROCESSED -> Label: {event['personLabel']} | Caption: '{event['caption']}'")

                # Actuation feedback via MQTT if connected
                if mqtt_bridge:
                    mqtt_bridge.publish_display(event['caption'])
                    if event['personLabel'] not in ["unknown", "motion", "visitor"] and not event['personLabel'].startswith("spoof_"):
                        # Known authorized person -> unlock door for 10 s
                        mqtt_bridge.publish_unlock(10)
                    elif event['personLabel'] == "unknown":
                        mqtt_bridge.publish_alert("red_alarm")

        # Drain offline outbox periodically (every 15 s)
        if time.time() - last_outbox_drain > 15.0:
            uploader.drain_outbox()
            last_outbox_drain = time.time()

        time.sleep(args.poll_interval)

    camera.release()
    if mqtt_bridge:
        mqtt_bridge.stop()
    logger.info("Smart Door Edge stopped cleanly.")

def cmd_enroll_dir(args):
    """Enrolls all real-life person photos placed in a folder (filename stem = person name)."""
    import os
    folder = args.dir
    if not os.path.isdir(folder):
        logger.error(f"Directory not found: {folder}")
        sys.exit(1)

    storage = EdgeStorage(DATABASE_PATH)
    face_mgr = FaceManager(storage)
    exts = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
    count = 0
    for fname in sorted(os.listdir(folder)):
        if not fname.lower().endswith(exts):
            continue
        person_name = os.path.splitext(fname)[0].replace("_", " ").strip()
        fpath = os.path.join(folder, fname)
        img = cv2.imread(fpath)
        if img is not None and face_mgr.enroll_face(person_name, img):
            print(f"[OK] Enrolled '{person_name}' from {fname}")
            count += 1
        else:
            print(f"[SKIP] No face detected in {fname}")
    print(f"Done: {count} real-life person(s) enrolled locally in {DATABASE_PATH}.")


def cmd_summary(args):
    """Displays local statistics and offline outbox status."""
    storage = EdgeStorage(DATABASE_PATH)
    known = storage.load_known_faces()
    pending = storage.get_pending_events(limit=100)
    print("="*50)
    print(f"SMART DOOR CAMERA EDGE SUMMARY ({DEVICE_ID})")
    print("="*50)
    print(f"Known Local Profiles ({len(known)}):")
    for kf in known:
        print(f" - ID: {kf['id']} | Name: {kf['name']}")
    print(f"\nOffline Outbox Pending Events: {len(pending)}")
    for p in pending:
        print(f" - Event {p['event_id']} (Retries: {p['retry_count']})")
    print("="*50)

def main():
    parser = argparse.ArgumentParser(description="Smart Door Camera Edge (Raspberry Pi)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # enroll
    parser_enroll = subparsers.add_parser("enroll", help="Enroll a new face locally")
    parser_enroll.add_argument("--name", required=True, help="Person name")
    parser_enroll.add_argument("--source", default="video.mp4", help="Camera source (webcam:0, picam, or video path)")

    # run
    parser_run = subparsers.add_parser("run", help="Run the continuous edge surveillance loop")
    parser_run.add_argument("--source", default="video.mp4", help="Camera source (webcam:0, picam, or video path)")
    parser_run.add_argument("--poll-interval", type=float, default=0.05, help="Frame delay interval")
    parser_run.add_argument("--mqtt", action="store_true", help="Enable MQTT IoT node integration")
    parser_run.add_argument("--mqtt-host", default="localhost", help="MQTT broker host")

    # enroll-dir
    parser_enrolldir = subparsers.add_parser("enroll-dir", help="Enroll all real photos in a folder (e.g. edge/known_people)")
    parser_enrolldir.add_argument("--dir", default="edge/known_people", help="Folder containing person photos (Name.jpg)")

    # summary
    parser_summary = subparsers.add_parser("summary", help="Show local storage & outbox stats")

    args = parser.parse_args()
    if args.command == "enroll":
        cmd_enroll(args)
    elif args.command == "enroll-dir":
        cmd_enroll_dir(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "summary":
        cmd_summary(args)

if __name__ == "__main__":
    main()
