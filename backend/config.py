# Configuration centrale KiddySentinel 2 IRM
HOST = "0.0.0.0"
PORT = 8000

# WebSocket Endpoints
WS_AI_CLIENT = "/ws/client"
WS_ESP32 = "/ws/esp32"
WS_DASHBOARD = "/ws/dashboard"

# Matrice des Besoins (CAA / Makaton / PECS)
GESTURES_CONFIG = {
    "POINTING": {
        "label": "Index Pointé",
        "action": "EAU_SOIF",
        "speech": "J'ai soif, je veux de l'eau s'il vous plaît !",
        "oled": "BESOIN : EAU/SOIF",
        "servo": 90,
        "led": "GREEN",
        "relay": None,
        "buzzer": False,
        "description": "Incline la paille ergonomique vers l'enfant"
    },
    "OPEN_PALM": {
        "label": "Paume Ouverte",
        "action": "JOIE_JEU",
        "speech": "Bonjour ! Je vais bien. Je veux jouer !",
        "oled": "HUMEUR : JOIE/JEU",
        "servo": None,
        "led": "RAINBOW",
        "relay": 1,
        "buzzer": False,
        "description": "Arc-en-ciel lumineux stimulant + Veilleuse ON"
    },
    "THUMBS_UP": {
        "label": "Pouce Levé",
        "action": "REPONSE_OUI",
        "speech": "Oui, d'accord ! Merci !",
        "oled": "REPONSE : OUI",
        "servo": None,
        "led": "MELODY_FLASH",
        "relay": 1,
        "buzzer": "SOFT_BEEP",
        "description": "Validation douce + Enclenche la musique apaisante"
    },
    "THUMBS_DOWN": {
        "label": "Pouce Baissé",
        "action": "REPONSE_NON",
        "speech": "Non, je ne veux pas, je n'aime pas.",
        "oled": "REPONSE : NON",
        "servo": None,
        "led": "SOFT_RED",
        "relay": 0,
        "buzzer": False,
        "description": "Confirmation sans punition + Coupure musique"
    },
    "CALL_ME": {
        "label": "Signe Call Me",
        "action": "APPEL_PARENT",
        "speech": "Maman, Papa, venez m'aider s'il vous plaît !",
        "oled": "URGENCE : PARENT",
        "servo": None,
        "led": "ALERT_BLINK",
        "relay": None,
        "buzzer": "CARILLON",
        "description": "Carillon doux d'appel parent"
    },
    "FIST": {
        "label": "Poing Fermé",
        "action": "DANGER_SOS",
        "speech": "Arrêtez ! J'ai mal, au secours !",
        "oled": "DANGER : DOULEUR",
        "servo": 0,
        "led": "FLASH_RED",
        "relay": 0,
        "buzzer": "SOS_ALARM",
        "description": "Arrêt d'urgence, alerte soignant et coupure matérielle"
    },
    "CLAP": {
        "label": "Clap Sonore",
        "action": "TOGGLE_LIGHT",
        "speech": "Allume ou éteins la lumière !",
        "oled": "SON : CLAP DETECTE",
        "servo": None,
        "led": "TOGGLE",
        "relay": "TOGGLE",
        "buzzer": False,
        "description": "Commutation va-et-vient veilleuse"
    },
    "PINCH": {
        "label": "Pincement",
        "action": "VOLUME_ADJUST",
        "speech": "Un tout petit peu...",
        "oled": "VOLUME ASSERVI",
        "servo": "PROGRESSIVE",
        "led": "FADE",
        "relay": None,
        "buzzer": False,
        "description": "Réglage progressif du volume / servomoteur"
    },
    "FAIL_SAFE": {
        "label": "Homme-Mort Pédiatrique",
        "action": "ABSENCE_OR_FALL",
        "speech": "Alerte de sécurité : absence détectée ou risque de chute.",
        "oled": "SECURITE : VEILLE",
        "servo": 0,
        "led": "AMBER_PULSE",
        "relay": 0,
        "buzzer": "WARNING_BEEP",
        "description": "Mode veille sécurisé après absence prolongée (> 8s)"
    }
}
