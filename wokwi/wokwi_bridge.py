"""
Jumeau Numérique Wokwi en Temps Réel (Digital Twin Bridge).
Connecte un ESP32 simulé ou un banc virtuel au backend FastAPI via WebSocket.
Permet d'exécuter, observer et valider toute la chaîne cyber-physique
sans nécessiter le matériel lourd en continu.
"""

import asyncio
import json
import websockets
import sys

BACKEND_WS = "ws://localhost:8000/ws/esp32"

class WokwiDigitalTwin:
    def __init__(self, uri=BACKEND_WS):
        self.uri = uri
        self.running = True
        self.servo_angle = 0
        self.relay_state = 0
        self.leds = [0, 0, 0, 0, 0]
        self.oled_text = "PRET"

    async def run(self):
        print("="*65)
        print("  KIDDYSENTINEL - JUMEAU NUMÉRIQUE ESP32 (WOKWI BRIDGE)")
        print("  Architecture Cyber-Physique 2 IRM - Session 2026")
        print("="*65)
        print(f"Connexion au serveur central FastAPI sur {self.uri} ...")

        while self.running:
            try:
                async with websockets.connect(self.uri) as ws:
                    print(">>> [JUMEAU NUMERIQUE] ESP32 Connecté au bus WebSocket avec succès !")
                    print("Prêt à recevoir les ordres d'actionnement...")

                    while self.running:
                        message = await ws.recv()
                        data = json.loads(message)
                        self.process_command(data)

            except (websockets.exceptions.ConnectionClosedError, ConnectionRefusedError):
                print("En attente de connexion avec le serveur FastAPI (reconnexion dans 2s)...")
                await asyncio.sleep(2)
            except Exception as e:
                print(f"Erreur pont virtuel: {e}")
                await asyncio.sleep(2)

    def process_command(self, cmd):
        msg_type = cmd.get("type")
        if msg_type in ["COMMAND", "INITIAL_STATE"]:
            c = cmd.get("state", cmd)
            action = c.get("action", "INITIAL")
            self.oled_text = c.get("oled", self.oled_text)
            
            if "servo" in c and c["servo"] is not None:
                self.servo_angle = c["servo"]
            if "relay" in c and c["relay"] is not None:
                self.relay_state = c["relay"]
            
            led_info = c.get("led", "OFF")
            buzzer_info = c.get("buzzer", "OFF")

            print("\n" + "-"*55)
            print(f" [COMMANDE MATERIELLE RECUE] Action: {action}")
            print(f" -> ECRAN OLED (I2C)     : [{self.oled_text}]")
            print(f" -> SERVOMOTEUR (GPIO 13): {self.servo_angle}° (Inclinaison paille)")
            print(f" -> RELAIS 220V (GPIO 25): {'ALLUME (1)' if self.relay_state else 'ETEINT (0)'}")
            print(f" -> 5 LEDS BIONIQUES     : {led_info}")
            print(f" -> BUZZER PIEZO         : {buzzer_info}")
            print("-"*55)

if __name__ == "__main__":
    twin = WokwiDigitalTwin()
    try:
        asyncio.run(twin.run())
    except KeyboardInterrupt:
        print("\nArrêt du Jumeau Numérique.")
