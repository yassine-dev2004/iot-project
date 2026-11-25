"""
KiddySentinel - Firmware MicroPython v1.22 pour ESP32 DevKit V4
Brochage conforme au cahier des charges 2 IRM :
- Servomoteur SG90 (Paille ergonomique) : GPIO 13 (PWM 50 Hz)
- Écran OLED SSD1306 (128x64)          : I2C SDA=GPIO 21, SCL=GPIO 22
- 5 LEDs Doigts Bioniques              : GPIOs 14, 12, 33, 32, 4
- Capteur Sonore KY-038                : GPIO 34 (Entrée Numérique / Interruption)
- Relais de Puissance                  : GPIO 25 (Sortie TOR Veilleuse/Musique)
- Buzzer Piézoélectrique               : GPIO 19 (PWM Fréquentiel)
"""

import time
import json

try:
    from machine import Pin, PWM, I2C
    MICROPYTHON_HW = True
except ImportError:
    # Mode émulation / test si exécuté sur Python hôte standard
    MICROPYTHON_HW = False
    print("[MOCK] Environnement d'émulation matérielle sans machine.")

# ----------------- Configuration Matérielle -----------------
PIN_SERVO = 13
PIN_I2C_SDA = 21
PIN_I2C_SCL = 22
PIN_LEDS = [14, 12, 33, 32, 4]
PIN_CLAP = 34
PIN_RELAY = 25
PIN_BUZZER = 19

