import json
import logging
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

class EdgeMQTTClient:
    """
    Subscribes to IoT node door events (PIR motion, Doorbell, Contact switch).
    Publishes actuation commands back to ESP32:
    - door/cmd/lock (unlock 10 s)
    - door/cmd/led (status colors, alarm)
    - door/display (shows Gemini caption on SSD1306 OLED)
    """
    def __init__(self,
                 broker_host: str = "localhost",
                 broker_port: int = 1883,
                 topic_prefix: str = "door",
                 on_motion_callback: Optional[Callable] = None,
                 on_bell_callback: Optional[Callable] = None):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.prefix = topic_prefix.rstrip("/")
        self.on_motion = on_motion_callback
        self.on_bell = on_bell_callback
        self.client = None

        self._init_client()

    def _init_client(self):
        try:
            import paho.mqtt.client as mqtt
            self.client = mqtt.Client(client_id="smart-door-pi-edge")
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.connect_async(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
            logger.info(f"MQTT client connecting to {self.broker_host}:{self.broker_port}...")
        except Exception as e:
            logger.warning(f"Could not initialize MQTT client: {e}. Edge running in standalone camera mode.")

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT Broker!")
            client.subscribe(f"{self.prefix}/motion")
            client.subscribe(f"{self.prefix}/bell")
            client.subscribe(f"{self.prefix}/contact")
            client.subscribe(f"{self.prefix}/status")
        else:
            logger.warning(f"MQTT connection failed with code {rc}")

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        payload_str = msg.payload.decode("utf-8", errors="ignore")
        logger.info(f"MQTT message received on {topic}: {payload_str}")

        try:
            data = json.loads(payload_str)
        except Exception:
            data = {"raw": payload_str}

        if topic == f"{self.prefix}/motion" and self.on_motion:
            self.on_motion(data)
        elif topic == f"{self.prefix}/bell" and self.on_bell:
            self.on_bell(data)

    def publish_unlock(self, duration_sec: int = 10):
        if self.client:
            self.client.publish(f"{self.prefix}/cmd/lock", json.dumps({"action": "unlock", "duration": duration_sec}))

    def publish_alert(self, pattern: str = "red_alarm"):
        if self.client:
            self.client.publish(f"{self.prefix}/cmd/led", json.dumps({"pattern": pattern}))

    def publish_display(self, text: str):
        if self.client:
            self.client.publish(f"{self.prefix}/display", json.dumps({"text": text[:64]}))

    def stop(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
