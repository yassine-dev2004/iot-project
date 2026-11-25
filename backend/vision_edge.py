"""
Pipeline Vision IA MediaPipe Hand-Tracking 21 Landmarks pour KiddySentinel.
Traite le flux vidéo (webcam ou simulation), extrait les repères 3D normalisés,
reconnaît les micro-gestes (Pointage, Paume, Pouce haut/bas, Call me, Poing, Pincement)
et transmet en temps réel via WebSocket au serveur FastAPI (<20 ms).
"""

import cv2
import mediapipe as mp
import time
import json
import asyncio
import websockets
import threading
from backend.gesture_classifier import GestureClassifier

BACKEND_WS_URL = "ws://localhost:8000/ws/client"

class VisionPipeline:
    def __init__(self, camera_id=0):
        self.camera_id = camera_id
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.6
        )
        self.mp_draw = mp.solutions.drawing_utils
        self.last_gesture = None
        self.last_send_time = 0
        self.debounce_sec = 1.2 # Anti-rebond gestuel pédiatrique
        self.ws_loop = None
        self.ws_client = None

    def start_camera(self):
        cap = cv2.VideoCapture(self.camera_id)
        if not cap.isOpened():
            print(f"[ERREUR] Impossible d'ouvrir la caméra {self.camera_id}.")
            return

        print(">>> Caméra démarrée. Détection IA MediaPipe active.")
        print("Touches: 'q' pour quitter, 'c' pour simuler un clap, 's' pour soif, 'p' pour parents.")

        asyncio_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        asyncio_thread.start()

        fps_time = time.time()
        fps = 30.0

        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                print("Flux vidéo indisponible.")
                break

            # Miroir horizontal pour effet miroir naturel
            frame = cv2.flip(frame, 1)
            h, w, c = frame.shape
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands.process(rgb_frame)

            detected_gesture = None
            confidence = 0.0
            details = {}

            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    self.mp_draw.draw_landmarks(
                        frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS
                    )
                    detected_gesture, confidence, details = GestureClassifier.classify(hand_landmarks.landmark)

                    # Affichage visuel sur la vidéo
                    if detected_gesture and detected_gesture != "UNKNOWN":
                        cv2.putText(
                            frame, f"GESTE: {detected_gesture} ({confidence*100:.0f}%)",
                            (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2
                        )
                        # Envoyer si le délai d'anti-rebond est respecté
                        curr_time = time.time()
                        if (curr_time - self.last_send_time > self.debounce_sec) or (detected_gesture != self.last_gesture):
                            self.last_send_time = curr_time
                            self.last_gesture = detected_gesture
                            self._schedule_send_gesture(detected_gesture, confidence, details)
            else:
                # Aucune main détectée
                cv2.putText(
                    frame, "En attente de la main de l'enfant...",
                    (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2
                )

            # Calcul FPS
            curr_fps_time = time.time()
            fps = 1.0 / (curr_fps_time - fps_time + 1e-6)
            fps_time = curr_fps_time
            cv2.putText(frame, f"FPS: {fps:.1f}", (w - 120, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            cv2.imshow("KiddySentinel - Vision Edge MediaPipe 3D (2 IRM)", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('c'):
                self._schedule_send_clap()
            elif key == ord('s'):
                self._schedule_send_gesture("POINTING", 1.0, {})
            elif key == ord('p'):
                self._schedule_send_gesture("CALL_ME", 1.0, {})

        cap.release()
        cv2.destroyAllWindows()

    def _run_async_loop(self):
        self.ws_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.ws_loop)
        self.ws_loop.run_until_complete(self._maintain_ws())

    async def _maintain_ws(self):
        while True:
            try:
                async with websockets.connect(BACKEND_WS_URL) as ws:
                    self.ws_client = ws
                    print(">>> Pipeline Vision connecté au WebSocket FastAPI !")
                    while True:
                        msg = await ws.recv()
                        # Traiter les retours du serveur si besoin
            except Exception:
                self.ws_client = None
                await asyncio.sleep(2)

    def _schedule_send_gesture(self, gesture, confidence, details):
        if self.ws_client and self.ws_loop:
            payload = {
                "type": "GESTURE_DETECTED",
                "gesture": gesture,
                "confidence": confidence,
                "servo_angle": details.get("servo_angle", None)
            }
            asyncio.run_coroutine_threadsafe(
                self.ws_client.send(json.dumps(payload)),
                self.ws_loop
            )

    def _schedule_send_clap(self):
        if self.ws_client and self.ws_loop:
            payload = {
                "type": "ACOUSTIC_CLAP",
                "gesture": "CLAP",
                "confidence": 1.0
            }
            asyncio.run_coroutine_threadsafe(
                self.ws_client.send(json.dumps(payload)),
                self.ws_loop
            )

if __name__ == "__main__":
    pipeline = VisionPipeline()
    pipeline.start_camera()