class KiddySentinelESP32:
    def __init__(self):
        self.relay_state = 0
        self.servo_angle = 0
        self.init_hardware()

    def init_hardware(self):
        if MICROPYTHON_HW:
            # Relais
            self.relay = Pin(PIN_RELAY, Pin.OUT)
            self.relay.value(0)

            # LEDs Bioniques
            self.leds = [Pin(p, Pin.OUT) for p in PIN_LEDS]
            self.all_leds(0)

            # Servomoteur PWM 50Hz (période 20ms)
            self.servo_pwm = PWM(Pin(PIN_SERVO), freq=50)
            self.set_servo_angle(0)

            # Buzzer PWM
            self.buzzer_pwm = PWM(Pin(PIN_BUZZER), freq=1000, duty=0)

            # Écran OLED SSD1306 (I2C)
            try:
                import ssd1306
                self.i2c = I2C(0, scl=Pin(PIN_I2C_SCL), sda=Pin(PIN_I2C_SDA))
                self.oled = ssd1306.SSD1306_I2C(128, 64, self.i2c)
                self.display_oled("KiddySentinel", "2 IRM SYSTEM", "PRET !")
            except Exception as e:
                print(f"[OLED] Non détecté ou ssd1306 manquant: {e}")
                self.oled = None

            # Capteur Clap KY-038 (interruption)
            try:
                self.clap_pin = Pin(PIN_CLAP, Pin.IN)
                self.clap_pin.irq(trigger=Pin.IRQ_RISING, handler=self._on_clap_detected)
            except Exception as e:
                print(f"[KY-038] Init erreur: {e}")
        else:
            print("[ESP32] Matériel initialisé (Mode Simulation Logicielle)")

    def _on_clap_detected(self, pin):
        # Anti-rebond simple
        print(">>> CLAP PHYSIQUE DETECTE SUR GPIO 34 !")
        self.toggle_relay()

    def set_servo_angle(self, angle):
        self.servo_angle = max(0, min(180, angle))
        if MICROPYTHON_HW:
            # 0° -> ~0.5ms (duty ~25), 180° -> ~2.5ms (duty ~125) sur échelle 1024
            duty = int(25 + (self.servo_angle / 180.0) * 100)
            self.servo_pwm.duty(duty)
        print(f"[ACTIONNEUR] Servomoteur positionné à {self.servo_angle}°")

    def set_relay(self, state):
        self.relay_state = 1 if state else 0
        if MICROPYTHON_HW:
            self.relay.value(self.relay_state)
        print(f"[ACTIONNEUR] Relais de Puissance : {'ACTIF (ON)' if self.relay_state else 'INACTIF (OFF)'}")

    def toggle_relay(self):
        self.set_relay(not self.relay_state)

    def all_leds(self, state):
        if MICROPYTHON_HW:
            for led in self.leds:
                led.value(1 if state else 0)
        print(f"[LEDS] Toutes LEDs = {state}")

    def play_led_pattern(self, pattern):
        if not MICROPYTHON_HW:
            print(f"[LEDS] Motif lumineux : {pattern}")
            return
        if pattern == "RAINBOW":
            for _ in range(3):
                for led in self.leds:
                    led.value(1)
                    time.sleep_ms(60)
                    led.value(0)
            self.all_leds(1)
        elif pattern == "GREEN":
            self.all_leds(0)
            self.leds[2].value(1) # LED centrale verte
        elif pattern == "FLASH_RED":
            for _ in range(5):
                self.all_leds(1)
                time.sleep_ms(100)
                self.all_leds(0)
                time.sleep_ms(100)
        elif pattern == "SOFT_RED":
            self.all_leds(0)
            self.leds[0].value(1)
        elif pattern == "ALERT_BLINK":
            for _ in range(4):
                self.all_leds(1)
                time.sleep_ms(150)
                self.all_leds(0)
                time.sleep_ms(150)

    def play_sound(self, sound_type):
        if not MICROPYTHON_HW:
            print(f"[BUZZER] Son joué : {sound_type}")
            return
        if sound_type == "SOFT_BEEP":
            self.buzzer_pwm.freq(1046) # Do6
            self.buzzer_pwm.duty(512)
            time.sleep_ms(150)
            self.buzzer_pwm.duty(0)
        elif sound_type == "CARILLON":
            notes = [523, 659, 784, 1046] # Do, Mi, Sol, Do
            for n in notes:
                self.buzzer_pwm.freq(n)
                self.buzzer_pwm.duty(400)
                time.sleep_ms(120)
            self.buzzer_pwm.duty(0)
        elif sound_type == "SOS_ALARM":
            for _ in range(3):
                self.buzzer_pwm.freq(2000)
                self.buzzer_pwm.duty(600)
                time.sleep_ms(200)
                self.buzzer_pwm.duty(0)
                time.sleep_ms(100)
        elif sound_type == "WARNING_BEEP":
            self.buzzer_pwm.freq(440)
            self.buzzer_pwm.duty(400)
            time.sleep_ms(300)
            self.buzzer_pwm.duty(0)

    def display_oled(self, line1="", line2="", line3=""):
        print(f"[OLED DISPLAY] L1: '{line1}' | L2: '{line2}' | L3: '{line3}'")
        if MICROPYTHON_HW and self.oled:
            self.oled.fill(0)
            self.oled.text("KiddySentinel", 10, 0)
            self.oled.hline(0, 12, 128, 1)
            self.oled.text(line1[:16], 0, 20)
            self.oled.text(line2[:16], 0, 36)
            self.oled.text(line3[:16], 0, 52)
            self.oled.show()

    def handle_command(self, cmd):
        """Reçoit une commande JSON envoyée depuis le serveur central FastAPI"""
        print(f"\n[COMMANDE RECUE] -> {cmd}")
        action = cmd.get("action")
        oled_txt = cmd.get("oled", "")
        servo = cmd.get("servo")
        relay = cmd.get("relay")
        led = cmd.get("led")
        buzzer = cmd.get("buzzer")

        # Mise à jour OLED
        self.display_oled(oled_txt, f"ACT: {action}", "STATUS: OK")

        # Mise à jour Servomoteur
        if servo is not None:
            self.set_servo_angle(servo)

        # Mise à jour Relais
        if relay == "TOGGLE":
            self.toggle_relay()
        elif relay is not None:
            self.set_relay(relay)

        # Motifs LED
        if led:
            self.play_led_pattern(led)

        # Buzzer Piézo
        if buzzer and buzzer != "OFF":
            self.play_sound(buzzer)


# Pour exécution autonome ou démarrage sur ESP32
esp_node = KiddySentinelESP32()

if __name__ == "__main__":
    print("Test local du driver ESP32...")
    esp_node.handle_command({
        "action": "EAU_SOIF",
        "oled": "BESOIN : EAU/SOIF",
        "servo": 90,
        "led": "GREEN",
        "buzzer": "SOFT_BEEP"
    })
