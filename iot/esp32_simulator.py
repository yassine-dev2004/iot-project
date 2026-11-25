import time
import json
import logging
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] (ESP32-Sim) %(message)s")
logger = logging.getLogger("ESP32Simulator")

BROKER = "localhost"
PORT = 1883
TOPIC_PREFIX = "door"

def on_connect(client, userdata, flags, rc):
    logger.info("ESP32 Simulator connected to MQTT Broker!")
    client.subscribe(f"{TOPIC_PREFIX}/cmd/#")
    client.subscribe(f"{TOPIC_PREFIX}/display")

def on_message(client, userdata, msg):
    logger.info(f">> ACTUATOR EVENT received on [{msg.topic}]: {msg.payload.decode()}")

def run_simulator():
    client = mqtt.Client(client_id="esp32-door-simulator")
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(BROKER, PORT, 60)
    except Exception as e:
        logger.warning(f"Could not connect to {BROKER}:{PORT}: {e}")
        return

    client.loop_start()

    logger.info("Simulating IoT events (motion, doorbell)... Press Ctrl+C to stop.")
    try:
        while True:
            # Simulate motion sensor
            time.sleep(10)
            logger.info("Publishing simulated PIR motion...")
            client.publish(f"{TOPIC_PREFIX}/motion", json.dumps({"motion": True}))

            time.sleep(15)
            logger.info("Publishing simulated Doorbell press...")
            client.publish(f"{TOPIC_PREFIX}/bell", json.dumps({"pressed": True}))
    except KeyboardInterrupt:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    run_simulator()
