import time
import os
import cv2
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from edge.storage import EdgeStorage
from edge.faces import FaceManager
from edge.llm import EventCaptioner
from edge.notifier import EventUploader

logger = logging.getLogger(__name__)

class EventManager:
    """
    Manages event triggers, state machine, debouncing, cooldown,
    snapshot JPEG serialization and event dispatch.
    """
    def __init__(self,
                 device_id: str,
                 storage: EdgeStorage,
                 face_manager: FaceManager,
                 captioner: EventCaptioner,
                 uploader: EventUploader,
                 cooldown_seconds: float = 30.0,
                 snapshot_dir: str = "edge/snapshots"):
        self.device_id = device_id
        self.storage = storage
        self.face_manager = face_manager
        self.captioner = captioner
        self.uploader = uploader
        self.cooldown_seconds = cooldown_seconds
        self.snapshot_dir = snapshot_dir

        os.makedirs(self.snapshot_dir, exist_ok=True)
        self.last_event_time = 0.0
        self.last_person_label = None

    def process_frame(self, frame) -> Optional[Dict[str, Any]]:
        if frame is None:
            return None

        # Local face detection & recognition
        person_label, liveness_ok, face_crop = self.face_manager.detect_and_recognize(frame)

        # Trigger check (motion, unknown visitor, or recognized person)
        current_time = time.time()
        cooldown_elapsed = (current_time - self.last_event_time) > self.cooldown_seconds
        label_changed = (person_label != self.last_person_label)

        if not (cooldown_elapsed or label_changed):
            return None # Suppress duplicate within cooldown window

        return self.trigger_event(frame, person_label, reason="camera_detection")

    def trigger_event(self, frame, person_label: str, reason: str = "camera_detection") -> Optional[Dict[str, Any]]:
        current_time = time.time()
        self.last_event_time = current_time
        self.last_person_label = person_label

        event_id = str(uuid.uuid4())
        timestamp_iso = datetime.utcnow().isoformat() + "Z"

        # Save snapshot JPEG locally
        image_filename = f"event_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{event_id[:8]}.jpg"
        image_path = os.path.join(self.snapshot_dir, image_filename)

        # Encode JPEG
        success, encoded_jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not success:
            logger.error("Failed to encode snapshot image to JPEG.")
            return None

        with open(image_path, "wb") as f:
            f.write(encoded_jpg.tobytes())

        # Generate Gemini caption
        caption = self.captioner.generate_caption(encoded_jpg.tobytes(), person_label)

        # Ignore non-events if captioner explicitly returns IGNORE
        if caption.strip().upper() == "IGNORE":
            logger.info(f"Event {event_id} ignored as per Gemini caption.")
            if os.path.exists(image_path):
                os.remove(image_path)
            return None

        payload = {
            "id": event_id,
            "timestamp": timestamp_iso,
            "personLabel": person_label,
            "caption": caption,
            "deviceId": self.device_id,
            "triggerReason": reason
        }

        # Store in offline outbox first
        self.storage.queue_event(event_id, payload, image_path)

        # Attempt immediate upload
        self.uploader.upload_event(event_id, payload, image_path)

        return payload
