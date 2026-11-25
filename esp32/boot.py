import network
import time
import uasyncio as asyncio
try:
    import ujson as json
except ImportError:
    import json

# Configuration Wi-Fi & Serveur
WIFI_SSID = "Mon_Reseau_WiFi"
WIFI_PASS = "MotDePasse"
SERVER_WS_URL = "ws://192.168.1.50:8000/ws/esp32"

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connexion au Wi-Fi...")
        wlan.connect(WIFI_SSID, WIFI_PASS)
        while not wlan.isconnected():
            time.sleep(0.5)
            print(".", end="")
    print("\nWi-Fi Connecté! IP:", wlan.ifconfig()[0])
