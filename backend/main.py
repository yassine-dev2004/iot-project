import asyncio
import json
import time
from typing import Set, Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.config import GESTURES_CONFIG, HOST, PORT
from backend.audit_logger import AuditLogger

app = FastAPI(
    title="KiddySentinel - Backend Cyber-Physique 2 IRM",
    description="Orchestrateur WebSocket Full-Duplex pour CAA Multimodale et Jumeau Numérique IoT",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = AuditLogger(log_dir="logs")

# Gestionnaire de connexions WebSockets
class ConnectionManager:
    def __init__(self):
        # Clients Web (Interface Caméra / Voix / Claps)
        self.client_connections: Set[WebSocket] = set()
        # Matériel physique ESP32 ou Jumeau Numérique Wokwi
        self.esp32_connections: Set[WebSocket] = set()
        # Tableaux de bord soignants / superviseurs
        self.dashboard_connections: Set[WebSocket] = set()
        # État courant du système physique
        self.state = {
            "relay": 0,
            "servo_angle": 0,
            "leds": [0, 0, 0, 0, 0],
            "oled_text": "KiddySentinel PRET",
            "buzzer": "OFF",
            "last_gesture": "NONE",
            "last_seen_child": time.time(),
            "fail_safe_triggered": False
        }

    async def connect_client(self, websocket: WebSocket):
        await websocket.accept()
        self.client_connections.add(websocket)

    def disconnect_client(self, websocket: WebSocket):
        self.client_connections.discard(websocket)

    async def connect_esp32(self, websocket: WebSocket):
        await websocket.accept()
        self.esp32_connections.add(websocket)
        # Envoyer l'état initial complet
        await websocket.send_text(json.dumps({
            "type": "INITIAL_STATE",
            "state": self.state
        }))

    def disconnect_esp32(self, websocket: WebSocket):
        self.esp32_connections.discard(websocket)

    async def connect_dashboard(self, websocket: WebSocket):
        await websocket.accept()
        self.dashboard_connections.add(websocket)
        await websocket.send_text(json.dumps({
            "type": "STATE_UPDATE",
            "state": self.state,
            "stats": logger.get_summary_stats()
        }))

    def disconnect_dashboard(self, websocket: WebSocket):
        self.dashboard_connections.discard(websocket)

    async def broadcast_esp32(self, command: dict):
        dead = []
        msg = json.dumps(command)
        for ws in self.esp32_connections:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.esp32_connections.discard(ws)

    async def broadcast_dashboard(self, update: dict):
        dead = []
        msg = json.dumps(update)
        for ws in self.dashboard_connections:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.dashboard_connections.discard(ws)

    async def broadcast_speech(self, text: str, priority: str = "NORMAL"):
        dead = []
        msg = json.dumps({
            "type": "SPEAK",
            "text": text,
            "priority": priority
        })
        for ws in self.client_connections:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.client_connections.discard(ws)

manager = ConnectionManager()

# Tâche de fond Homme-Mort Pédiatrique (Fail-Safe)
async def pediatric_fail_safe_monitor():
    while True:
        await asyncio.sleep(2.0)
        # Si aucun geste ou visage/main détecté depuis > 10 secondes et qu'on n'a pas encore déclenché
        elapsed = time.time() - manager.state["last_seen_child"]
        if elapsed > 10.0 and not manager.state["fail_safe_triggered"] and len(manager.client_connections) > 0:
            manager.state["fail_safe_triggered"] = True
            config = GESTURES_CONFIG["FAIL_SAFE"]
            logger.log_event(
                indice_type="FAIL_SAFE",
                gesture_name="HOMME_MORT",
                action=config["action"],
                speech=config["speech"],
                confidence=1.0,
                details={"elapsed_seconds": round(elapsed, 1)}
            )
            
            # Action ESP32
            esp_cmd = {
                "type": "COMMAND",
                "action": "FAIL_SAFE",
                "oled": config["oled"],
                "led": config["led"],
                "servo": config["servo"],
                "relay": config["relay"],
                "buzzer": config["buzzer"]
            }
            await manager.broadcast_esp32(esp_cmd)
            
            # Annonce vocale de sécurité
            await manager.broadcast_speech(config["speech"], priority="HIGH")
            
            # Mise à jour dashboard
            await manager.broadcast_dashboard({
                "type": "ALERT_FAIL_SAFE",
                "message": f"Absence prolongée de l'enfant ({round(elapsed)}s) : Passage en veille sécurisée !",
                "stats": logger.get_summary_stats()
            })

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(pediatric_fail_safe_monitor())

# Route API pour statistiques
@app.get("/api/stats")
async def get_stats():
    return {
        "stats": logger.get_summary_stats(),
        "state": manager.state,
        "esp32_connected": len(manager.esp32_connections) > 0,
        "clients_connected": len(manager.client_connections)
    }

# Route API pour télécharger le journal CSV thérapeutique
@app.get("/api/export/csv")
async def export_csv():
    if os.path.exists(logger.csv_file):
        return FileResponse(logger.csv_file, media_type="text/csv", filename="kiddysentinel_audit.csv")
    return {"error": "Fichier non trouvé"}

# WebSocket pour l'interface client (IA Vision / Clap / Web Speech)
@app.websocket("/ws/client")
async def websocket_client_endpoint(websocket: WebSocket):
    await manager.connect_client(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            msg_type = payload.get("type")

            # Réception d'un geste ou d'un son
            if msg_type in ["GESTURE_DETECTED", "ACOUSTIC_CLAP"]:
                gesture_key = payload.get("gesture")
                custom_servo = payload.get("servo_angle", None)
                confidence = float(payload.get("confidence", 1.0))
                
                # Réinitialiser le timer d'absence
                manager.state["last_seen_child"] = time.time()
                manager.state["fail_safe_triggered"] = False

                if gesture_key in GESTURES_CONFIG:
                    conf = GESTURES_CONFIG[gesture_key]
                    
                    # Mise à jour de l'état
                    servo_target = custom_servo if custom_servo is not None else conf["servo"]
                    if conf["relay"] == "TOGGLE":
                        manager.state["relay"] = 1 if manager.state["relay"] == 0 else 0
                    elif conf["relay"] is not None:
                        manager.state["relay"] = conf["relay"]

                    if servo_target is not None and isinstance(servo_target, int):
                        manager.state["servo_angle"] = servo_target

                    manager.state["oled_text"] = conf["oled"]
                    manager.state["last_gesture"] = gesture_key
                    manager.state["buzzer"] = str(conf["buzzer"])

                    # Log audit
                    logger.log_event(
                        indice_type="ACOUSTIC_CLAP" if msg_type == "ACOUSTIC_CLAP" else "VISION",
                        gesture_name=conf["label"],
                        action=conf["action"],
                        speech=conf["speech"],
                        confidence=confidence,
                        details={
                            "servo": manager.state["servo_angle"],
                            "relay": manager.state["relay"],
                            "oled": manager.state["oled_text"]
                        }
                    )

                    # Commande vers ESP32 (Physique ou Jumeau Numérique Wokwi)
                    esp_cmd = {
                        "type": "COMMAND",
                        "action": conf["action"],
                        "gesture": gesture_key,
                        "oled": conf["oled"],
                        "servo": manager.state["servo_angle"],
                        "relay": manager.state["relay"],
                        "led": conf["led"],
                        "buzzer": conf["buzzer"]
                    }
                    await manager.broadcast_esp32(esp_cmd)

                    # Notification tableau de bord soignant
                    await manager.broadcast_dashboard({
                        "type": "STATE_UPDATE",
                        "event": {
                            "label": conf["label"],
                            "action": conf["action"],
                            "speech": conf["speech"],
                            "confidence": confidence
                        },
                        "state": manager.state,
                        "stats": logger.get_summary_stats()
                    })

                    # Acquittement / commande vocale vers le client Web
                    await websocket.send_text(json.dumps({
                        "type": "SPEAK",
                        "text": conf["speech"],
                        "action": conf["action"]
                    }))

            elif msg_type == "HEARTBEAT_CHILD_PRESENT":
                manager.state["last_seen_child"] = time.time()
                manager.state["fail_safe_triggered"] = False

    except WebSocketDisconnect:
        manager.disconnect_client(websocket)
    except Exception as e:
        print(f"Erreur Client WS: {e}")
        manager.disconnect_client(websocket)

# WebSocket pour l'ESP32 / Wokwi
@app.websocket("/ws/esp32")
async def websocket_esp32_endpoint(websocket: WebSocket):
    await manager.connect_esp32(websocket)
    print(">>> ESP32 / Jumeau Numérique connecté avec succès !")
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            
            # L'ESP32 peut lui-même remonter un événement matériel (ex: capteur clap KY-038 branché sur GPIO 34)
            if payload.get("type") == "HARDWARE_EVENT":
                hw_event = payload.get("event")
                if hw_event == "KY038_CLAP":
                    # Déclenchement Clap depuis le matériel physique
                    conf = GESTURES_CONFIG["CLAP"]
                    manager.state["relay"] = 1 if manager.state["relay"] == 0 else 0
                    manager.state["oled_text"] = conf["oled"]
                    
                    logger.log_event(
                        indice_type="ACOUSTIC_CLAP_HARDWARE",
                        gesture_name="Clap KY-038 Physique",
                        action="TOGGLE_LIGHT",
                        speech=conf["speech"],
                        confidence=1.0,
                        details={"relay": manager.state["relay"]}
                    )
                    
                    # Synthèse vocale & dashboard
                    await manager.broadcast_speech(conf["speech"])
                    await manager.broadcast_dashboard({
                        "type": "STATE_UPDATE",
                        "event": {"label": "Clap KY-038", "speech": conf["speech"]},
                        "state": manager.state,
                        "stats": logger.get_summary_stats()
                    })
                    
            elif payload.get("type") == "ESP32_TELEMETRY":
                # Télémétrie en temps réel de l'ESP32
                await manager.broadcast_dashboard({
                    "type": "ESP32_TELEMETRY",
                    "telemetry": payload.get("data")
                })
    except WebSocketDisconnect:
        print("<<< Déconnexion ESP32")
        manager.disconnect_esp32(websocket)
    except Exception as e:
        print(f"Erreur ESP32 WS: {e}")
        manager.disconnect_esp32(websocket)

# WebSocket pour le Tableau de Bord Parents / Thérapeutes
@app.websocket("/ws/dashboard")
async def websocket_dashboard_endpoint(websocket: WebSocket):
    await manager.connect_dashboard(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_dashboard(websocket)

# Montage des fichiers statiques du Frontend Web
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=True)
