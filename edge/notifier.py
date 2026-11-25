import os
import json
import logging
import requests
from edge.storage import EdgeStorage

logger = logging.getLogger(__name__)

class EventUploader:
    """
    Transmits captured events and JPEG snapshots to Spring Boot backend via HTTP POST multipart.
    Handles authentication via X-Device-Api-Key header.
    Features automatic retry and offline SQLite outbox draining.
    """
    def __init__(self, backend_url: str, device_api_key: str, storage: EdgeStorage):
        self.backend_url = backend_url
        self.device_api_key = device_api_key
        self.storage = storage
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    def send_telegram_alert(self, payload: dict, image_path: str):
        """Optional fallback push notification directly to the user's phone via Telegram Bot API."""
        if not self.telegram_bot_token or not self.telegram_chat_id or not os.path.exists(image_path):
            return
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendPhoto"
            caption = f"Smart Door ({payload.get('personLabel', 'unknown')}): {payload.get('caption', '')}"
            with open(image_path, "rb") as photo:
                requests.post(url, data={"chat_id": self.telegram_chat_id, "caption": caption}, files={"photo": photo}, timeout=6.0)
        except Exception as e:
            logger.warning(f"Telegram alert failed: {e}")

    def upload_event(self, event_id: str, payload: dict, image_path: str) -> bool:
        self.send_telegram_alert(payload, image_path)
        headers = {
            "X-Device-Api-Key": self.device_api_key
        }

        if not os.path.exists(image_path):
            logger.error(f"Snapshot image not found at {image_path}")
            return False

        try:
            with open(image_path, "rb") as img_file:
                files = {
                    "image": (os.path.basename(image_path), img_file, "image/jpeg"),
                    "data": (None, json.dumps(payload), "application/json")
                }
                response = requests.post(
                    self.backend_url,
                    headers=headers,
                    files=files,
                    timeout=5.0
                )
                if response.status_code in [200, 201]:
                    logger.info(f"Event {event_id} successfully uploaded to backend ({response.status_code}).")
                    self.storage.mark_event_sent(event_id)
                    return True
                else:
                    logger.warning(f"Backend responded with status {response.status_code}: {response.text}")
                    self.storage.increment_retry(event_id)
                    return False
        except requests.RequestException as e:
            logger.warning(f"Network error uploading event {event_id}: {e}. Retained in outbox.")
            self.storage.increment_retry(event_id)
            return False

    def drain_outbox(self):
        """Attempts to resend any queued events from offline periods."""
        pending = self.storage.get_pending_events(limit=10)
        for item in pending:
            logger.info(f"Retrying pending event {item['event_id']} (attempt #{item['retry_count'] + 1})")
            success = self.upload_event(item["event_id"], item["payload"], item["image_path"])
            if not success:
                break # Stop draining if network is still down
