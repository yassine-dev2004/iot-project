# IoT Door Node — ESP32 + MQTT + Wokwi (`/iot`)

Firmware C++ (Arduino / PlatformIO) et schéma électronique **Wokwi** pour le nœud matériel déporté sur la porte d'entrée, connecté en temps réel au Raspberry Pi Edge (`/edge`) via **MQTT**.

---

## 1. Câblage Matériel (ESP32 DevKit V4)

| Composant | Rôle | Broche ESP32 | Mode / Protocole |
|---|---|---|---|
| **Capteur PIR (HC-SR501)** | Détecte une présence devant la porte et réveille la caméra Pi | `GPIO 15` | Entrée numérique (`INPUT`) |
| **Bouton Sonnette** | Déclenche un carillon + capture photo immédiate | `GPIO 4` | Entrée `INPUT_PULLUP` (actif bas) |
| **Contact Magnétique Porte** | Détecte l'ouverture / fermeture physique du battant | `GPIO 5` | Entrée `INPUT_PULLUP` avec anti-rebond |
| **Servomoteur Serrure** | Déverrouille à `90°` pendant `10 s` puis reverrouille à `0°` | `GPIO 13` | Sortie PWM `50 Hz` (`ESP32Servo`) |
| **LED Verte** | Indique l'accès autorisé / serrure déverrouillée | `GPIO 18` | Sortie numérique (`OUTPUT`) |
| **LED Rouge** | Alerte intrusion / visiteur inconnu rôdant | `GPIO 19` | Sortie numérique (`OUTPUT`) |
| **Buzzer Piézo** | Carillon de sonnette (`2 kHz`) & alarme sécurité (`1 kHz`) | `GPIO 23` | Sortie fréquentielle (`tone`) |
| **Écran OLED SSD1306** | Affiche l'état du verrou et la légende Gemini en direct | `GPIO 21` (SDA), `GPIO 22` (SCL) | Bus I2C (`0x3C`, `128×64`) |

---

## 2. Topics MQTT Bidirectionnels

### Capteurs : ESP32 $\rightarrow$ Raspberry Pi Edge
| Topic | Exemple de Payload JSON | Action déclenchée côté Pi (`/edge`) |
|---|---|---|
| `door/motion` | `{"motion": true}` | Réveille le pipeline caméra YuNet/SFace |
| `door/bell` | `{"pressed": true}` | Force un événement `doorbell_press` + snapshot + légende Gemini |
| `door/contact` | `{"open": true}` / `{"open": false}` | Journalise l'ouverture/fermeture mécanique de la porte |
| `door/status` | `{"status": "online", "uptime_s": 60}` | Heartbeat toutes les `30 s` + *Last Will* `{"status": "offline"}` |

### Actionneurs : Raspberry Pi Edge $\rightarrow$ ESP32
| Topic | Exemple de Payload JSON | Action matérielle sur l'ESP32 |
|---|---|---|
| `door/cmd/lock` | `{"action": "unlock", "duration": 10}` | Servo à `90°` + LED Verte ON pendant `10 s`, puis retour auto à `0°` |
| `door/cmd/led` | `{"pattern": "red_alarm"}` | Clignotement LED Rouge + sirène Buzzer |
| `door/display` | `{"text": "Package delivered at 14:20"}` | Affiche la légende Gemini sur l'écran OLED SSD1306 |

---

## 3. Comment Tester sur Wokwi (2 Méthodes)

### Méthode A — Sur Wokwi.com (Sans rien installer)
1. Rendez-vous sur https://wokwi.com/projects/new/esp32
2. Dans l'onglet **`sketch.ino`**, collez le contenu de `iot/src/main.cpp`.
3. Dans l'onglet **`diagram.json`**, collez le contenu de `iot/wokwi/diagram.json`.
4. Dans l'onglet **Library Manager (`+`)**, ajoutez : `PubSubClient`, `ArduinoJson`, `Adafruit SSD1306`, `Adafruit GFX Library`, `ESP32Servo`.
5. Cliquez sur **Play (▶)** :
   - L'ESP32 se connecte automatiquement au Wi-Fi virtuel `Wokwi-GUEST` puis au broker MQTT (`test.mosquitto.org`).
   - Cliquez sur le **capteur PIR** ou le **bouton bleu Doorbell** dans Wokwi pour envoyer de vrais messages MQTT !
   - Lancez en parallèle sur votre PC :
     ```bash
     python -m edge.main run --source video.mp4 --mqtt --mqtt-host test.mosquitto.org
     ```
     Votre PC recevra en direct les clics depuis Wokwi et renverra l'ordre d'ouverture du servomoteur et la légende Gemini sur l'écran OLED de Wokwi !

### Méthode B — Sans Wokwi (Simulateur Python Local)
Si vous voulez tester en local hors-ligne avec Mosquitto (`docker compose up -d mosquitto`) :
```bash
# Terminal 1 : Simule l'ESP32 (PIR + Sonnette + Réception Servo/OLED)
python iot/esp32_simulator.py

# Terminal 2 : Pipeline Edge connecté en MQTT
python -m edge.main run --source video.mp4 --mqtt --mqtt-host localhost
```
