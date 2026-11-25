import os
from dotenv import load_dotenv

load_dotenv()

DEVICE_ID = os.getenv("DEVICE_ID", "pi-front-door-01")
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "sk_device_secret_door_key_12345")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080/api/events")

FACE_DET_SCORE_THRESH = float(os.getenv("FACE_DET_SCORE_THRESH", "0.85"))
FACE_NMS_THRESH = float(os.getenv("FACE_NMS_THRESH", "0.3"))
FACE_RECOG_COSINE_THRESH = float(os.getenv("FACE_RECOG_COSINE_THRESH", "0.363"))
FACE_RECOG_L2_THRESH = float(os.getenv("FACE_RECOG_L2_THRESH", "1.128"))
LIVENESS_CONSECUTIVE_FRAMES = int(os.getenv("LIVENESS_CONSECUTIVE_FRAMES", "3"))
LIVENESS_MOTION_THRESH = float(os.getenv("LIVENESS_MOTION_THRESH", "0.015"))

EVENT_COOLDOWN_SECONDS = float(os.getenv("EVENT_COOLDOWN_SECONDS", "30.0"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

ENABLE_GPIO = os.getenv("ENABLE_GPIO", "false").lower() == "true"
DOORBELL_GPIO_PIN = int(os.getenv("DOORBELL_GPIO_PIN", "17"))

DATABASE_PATH = os.getenv("DATABASE_PATH", "edge_data.db")
MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
