#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ESP32Servo.h>

// Wi-Fi Config (Default Wokwi-GUEST for simulation)
const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASS = "";

// MQTT Broker (Public test broker or local Mosquitto)
const char* MQTT_BROKER = "test.mosquitto.org";
const int MQTT_PORT = 1883;
const char* TOPIC_PREFIX = "door";

// Pin Definitions
#define PIN_PIR        15
#define PIN_DOORBELL   4
#define PIN_CONTACT    5
#define PIN_SERVO      13
#define PIN_LED_GREEN  18
#define PIN_LED_RED    19
#define PIN_BUZZER     23
#define OLED_SDA       21
#define OLED_SCL       22

Adafruit_SSD1306 display(128, 64, &Wire, -1);
Servo lockServo;
WiFiClient espClient;
PubSubClient client(espClient);

unsigned long lastHeartbeat = 0;
unsigned long unlockEndTime = 0;
bool isUnlocked = false;

// Debounce trackers
int lastPirState = LOW;
int lastBellState = HIGH;
int lastContactState = HIGH;

void connectWiFi() {
  Serial.print("Connecting to Wi-Fi");
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected! IP: " + WiFi.localIP().toString());
}

void showOled(const char* line1, const char* line2) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.println("Smart Door IoT Node");
  display.drawLine(0, 10, 128, 10, SSD1306_WHITE);
  display.setCursor(0, 20);
  display.println(line1);
  display.setCursor(0, 36);
  display.println(line2);
  display.display();
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String message = "";
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.printf("MQTT In [%s]: %s\n", topic, message.c_str());

  StaticJsonDocument<256> doc;
  deserializeJson(doc, message);

  String sTopic = String(topic);
  if (sTopic.endsWith("/cmd/lock")) {
    int duration = doc["duration"] | 10;
    lockServo.write(90); // Unlocked position
    digitalWrite(PIN_LED_GREEN, HIGH);
    isUnlocked = true;
    unlockEndTime = millis() + (duration * 1000);
    showOled("DOOR UNLOCKED", "Welcome!");
  } else if (sTopic.endsWith("/cmd/led")) {
    String pattern = doc["pattern"] | "none";
    if (pattern == "red_alarm") {
      digitalWrite(PIN_LED_RED, HIGH);
      tone(PIN_BUZZER, 1000, 500);
      delay(600);
      digitalWrite(PIN_LED_RED, LOW);
    }
  } else if (sTopic.endsWith("/display")) {
    const char* text = doc["text"] | "Activity";
    showOled("EVENT CAPTION:", text);
  }
}

void reconnectMQTT() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    String clientId = "ESP32Door-" + String(random(0xffff), HEX);
    String lwtTopic = String(TOPIC_PREFIX) + "/status";

    if (client.connect(clientId.c_str(), lwtTopic.c_str(), 1, true, "{\"status\":\"offline\"}")) {
      Serial.println("connected!");
      client.publish(lwtTopic.c_str(), "{\"status\":\"online\"}", true);

      client.subscribe((String(TOPIC_PREFIX) + "/cmd/lock").c_str());
      client.subscribe((String(TOPIC_PREFIX) + "/cmd/led").c_str());
      client.subscribe((String(TOPIC_PREFIX) + "/display").c_str());
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" retrying in 5 seconds");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);

  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_DOORBELL, INPUT_PULLUP);
  pinMode(PIN_CONTACT, INPUT_PULLUP);
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);

  Wire.begin(OLED_SDA, OLED_SCL);
  if (display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    showOled("SYSTEM READY", "Standing by...");
  }

  lockServo.attach(PIN_SERVO);
  lockServo.write(0); // Locked position

  connectWiFi();
  client.setServer(MQTT_BROKER, MQTT_PORT);
  client.setCallback(mqttCallback);
}

void loop() {
  if (!client.connected()) {
    reconnectMQTT();
  }
  client.loop();

  // Handle auto-lock timer
  if (isUnlocked && millis() > unlockEndTime) {
    lockServo.write(0); // Relock
    digitalWrite(PIN_LED_GREEN, LOW);
    isUnlocked = false;
    showOled("DOOR LOCKED", "Standing by...");
  }

  // 1. PIR Motion Sensor
  int pirVal = digitalRead(PIN_PIR);
  if (pirVal != lastPirState) {
    lastPirState = pirVal;
    if (pirVal == HIGH) {
      client.publish((String(TOPIC_PREFIX) + "/motion").c_str(), "{\"motion\":true}");
    }
  }

  // 2. Doorbell Pushbutton
  int bellVal = digitalRead(PIN_DOORBELL);
  if (bellVal == LOW && lastBellState == HIGH) {
    tone(PIN_BUZZER, 2000, 200);
    client.publish((String(TOPIC_PREFIX) + "/bell").c_str(), "{\"pressed\":true}");
    delay(50); // Debounce
  }
  lastBellState = bellVal;

  // 3. Door-Contact Reed Switch (debounced)
  int contactVal = digitalRead(PIN_CONTACT);
  if (contactVal != lastContactState) {
    delay(40); // Debounce
    contactVal = digitalRead(PIN_CONTACT);
    if (contactVal != lastContactState) {
      lastContactState = contactVal;
      const char* doorState = (contactVal == LOW) ? "{\"open\":false}" : "{\"open\":true}";
      client.publish((String(TOPIC_PREFIX) + "/contact").c_str(), doorState);
    }
  }

  // 4. Heartbeat every 30 seconds
  if (millis() - lastHeartbeat > 30000) {
    lastHeartbeat = millis();
    String hb = "{\"status\":\"online\",\"uptime_s\":" + String(millis() / 1000) + "}";
    client.publish((String(TOPIC_PREFIX) + "/status").c_str(), hb.c_str());
  }

  delay(20);
}
