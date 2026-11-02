/*
 * AutoGuard DMS — ESP32-S3 Companion Peripheral Controller Firmware
 * 
 * Subsystem: ESP32-S3 Actuator Controller & Hardware Safety Watchdog
 * Architecture: Powered by cl0ud (https://github.com/Ojas-sta/cl0ud-brand-engineering)
 * Co-Engineered by: Ojas Singh <ojasctc@gmail.com>
 * 
 * Hardware:
 *   - ESP32-S3 DevKit / NodeMCU
 *   - RGB LED / WS2812B NeoPixel on GPIO 48 (or discrete LEDs on GPIO 4, 5, 6, 7)
 *   - Piezo Buzzer on GPIO 8 (PWM channel 0)
 *   - Emergency Push Button on GPIO 0 (BOOT button) or GPIO 9 (Active LOW, internal pull-up)
 *   - UART0 / USB-Serial connected to Raspberry Pi 4B (115200 baud)
 */

#include <Arduino.h>

#define FIRMWARE_VERSION "1.0.0-PROD"
#define PROTOCOL_VERSION 1

// Pin Definitions
#define PIN_BUZZER        8
#define PIN_BUTTON        0      // BOOT button on most ESP32-S3 boards
#define PIN_LED_GREEN     4
#define PIN_LED_YELLOW    5
#define PIN_LED_ORANGE    6
#define PIN_LED_RED       7

#define PWM_BUZZER_CHANNEL 0
#define PWM_RESOLUTION     8

// Watchdog communication timeout (3 seconds)
#define WATCHDOG_TIMEOUT_MS 3000

unsigned long lastRxTime = 0;
unsigned long lastTxTime = 0;
bool buttonState = false;
bool lastButtonState = false;

// Alert state variables
String currentLedColor = "GREEN";
bool currentBuzzerActive = false;
String currentBuzzerPattern = "OFF";

// Simple JSON parser helpers
String extractJsonValue(const String& json, const String& key) {
  int keyIndex = json.indexOf("\"" + key + "\"");
  if (keyIndex == -1) return "";
  int colonIndex = json.indexOf(":", keyIndex);
  if (colonIndex == -1) return "";
  
  int startVal = colonIndex + 1;
  while (startVal < json.length() && (json[startVal] == ' ' || json[startVal] == '\"')) {
    startVal++;
  }
  
  int endVal = startVal;
  while (endVal < json.length() && json[endVal] != ',' && json[endVal] != '}' && json[endVal] != '\"' && json[endVal] != '\r' && json[endVal] != '\n') {
    endVal++;
  }
  return json.substring(startVal, endVal);
}

void setLeds(String color) {
  digitalWrite(PIN_LED_GREEN,  (color == "GREEN")  ? HIGH : LOW);
  digitalWrite(PIN_LED_YELLOW, (color == "YELLOW") ? HIGH : LOW);
  digitalWrite(PIN_LED_ORANGE, (color == "ORANGE") ? HIGH : LOW);
  digitalWrite(PIN_LED_RED,    (color == "RED")    ? HIGH : LOW);
}

void updateBuzzer(bool active, String pattern) {
  if (!active || pattern == "OFF") {
    ledcWriteTone(PWM_BUZZER_CHANNEL, 0);
    return;
  }
  
  unsigned long now = millis();
  if (pattern == "CHIME") {
    ledcWriteTone(PWM_BUZZER_CHANNEL, 880);
  } else if (pattern == "DOUBLE_PULSE") {
    // Pulse on/off based on timer
    int cycle = (now % 1000);
    if (cycle < 150 || (cycle > 250 && cycle < 400)) {
      ledcWriteTone(PWM_BUZZER_CHANNEL, 1046);
    } else {
      ledcWriteTone(PWM_BUZZER_CHANNEL, 0);
    }
  } else if (pattern == "RAPID_SIREN" || pattern == "EMERGENCY") {
    int cycle = (now % 400);
    if (cycle < 200) {
      ledcWriteTone(PWM_BUZZER_CHANNEL, 1318);
    } else {
      ledcWriteTone(PWM_BUZZER_CHANNEL, 1760);
    }
  }
}

void sendHeartbeat() {
  buttonState = (digitalRead(PIN_BUTTON) == LOW); // Active LOW
  
  Serial.print("{\"version\":");
  Serial.print(PROTOCOL_VERSION);
  Serial.print(",\"device\":\"ESP32S3\",\"status\":\"OK\",\"firmware\":\"");
  Serial.print(FIRMWARE_VERSION);
  Serial.print("\",\"button_pressed\":");
  Serial.print(buttonState ? "true" : "false");
  Serial.print(",\"sensor_status\":\"OK\"}\n");
}

void handleCommand(const String& line) {
  lastRxTime = millis();
  
  String cmd = extractJsonValue(line, "command");
  if (cmd == "ALERT_UPDATE") {
    currentLedColor = extractJsonValue(line, "led_state");
    String buzzerVal = extractJsonValue(line, "buzzer");
    currentBuzzerActive = (buzzerVal == "true");
    currentBuzzerPattern = extractJsonValue(line, "buzzer_pattern");
    
    setLeds(currentLedColor);
  }
}

void setup() {
  Serial.begin(115200);
  delay(100);

  pinMode(PIN_BUTTON, INPUT_PULLUP);
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_YELLOW, OUTPUT);
  pinMode(PIN_LED_ORANGE, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);

  // Setup Buzzer PWM
  ledcSetup(PWM_BUZZER_CHANNEL, 1000, PWM_RESOLUTION);
  ledcAttachPin(PIN_BUZZER, PWM_BUZZER_CHANNEL);

  setLeds("GREEN");
  lastRxTime = millis();
}

void loop() {
  unsigned long now = millis();

  // Read incoming Serial lines from Raspberry Pi
  while (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() > 0 && line.startsWith("{") && line.endsWith("}")) {
      handleCommand(line);
    }
  }

  // Safety Watchdog: If no message from Raspberry Pi within 3 seconds, enter safe standby
  if (now - lastRxTime > WATCHDOG_TIMEOUT_MS) {
    ledcWriteTone(PWM_BUZZER_CHANNEL, 0); // Silence buzzer
    // Breathing yellow/green standby
    int pulse = (now % 1000);
    digitalWrite(PIN_LED_GREEN, (pulse < 500) ? HIGH : LOW);
    digitalWrite(PIN_LED_YELLOW, LOW);
    digitalWrite(PIN_LED_ORANGE, LOW);
    digitalWrite(PIN_LED_RED, LOW);
  } else {
    // Actuate buzzer pattern
    updateBuzzer(currentBuzzerActive, currentBuzzerPattern);
  }

  // Send periodic telemetry & heartbeat every 250ms
  if (now - lastTxTime >= 250) {
    sendHeartbeat();
    lastTxTime = now;
  }
}
