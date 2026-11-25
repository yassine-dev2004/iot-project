import math

class GestureClassifier:
    """
    Classificateur géométrique invariant pour KiddySentinel.
    Analyse les 21 landmarks 3D d'une main fournis par Google MediaPipe Hands.
    Gère les micro-pointages indépendamment de l'angle ou de la taille de la main de l'enfant.
    """

    # Indices des landmarks MediaPipe Hands:
    # WRIST = 0
    # THUMB: CMC=1, MCP=2, IP=3, TIP=4
    # INDEX: MCP=5, PIP=6, DIP=7, TIP=8
    # MIDDLE: MCP=9, PIP=10, DIP=11, TIP=12
    # RING: MCP=13, PIP=14, DIP=15, TIP=16
    # PINKY: MCP=17, PIP=18, DIP=19, TIP=20

    @staticmethod
    def _dist(p1, p2):
        return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (p1.z - p2.z)**2)

    @classmethod
    def classify(cls, landmarks):
        if not landmarks or len(landmarks) < 21:
            return None, 0.0, {}

        # 1. Échelle normalisée basée sur la paume (Poignet à Base Majeur)
        wrist = landmarks[0]
        middle_mcp = landmarks[9]
        palm_size = cls._dist(wrist, middle_mcp)
        if palm_size < 1e-5:
            palm_size = 1.0

        # Vérifier l'état de chaque doigt (ouvert/fermé/étendu)
        # Un doigt est étendu si la distance bout-doigt au poignet est nettement supérieure à l'articulation MCP au poignet
        index_open = cls._dist(landmarks[8], wrist) > cls._dist(landmarks[6], wrist) * 1.15
        middle_open = cls._dist(landmarks[12], wrist) > cls._dist(landmarks[10], wrist) * 1.15
        ring_open = cls._dist(landmarks[16], wrist) > cls._dist(landmarks[14], wrist) * 1.15
        pinky_open = cls._dist(landmarks[20], wrist) > cls._dist(landmarks[18], wrist) * 1.15

        # Pouce étendu par rapport au MCP
        thumb_open = cls._dist(landmarks[4], wrist) > cls._dist(landmarks[2], wrist) * 1.15

        # Distance pouce-index normalisée pour le pincement (Pinch Grip)
        pinch_dist = cls._dist(landmarks[4], landmarks[8]) / palm_size

        # Orientation verticale du pouce
        thumb_dy = landmarks[4].y - landmarks[2].y  # en coordonnées écran: y augmente vers le bas
        thumb_up = thumb_open and (thumb_dy < -0.05 * palm_size) and not (middle_open or ring_open or pinky_open)
        thumb_down = thumb_open and (thumb_dy > 0.05 * palm_size) and not (middle_open or ring_open or pinky_open)

        # Signe Call Me (Pouce + Auriculaire ouverts, Index + Majeur + Annulaire fermés)
        call_me = thumb_open and pinky_open and (not index_open) and (not middle_open) and (not ring_open)

        # Pincement (Pinch Grip) : Pouce et Index très proches l'un de l'autre
        if pinch_dist < 0.22 and not (middle_open and ring_open and pinky_open):
            # Servomoteur asservi à l'ouverture du pincement (0 à 180°)
            servo_val = int(min(max((pinch_dist / 0.25) * 180, 0), 180))
            return "PINCH", 0.92, {"pinch_ratio": round(pinch_dist, 3), "servo_angle": servo_val}

        # Index Pointé (Pointing) : Index ouvert, autres doigts fermés
        if index_open and not middle_open and not ring_open and not pinky_open:
            return "POINTING", 0.95, {}

        # Signe Call Me
        if call_me:
            return "CALL_ME", 0.96, {}

        # Pouce levé
        if thumb_up:
            return "THUMBS_UP", 0.94, {}

        # Pouce baissé
        if thumb_down:
            return "THUMBS_DOWN", 0.94, {}

        # Poing fermé (Fist / SOS) : Tous les doigts repliés
        if not index_open and not middle_open and not ring_open and not pinky_open and not thumb_open:
            return "FIST", 0.97, {}

        # Paume ouverte (5 doigts ouverts)
        if index_open and middle_open and ring_open and pinky_open and thumb_open:
            return "OPEN_PALM", 0.98, {}

        return "UNKNOWN", 0.5, {
            "fingers": [thumb_open, index_open, middle_open, ring_open, pinky_open]
        }
