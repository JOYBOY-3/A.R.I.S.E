// A.R.I.S.E. Smart Scanner Firmware - Version 3.3 (Queue & Bulk Sync Improvements)
// ==================================================================================
// NEW FEATURES:
// - Duplicate queue entry prevention
// - Bulk sync protocol (send entire queue at once)
// - Enhanced OLED feedback messages
// - Sync progress indicator
// ==================================================================================

// --- LIBRARY INCLUDES ---
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Adafruit_Fingerprint.h>
#include "UniversalFingerprint.h"
#include <ArduinoJson.h>
#include <Preferences.h>
Preferences preferences;

// --- HARDWARE DEFINITIONS ---
HardwareSerial sensorSerial(2);
UniversalFingerprint finger(&sensorSerial);

// OLED Display
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// --- BATTERY MONITORING ---
#include "esp_adc_cal.h"
#include "driver/adc.h"

#define BATTERY_PIN 35
const float R1 = 9650.0;
const float R2 = 9650.0;
const float DIVIDER_RATIO = R2 / (R1 + R2);
const float VOLTAGE_CORRECTION_SLOPE = 1.0;
const float VOLTAGE_CORRECTION_OFFSET = 0.21;
const float LOW_BATTERY_VOLTAGE = 3.3;

esp_adc_cal_characteristics_t adc_chars;
bool adc_calibrated = false;

float batteryVoltage = 0.0;
int batteryPercentage = 0;
bool isBatteryCritical = false;

unsigned long lastBatteryCheck = 0;
const long BATTERY_CHECK_INTERVAL = 2000;

// --- NETWORK CONFIGURATION ---
char ssid[32] = "JOY_BOY 8384";
char password[32] = "833G47j,";
char server_ip[64] = "http://192.168.137.1:5000";

// --- STATE MANAGEMENT ---
bool isSessionActive = false;
String activeSessionName = "";
unsigned long lastStatusCheck = 0;
const long statusCheckInterval = 5000;
unsigned long lastHeartbeat = 0;
const long heartbeatInterval = 10000;

// --- OFFLINE QUEUE (ENHANCED) ---
#define MAX_QUEUE_SIZE 50
int offlineQueue[MAX_QUEUE_SIZE];
int queueCount = 0;
int syncCount = 0;

// --- ADMIN TASK MANAGEMENT ---
enum AdminTask { NONE,
                 ENROLL,
                 DELETE,
                 MATCH,
                 DELETE_ALL };
AdminTask currentAdminTask = NONE;
int adminTaskId = 0;

// =============================================
// BATTERY FUNCTIONS (Unchanged)
// =============================================

void setupADCCalibration() {
  adc1_config_width(ADC_WIDTH_BIT_12);
  adc1_config_channel_atten(ADC1_CHANNEL_7, ADC_ATTEN_DB_11);

  esp_adc_cal_value_t val_type = esp_adc_cal_characterize(
    ADC_UNIT_1, ADC_ATTEN_DB_11, ADC_WIDTH_BIT_12, 1100, &adc_chars);

  adc_calibrated = true;
  Serial.println("ADC calibration complete!");
}

float mapFloat(float x, float in_min, float in_max, float out_min, float out_max) {
  return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
}

float readBatteryVoltage() {
  if (!adc_calibrated) setupADCCalibration();

  uint32_t raw_sum = 0;
  const int samples = 128;

  for (int i = 0; i < samples; i++) {
    raw_sum += adc1_get_raw(ADC1_CHANNEL_7);
  }

  uint32_t raw_avg = raw_sum / samples;
  uint32_t voltage_at_pin_mv = esp_adc_cal_raw_to_voltage(raw_avg, &adc_chars);
  float voltage_at_pin = voltage_at_pin_mv / 1000.0;
  float calculated_battery_voltage = voltage_at_pin / DIVIDER_RATIO;

  static float voltage_readings[10] = { 0 };
  static int reading_index = 0;

  voltage_readings[reading_index] = calculated_battery_voltage;
  reading_index = (reading_index + 1) % 10;

  float temp[10];
  for (int i = 0; i < 10; i++) temp[i] = voltage_readings[i];

  for (int i = 0; i < 9; i++) {
    for (int j = i + 1; j < 10; j++) {
      if (temp[i] > temp[j]) {
        float swap = temp[i];
        temp[i] = temp[j];
        temp[j] = swap;
      }
    }
  }

  float filtered_voltage = 0;
  for (int i = 2; i < 8; i++) filtered_voltage += temp[i];
  filtered_voltage /= 6.0;

  float calibrated_voltage = (filtered_voltage * VOLTAGE_CORRECTION_SLOPE) + VOLTAGE_CORRECTION_OFFSET;
  return calibrated_voltage;
}

void updateBatteryPercentage() {
  batteryVoltage = readBatteryVoltage();

  static int last_stable_percentage = -1;
  static unsigned long last_percentage_change = 0;
  const unsigned long MIN_CHANGE_TIME = 30000;

  float raw_percentage = 0.0;

  if (batteryVoltage >= 4.18) raw_percentage = 100.0;
  else if (batteryVoltage >= 4.10) raw_percentage = mapFloat(batteryVoltage, 4.10, 4.18, 95.0, 100.0);
  else if (batteryVoltage >= 4.05) raw_percentage = mapFloat(batteryVoltage, 4.05, 4.10, 90.0, 95.0);
  else if (batteryVoltage >= 4.00) raw_percentage = mapFloat(batteryVoltage, 4.00, 4.05, 85.0, 90.0);
  else if (batteryVoltage >= 3.95) raw_percentage = mapFloat(batteryVoltage, 3.95, 4.00, 80.0, 85.0);
  else if (batteryVoltage >= 3.90) raw_percentage = mapFloat(batteryVoltage, 3.90, 3.95, 70.0, 80.0);
  else if (batteryVoltage >= 3.85) raw_percentage = mapFloat(batteryVoltage, 3.85, 3.90, 60.0, 70.0);
  else if (batteryVoltage >= 3.80) raw_percentage = mapFloat(batteryVoltage, 3.80, 3.85, 50.0, 60.0);
  else if (batteryVoltage >= 3.75) raw_percentage = mapFloat(batteryVoltage, 3.75, 3.80, 40.0, 50.0);
  else if (batteryVoltage >= 3.70) raw_percentage = mapFloat(batteryVoltage, 3.70, 3.75, 30.0, 40.0);
  else if (batteryVoltage >= 3.65) raw_percentage = mapFloat(batteryVoltage, 3.65, 3.70, 20.0, 30.0);
  else if (batteryVoltage >= 3.60) raw_percentage = mapFloat(batteryVoltage, 3.60, 3.65, 10.0, 20.0);
  else if (batteryVoltage >= 3.50) raw_percentage = mapFloat(batteryVoltage, 3.50, 3.60, 5.0, 10.0);
  else if (batteryVoltage >= 3.40) raw_percentage = mapFloat(batteryVoltage, 3.40, 3.50, 1.0, 5.0);
  else raw_percentage = 0.0;

  int new_percentage = (int)(raw_percentage + 0.5);
  new_percentage = constrain(new_percentage, 0, 100);

  unsigned long currentTime = millis();

  if (last_stable_percentage == -1) {
    batteryPercentage = new_percentage;
    last_stable_percentage = new_percentage;
  } else if (new_percentage == 0 || new_percentage == 100) {
    batteryPercentage = new_percentage;
    last_stable_percentage = new_percentage;
    last_percentage_change = currentTime;
  } else if (abs(new_percentage - last_stable_percentage) >= 2) {
    batteryPercentage = new_percentage;
    last_stable_percentage = new_percentage;
    last_percentage_change = currentTime;
  } else if ((currentTime - last_percentage_change) > MIN_CHANGE_TIME) {
    batteryPercentage = new_percentage;
    last_stable_percentage = new_percentage;
    last_percentage_change = currentTime;
  }
}

bool isUSBPowered() {
  return (batteryVoltage > 4.5);
}

void checkBatterySafety() {
  if (isUSBPowered()) return;

  updateBatteryPercentage();

  if (batteryVoltage <= LOW_BATTERY_VOLTAGE) {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 20);
    display.println("BATTERY CRITICAL");
    display.setCursor(0, 35);
    display.println("SHUTTING DOWN...");
    display.setCursor(0, 50);
    display.print("Voltage: ");
    display.print(batteryVoltage, 2);
    display.println("V");
    display.display();

    delay(3000);
    esp_deep_sleep_start();
  }
}

void updateBatteryNonBlocking() {
  if (millis() - lastBatteryCheck > BATTERY_CHECK_INTERVAL) {
    updateBatteryPercentage();
    checkBatterySafety();
    lastBatteryCheck = millis();
  }
}

// =============================================
// DISPLAY FUNCTIONS
// =============================================

void drawWifiStrengthBar(int x, int y) {
  long rssi = WiFi.RSSI();
  int bars = 0;
  int wifiPercent = 0;

  if (WiFi.status() == WL_CONNECTED) {
    if (rssi > -55) bars = 4;
    else if (rssi > -65) bars = 3;
    else if (rssi > -75) bars = 2;
    else if (rssi > -85) bars = 1;
    else bars = 0;

    wifiPercent = map(constrain(rssi, -100, -30), -100, -30, 0, 100);
  }

  display.setCursor(x, y);

  int barWidth = 3;
  int barSpacing = 1;
  int barStartX = x;

  for (int i = 0; i < 4; i++) {
    int barHeight = (i + 1) * 2;
    int barX = barStartX + (i * (barWidth + barSpacing));
    int barY = y + 8 - barHeight;

    if (i < bars) {
      display.fillRect(barX, barY, barWidth, barHeight, SSD1306_WHITE);
    } else {
      display.drawRect(barX, barY, barWidth, barHeight, SSD1306_WHITE);
    }
  }

  display.setCursor(barStartX + 20, y);
  if (WiFi.status() == WL_CONNECTED) {
    if (wifiPercent < 10) display.print(" ");
    display.print(wifiPercent);
    display.print("% ");
  } else {
    display.print("OFF ");
  }
}

void drawBatteryInfo(int x, int y) {
  display.setCursor(x, y);
  display.print("  B:");

  if (batteryPercentage < 100) display.print(" ");
  if (batteryPercentage < 10) display.print(" ");

  display.print(batteryPercentage);
  display.print("% ");
  display.print(batteryVoltage, 1);
  display.print("v");
}

void drawQueueInfo(int x, int y) {
  display.setCursor(x, y);
  display.print("Queue: ");
  display.print(queueCount);
  display.print("   Sync: ");
  display.print(syncCount);
}

void drawStatusBar() {
  drawWifiStrengthBar(0, 0);
  drawBatteryInfo(45, 0);
  drawQueueInfo(0, 12);
  display.drawLine(0, 20, 127, 20, SSD1306_WHITE);
}

void updateDisplay(String mainMsg = "", String subMsg = "") {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);

  drawStatusBar();

  int contentStartY = 23;

  if (mainMsg != "") {
    if (mainMsg.length() <= 8) {
      display.setTextSize(2);
      display.setCursor(0, contentStartY);
      display.println(mainMsg);
      contentStartY += 20;
    } else {
      display.setTextSize(2);
      display.setCursor(0, contentStartY);

      String firstLine = mainMsg;
      String secondLine = "";

      if (mainMsg.length() > 16) {
        int splitPos = mainMsg.lastIndexOf(' ', 16);
        if (splitPos == -1) splitPos = 16;
        firstLine = mainMsg.substring(0, splitPos);
        secondLine = mainMsg.substring(splitPos + 1);
      }

      display.println(firstLine);
      contentStartY += 10;

      if (secondLine != "") {
        display.setCursor(0, contentStartY);
        display.println(secondLine);
        contentStartY += 10;
      }
    }
  }

  if (subMsg != "") {
    display.setTextSize(1);
    display.setCursor(0, (contentStartY + 22));
    display.println(subMsg);
  }

  display.display();
}

// =============================================
// CONFIGURATION MANAGEMENT
// =============================================

void loadAllConfig() {
  preferences.begin("device-config", true);

  if (preferences.getString("ssid", "").length() > 0) {
    String savedSSID = preferences.getString("ssid");
    String savedPass = preferences.getString("password");
    savedSSID.toCharArray(ssid, 32);
    savedPass.toCharArray(password, 32);
  }

  if (preferences.getString("server_ip", "").length() > 0) {
    String savedServerIP = preferences.getString("server_ip");
    savedServerIP.toCharArray(server_ip, 64);
    Serial.println("Loaded server: " + savedServerIP);
  }

  preferences.end();
}

void saveWiFiConfig(const char* newSSID, const char* newPassword) {
  preferences.begin("device-config", false);
  preferences.putString("ssid", newSSID);
  preferences.putString("password", newPassword);
  preferences.end();
  Serial.println("WiFi credentials saved.");
}

void saveServerConfig(const char* newServerIP) {
  preferences.begin("device-config", false);
  preferences.putString("server_ip", newServerIP);
  preferences.end();
  Serial.println("Server configuration saved: " + String(newServerIP));
}

void handleConfigCommand(String command) {
  command.trim();

  if (command.startsWith("wifi ")) {
    int firstSpace = command.indexOf(' ');
    int secondSpace = command.indexOf(' ', firstSpace + 1);

    if (firstSpace != -1 && secondSpace != -1) {
      String newSSID = command.substring(firstSpace + 1, secondSpace);
      String newPassword = command.substring(secondSpace + 1);

      if (newSSID.length() > 0 && newPassword.length() > 0) {
        saveWiFiConfig(newSSID.c_str(), newPassword.c_str());
        Serial.println("✅ WiFi settings saved!");
        Serial.println("📶 Restart device to connect to: " + newSSID);
      } else {
        Serial.println("❌ Please provide both WiFi name and password");
      }
    } else {
      Serial.println("❌ Usage: wifi NetworkName Password");
      Serial.println("   Example: wifi SchoolWiFi MyPassword123");
    }
  } else if (command.startsWith("server ")) {
    String newServerIP = command.substring(7);
    newServerIP.trim();

    if (newServerIP.length() > 0 && (newServerIP.startsWith("http://") || newServerIP.startsWith("https://"))) {
      saveServerConfig(newServerIP.c_str());
      Serial.println("✅ Server address saved!");
      Serial.println("🌐 New server: " + newServerIP);
    } else {
      Serial.println("❌ Server address must start with http:// or https://");
      Serial.println("   Example: server http://192.168.1.100:5000");
    }
  } else if (command == "config") {
    Serial.println("\n⚙️ CURRENT SETTINGS:");
    Serial.println("📶 WiFi: " + String(ssid));
    Serial.println("🌐 Server: " + String(server_ip));
    Serial.println("💡 Use 'wifi' or 'server' commands to change");
  } else if (command == "reset-config") {
    preferences.begin("device-config", false);
    preferences.clear();
    preferences.end();
    Serial.println("✅ Settings reset to factory defaults");
    Serial.println("🔄 Restart device to apply changes");
  } else {
    Serial.println("❌ Unknown command. Type anything to see available commands.");
  }
}

// =============================================
// ✅ NEW: ENHANCED QUEUE MANAGEMENT
// =============================================

/**
 * Check if a roll ID already exists in the queue
 * Prevents duplicate entries when same student scans multiple times
 */
bool isInQueue(int roll_id) {
  for (int i = 0; i < queueCount; i++) {
    if (offlineQueue[i] == roll_id) {
      return true;
    }
  }
  return false;
}

/**
 * Add roll ID to offline queue with duplicate prevention
 */
void addToQueue(int roll_id) {
  String subMsg = "Roll #" + String(roll_id);

  // ✅ NEW: Check for duplicates
  if (isInQueue(roll_id)) {
    updateDisplay("Already Queued!", subMsg);
    Serial.println("⚠️  Roll #" + String(roll_id) + " already in queue - skipping");
    delay(1500);
    return;
  }

  // Check if queue is full
  if (queueCount >= MAX_QUEUE_SIZE) {
    updateDisplay("Queue Full!", "Cannot save");
    Serial.println("❌ Queue full! Cannot add Roll #" + String(roll_id));
    delay(2000);
    return;
  }

  // Add to queue
  offlineQueue[queueCount] = roll_id;
  queueCount++;

  updateDisplay("Saved Offline", subMsg);
  Serial.println("💾 Roll #" + String(roll_id) + " added to queue (Total: " + String(queueCount) + ")");
  delay(1500);
}

// =============================================
// ✅ NEW: BULK SYNC PROTOCOL
// =============================================

/**
 * Sync entire offline queue to server in ONE request
 * Much faster than sequential sync
 */
void tryToSyncQueue() {
  if (WiFi.status() != WL_CONNECTED || queueCount == 0) {
    return;
  }

  Serial.println("\n=== BULK SYNC STARTED ===");
  Serial.println("Queue count: " + String(queueCount));

  updateDisplay("Syncing...", String(queueCount) + " records");
  delay(1000);

  HTTPClient http;
  http.setTimeout(15000);
  http.begin(String(server_ip) + "/api/bulk-mark-attendance");
  http.addHeader("Content-Type", "application/json");

  // ✅ Build JSON array of all queued roll IDs
  JsonDocument doc;
  // JsonArray rollIds = doc.createNestedArray("roll_ids");
  JsonArray rollIds = doc["roll_ids"].to<JsonArray>();

  for (int i = 0; i < queueCount; i++) {
    rollIds.add(offlineQueue[i]);
  }

  String jsonPayload;
  serializeJson(doc, jsonPayload);

  Serial.println("Payload: " + jsonPayload);

  // Show progress dots while waiting
  updateDisplay("Syncing", "Please wait...");

  int httpCode = http.POST(jsonPayload);

  if (httpCode == 200) {
    JsonDocument responseDoc;
    DeserializationError error = deserializeJson(responseDoc, http.getString());

    if (error) {
      Serial.println("❌ JSON parse error: " + String(error.c_str()));
      updateDisplay("Sync Error", "Invalid response");
      delay(2000);
      http.end();
      return;
    }

    int successCount = responseDoc["success_count"];
    JsonArray failed = responseDoc["failed"];

    Serial.println("Success: " + String(successCount) + "/" + String(queueCount));

    // Update sync counter
    syncCount += successCount;

    if (failed.size() == 0) {
      // ✅ All succeeded - clear entire queue
      queueCount = 0;
      updateDisplay("Sync Complete!", String(successCount) + " marked");
      Serial.println("✅ All records synced successfully!");
      delay(2000);
    } else {
      // ⚠️ Partial success - rebuild queue with only failed IDs
      Serial.println("⚠️  Partial sync: " + String(failed.size()) + " failed");

      int newQueueCount = 0;
      for (JsonVariant failedId : failed) {
        int failedRollId = failedId.as<int>();
        offlineQueue[newQueueCount++] = failedRollId;
        Serial.println("  Failed: Roll #" + String(failedRollId));
      }
      queueCount = newQueueCount;

      updateDisplay("Partial Sync", String(successCount) + " OK, " + String(failed.size()) + " fail");
      delay(2500);
    }

  } else {
    Serial.println("❌ Bulk sync failed: HTTP " + String(httpCode));
    updateDisplay("Sync Failed", "Retry later");
    delay(1500);
  }

  http.end();
  Serial.println("=== BULK SYNC ENDED ===\n");
}

// =============================================
// FINGERPRINT FUNCTIONS (Unchanged from original)
// =============================================

int getFingerprintID() {
  Serial.println("\n=== UNIVERSAL FINGERPRINT MATCHING ===");
  updateDisplay("Place Finger", activeSessionName);

  unsigned long startTime = millis();
  uint8_t p = FINGERPRINT_NOFINGER;

  while (true) {
    p = finger.getImage();

    if (p == FINGERPRINT_OK) {
      Serial.println("SUCCESS: Finger image captured");
      updateDisplay("Scanning", "Please wait...");
      break;
    } else if (p == FINGERPRINT_NOFINGER) {
      if (millis() - startTime > 10000) {
        Serial.println("INFO: Finger detection timeout (normal during session)");
        return -1;
      }
    } else {
      Serial.println("ERROR: Imaging error - code: " + String(p));
      updateDisplay("Scan Error", "Try again");
      delay(1000);
      return -2;
    }
    delay(100);
  }

  p = finger.image2Tz();
  if (p != FINGERPRINT_OK) {
    Serial.println("ERROR: Failed to convert image to template");
    updateDisplay("Processing", "Error - Retry");
    delay(1000);
    return -2;
  }

  p = finger.fingerFastSearch();

  switch (p) {
    case FINGERPRINT_OK:
      Serial.println("SUCCESS: Match found!");
      Serial.println("-> Finger ID: " + String(finger.getFingerID()));
      Serial.println("-> Confidence: " + String(finger.getConfidence()));
      updateDisplay("Verified", "Success!");
      delay(500);
      return finger.getFingerID();

    case FINGERPRINT_NOTFOUND:
      Serial.println("INFO: No match found in database");
      updateDisplay("Not Found", "In database");
      delay(1500);
      return -1;

    default:
      Serial.println("ERROR: Search failed: " + String(p));
      updateDisplay("Match Error", "Try again");
      delay(1000);
      return -2;
  }
}

bool isSlotOccupied(int id) {
  Serial.println("Checking slot " + String(id) + " for existing enrollment...");
  uint8_t result = finger.loadModel(id);

  if (result == FINGERPRINT_OK) {
    Serial.println("⚠️  Slot " + String(id) + " is already occupied!");
    return true;
  } else if (result == FINGERPRINT_PACKETRECIEVEERR) {
    Serial.println("✅ Slot " + String(id) + " appears to be empty");
    return false;
  } else {
    Serial.println("ℹ️  Slot " + String(id) + " check result: " + String(result) + " - treating as empty");
    return false;
  }
}

int8_t getFingerprintEnroll(int id) {
  Serial.println("\n=== ENHANCED ENROLLMENT WITH OVERWRITE PROTECTION ===");

  uint16_t maxCapacity = finger.getMaxCapacity();
  if (id > maxCapacity) {
    Serial.println("❌ ERROR: Slot " + String(id) + " exceeds sensor capacity (" + String(maxCapacity) + ")");
    updateDisplay("Invalid Slot", "Max: " + String(maxCapacity));
    delay(3000);
    return FINGERPRINT_BADLOCATION;
  }

  if (isSlotOccupied(id)) {
    Serial.println("❌ ENROLLMENT BLOCKED: Slot " + String(id) + " already has a fingerprint!");
    updateDisplay("Slot Occupied!", "ID: " + String(id));
    delay(2000);

    int existing_roll_id = floor((id - 1) / 2) + 1;
    updateDisplay("Maps to Roll", "#" + String(existing_roll_id));
    delay(2000);

    updateDisplay("Delete First", "Use: delete " + String(id));
    delay(2000);

    Serial.println("💡 This slot corresponds to Roll ID: " + String(existing_roll_id));
    Serial.println("💡 Use 'delete " + String(id) + "' to remove existing enrollment first");

    return FINGERPRINT_BADLOCATION;
  }

  Serial.println("✅ Slot " + String(id) + " is available for enrollment");
  updateDisplay("Slot Available", "ID: " + String(id));
  delay(1500);

  int roll_id = floor((id - 1) / 2) + 1;
  updateDisplay("Will map to", "Roll #" + String(roll_id));
  delay(1500);

  int p = -1;
  updateDisplay("Enrolling", "Place finger...");
  Serial.println("Waiting for valid finger to enroll in slot " + String(id));

  unsigned long startTime = millis();
  const unsigned long timeout = 30000;

  while (true) {
    p = finger.getImage();

    if (p == FINGERPRINT_OK) {
      updateDisplay("Enrolling", "Image taken...");
      delay(1500);
      break;
    } else if (p == FINGERPRINT_NOFINGER) {
      if (millis() - startTime > timeout) {
        updateDisplay("Enroll Timeout", "Please try again");
        Serial.println("Enrollment timeout - no finger detected");
        return FINGERPRINT_TIMEOUT;
      }
    } else {
      Serial.println("Imaging error: " + String(p));
    }
    delay(100);
  }

  p = finger.image2Tz(1);
  if (p != FINGERPRINT_OK) {
    updateDisplay("Enroll Error", "Convert 1 fail");
    delay(1500);
    Serial.println("Error converting first image");
    return p;
  }

  updateDisplay("Enrolling", "Remove finger");
  delay(1500);

  p = 0;
  while (p != FINGERPRINT_NOFINGER) {
    p = finger.getImage();
    delay(100);
  }

  updateDisplay("Enrolling", "Place same finger");
  p = -1;
  startTime = millis();

  while (true) {
    p = finger.getImage();

    if (p == FINGERPRINT_OK) {
      updateDisplay("Enrolling", "Image taken...");
      delay(1500);
      break;
    } else if (p == FINGERPRINT_NOFINGER) {
      if (millis() - startTime > timeout) {
        updateDisplay("Enroll Timeout", "Please try again");
        Serial.println("Second image timeout");
        return FINGERPRINT_TIMEOUT;
      }
    } else {
      Serial.println("Second image error: " + String(p));
    }
    delay(100);
  }

  p = finger.image2Tz(2);
  if (p != FINGERPRINT_OK) {
    updateDisplay("Enroll Error", "Convert 2 fail");
    delay(1500);
    Serial.println("Error converting second image");
    return p;
  }

  updateDisplay("Enrolling", "Processing...");
  delay(1500);
  p = finger.createModel();
  if (p != FINGERPRINT_OK) {
    updateDisplay("Enroll Error", "Prints mismatch");
    delay(1500);
    Serial.println("Fingerprints did not match");
    return p;
  }

  p = finger.storeModel(id);
  if (p != FINGERPRINT_OK) {
    updateDisplay("Enroll Error", "Store failed");
    delay(1500);
    Serial.println("Error storing model");
    return p;
  }

  int class_roll_id = floor((id - 1) / 2) + 1;
  updateDisplay("Enrolled!", "Roll #" + String(class_roll_id));
  delay(1500);
  updateDisplay("Success!", "Slot #" + String(id));
  delay(1500);

  Serial.println("✅ SUCCESS: Fingerprint enrolled in slot " + String(id));
  Serial.println("📋 Mapping: Slot " + String(id) + " → Roll ID " + String(class_roll_id));
  return FINGERPRINT_OK;
}

void checkFingerprintDatabase() {
  Serial.println("\n=== UNIVERSAL FINGERPRINT DATABASE ===");

  if (!finger.verifyPassword()) {
    Serial.println("ERROR: Fingerprint sensor not responding!");
    return;
  }

  Serial.println("SUCCESS: " + finger.getSensorName());
  Serial.println("-> Max Capacity: " + String(finger.getMaxCapacity()) + " templates");

  uint16_t templateCount = finger.getTemplateCount();
  if (templateCount > 0) {
    Serial.println("-> Templates stored: " + String(templateCount));
  }
}

void resetFingerprintSensor() {
  Serial.println("Performing sensor hardware reset...");

  sensorSerial.end();
  delay(1000);
  sensorSerial.begin(57600, SERIAL_8N1, 16, 17);
  delay(2000);

  while (sensorSerial.available()) {
    sensorSerial.read();
  }

  Serial.println("Re-initializing fingerprint sensor...");

  if (finger.begin()) {
    Serial.println("✅ Sensor reset successful!");
    Serial.println("Detected: " + finger.getSensorName());
    Serial.println("Forcing AS608 compatibility mode...");
  } else {
    Serial.println("❌ Sensor reset failed!");
  }
}

bool deleteAllFingerprints() {
  Serial.println("\n=== DELETING ALL FINGERPRINTS ===");
  updateDisplay("Deleting ALL", "Please wait...");

  uint8_t p = finger.emptyDatabase();

  if (p == FINGERPRINT_OK) {
    Serial.println("SUCCESS: All fingerprints deleted from sensor memory");
    updateDisplay("All Deleted!", "Memory cleared");
    delay(2000);
    return true;
  } else {
    Serial.println("ERROR: Failed to delete all fingerprints. Error code: " + String(p));
    updateDisplay("Delete Failed", "Error: " + String(p));
    delay(2000);
    return false;
  }
}

void testFingerprintSensor() {
  Serial.println("\n=== FINGERPRINT SENSOR DIAGNOSTICS ===");

  Serial.print("1. Sensor connection: ");
  if (finger.verifyPassword()) {
    Serial.println("✅ OK");
  } else {
    Serial.println("❌ FAILED");
    return;
  }

  Serial.println("2. Sensor Info: " + finger.getSensorName());
  Serial.println("   Capacity: " + String(finger.getMaxCapacity()) + " templates");

  Serial.print("3. Image capture test: ");
  updateDisplay("Testing", "Place finger...");

  uint8_t result = finger.getImage();
  if (result == FINGERPRINT_OK) {
    Serial.println("✅ SUCCESS - Finger detected");
  } else if (result == FINGERPRINT_NOFINGER) {
    Serial.println("⚠️  NO FINGER - This is normal if no finger placed");
  } else {
    Serial.println("❌ FAILED - Error: " + String(result));
  }

  delay(2000);

  Serial.print("4. Template count: ");
  uint16_t templateCount = finger.getTemplateCount();
  Serial.println(String(templateCount) + " templates");

  Serial.println("=== DIAGNOSTICS COMPLETE ===");
}

// =============================================
// NETWORK COMMUNICATION
// =============================================

void checkServerSessionStatus() {
  if (WiFi.status() != WL_CONNECTED) {
    isSessionActive = false;
    return;
  }

  HTTPClient http;
  http.setTimeout(10000);
  http.begin(String(server_ip) + "/api/session-status");

  int httpCode = http.GET();

  if (httpCode > 0) {
    if (httpCode == 200) {
      JsonDocument doc;
      DeserializationError error = deserializeJson(doc, http.getString());
      if (!error) {
        isSessionActive = doc["isSessionActive"];
        activeSessionName = doc["sessionName"].as<String>();
      } else {
        Serial.println("JSON parsing failed");
        isSessionActive = false;
      }
    }
  } else {
    isSessionActive = false;
    activeSessionName = "";
  }
  http.end();
}

void sendToServer(int roll_id) {
  if (WiFi.status() != WL_CONNECTED) {
    addToQueue(roll_id);
    return;
  }

  updateDisplay("Syncing...", "Roll #" + String(roll_id));
  delay(200);

  HTTPClient http;
  http.begin(String(server_ip) + "/api/mark-attendance-by-roll-id");
  http.addHeader("Content-Type", "application/json");

  JsonDocument doc;
  doc["class_roll_id"] = roll_id;
  String jsonPayload;
  serializeJson(doc, jsonPayload);

  int httpCode = http.POST(jsonPayload);

  if (httpCode > 0) {
    JsonDocument responseDoc;
    deserializeJson(responseDoc, http.getString());
    String serverMsg = responseDoc["message"].as<String>();
    serverMsg.replace("\n", " ");
    String subMsg = "Roll #" + String(roll_id);

    if (responseDoc["status"] == "success") {
      updateDisplay("Marked     ", subMsg);
      delay(1000);
    } else if (responseDoc["status"] == "duplicate") {
      updateDisplay("!Already Marked", subMsg);
      delay(1000);
    } else {
      updateDisplay(serverMsg, subMsg);
      delay(1000);
    }
  } else {
    addToQueue(roll_id);
  }
  http.end();
  delay(1000);
}

void sendHeartbeat() {
  if (WiFi.status() != WL_CONNECTED) { return; }

  HTTPClient http;
  http.begin(String(server_ip) + "/api/device/heartbeat");
  http.addHeader("Content-Type", "application/json");

  JsonDocument doc;
  doc["mac_address"] = WiFi.macAddress();
  doc["wifi_strength"] = WiFi.RSSI();
  doc["battery"] = batteryPercentage;
  doc["queue_count"] = queueCount;
  doc["sync_count"] = syncCount;

  String jsonPayload;
  serializeJson(doc, jsonPayload);
  http.POST(jsonPayload);
  http.end();
}

// =============================================
// SERIAL COMMAND HANDLER
// =============================================

void handleSerialCommands() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    Serial.println("");

    if (command.startsWith("wifi ") || command.startsWith("server ") || command == "config" || command == "reset-config") {
      handleConfigCommand(command);
    } else if (command == "test-sensor") {
      testFingerprintSensor();
    } else if (command.startsWith("enroll")) {
      adminTaskId = command.substring(7).toInt();
      uint16_t maxCapacity = finger.getMaxCapacity();

      if (adminTaskId > 0 && adminTaskId <= maxCapacity) {
        if (isSlotOccupied(adminTaskId)) {
          int existing_roll_id = floor((adminTaskId - 1) / 2) + 1;
          Serial.println("❌ SLOT OCCUPIED: Slot " + String(adminTaskId) + " already enrolled!");
          updateDisplay("Slot Occupied", "ID: " + String(adminTaskId));
          delay(1500);
          Serial.println("💡 This slot maps to Roll ID: " + String(existing_roll_id));
          Serial.println("💡 Use 'delete " + String(adminTaskId) + "' first, then enroll again");
        } else {
          currentAdminTask = ENROLL;
          Serial.println("✅ Slot " + String(adminTaskId) + " is available");
          updateDisplay("Starting", "Enrollment...");
          delay(1000);
          Serial.println("-> OK. Device is now waiting for a finger to enroll in slot " + String(adminTaskId));
          Serial.println("-> Sensor capacity: " + String(maxCapacity) + " templates");
          int roll_id = floor((adminTaskId - 1) / 2) + 1;
          Serial.println("📋 This slot will map to Roll ID: " + String(roll_id));
        }
      } else {
        Serial.println("❌ ERROR: Invalid ID. Must be 1-" + String(maxCapacity));
        updateDisplay("Invalid Slot", "Max: " + String(maxCapacity));
        delay(2000);
      }
    } else if (command.startsWith("delete-all")) {
      currentAdminTask = DELETE_ALL;
      Serial.println("-> OK. Deleting ALL fingerprints from sensor memory...");
    } else if (command.startsWith("delete")) {
      adminTaskId = command.substring(7).toInt();
      uint16_t maxCapacity = finger.getMaxCapacity();

      if (adminTaskId > 0 && adminTaskId <= maxCapacity) {
        currentAdminTask = DELETE;
        Serial.println("-> OK. Deleting template in slot " + String(adminTaskId));
      } else {
        Serial.println("--> ERROR: Invalid ID. Must be 1-" + String(maxCapacity));
      }
    } else if (command.startsWith("match")) {
      currentAdminTask = MATCH;
      Serial.println("-> OK. Device is now waiting for a finger to test matching.");
    } else if (command == "sensor-info") {
      Serial.println("\n=== SENSOR INFORMATION ===");
      Serial.println("Type: " + finger.getSensorName());
      Serial.println("Capacity: " + String(finger.getMaxCapacity()) + " templates");
      Serial.println("Status: " + String(finger.verifyPassword() ? "Connected" : "Disconnected"));
    } else if (command == "help" || command == "?") {
      showHelpMenu();
    } else if (command.length() > 0) {
      Serial.println("❌ Unknown command: '" + command + "'");
      Serial.println("💡 Type 'help' to see available commands");
    }
  }
}

void showHelpMenu() {
  uint16_t maxCapacity = finger.getMaxCapacity();

  Serial.println("\n📋 AVAILABLE COMMANDS:");
  Serial.println("\n--- WiFi & Server Setup ---");
  Serial.println("• wifi YourNetworkName YourPassword");
  Serial.println("• server http://your-server-ip:5000");
  Serial.println("• config                    (show current settings)");
  Serial.println("• reset-config              (reset to factory defaults)");

  Serial.println("\n--- Fingerprint Management ---");
  Serial.println("• enroll 5                  (save fingerprint in slot 5 of Roll #3)");
  Serial.println("• delete 5                  (remove fingerprint from slot 5 of Roll #3)");
  Serial.println("• delete-all                (delete ALL fingerprints)");
  Serial.println("• match                     (test fingerprint scanning)");
  Serial.println("• sensor-info               (show sensor details)");
  Serial.println("• help                      (show this help menu)");

  Serial.println("\n--- Examples ---");
  Serial.println("wifi SchoolWiFi MyPassword123");
  Serial.println("server http://192.168.1.100:5000");
  Serial.println("enroll 10");
  Serial.println("delete-all");
  Serial.println("sensor-info");
}

void executeAdminTask() {
  uint16_t maxCapacity = finger.getMaxCapacity();

  switch (currentAdminTask) {
    case ENROLL:
      {
        if (adminTaskId > maxCapacity) {
          Serial.println("❌ ERROR: Slot " + String(adminTaskId) + " exceeds sensor capacity (" + String(maxCapacity) + ")");
          break;
        }

        int8_t enrollResult = getFingerprintEnroll(adminTaskId);
        if (enrollResult == FINGERPRINT_OK) {
          Serial.println("✅ ENROLLMENT SUCCESS: Slot " + String(adminTaskId));
        } else {
          Serial.println("❌ Enrollment failed with error: " + String(enrollResult));
        }
      }
      break;

    case DELETE:
      {
        if (adminTaskId > maxCapacity) {
          Serial.println("❌ ERROR: Slot " + String(adminTaskId) + " exceeds sensor capacity");
          break;
        }

        updateDisplay("Confirm Delete", "Slot: " + String(adminTaskId));
        delay(1000);

        int roll_id = floor((adminTaskId - 1) / 2) + 1;
        updateDisplay("Affects Roll", "#" + String(roll_id));
        delay(1000);

        updateDisplay("Deleting...", "Please wait");

        if (finger.deleteModel(adminTaskId) == FINGERPRINT_OK) {
          updateDisplay("Deleted!", "Slot: " + String(adminTaskId));
          delay(1000);
          updateDisplay("Roll #" + String(roll_id), "is now available");
          Serial.println("✅ SUCCESS: Template deleted from slot " + String(adminTaskId));
          Serial.println("📋 Roll ID " + String(roll_id) + " is now available for re-enrollment");
        } else {
          updateDisplay("Delete Failed", "Slot: " + String(adminTaskId));
          Serial.println("❌ ERROR: Could not delete template from slot " + String(adminTaskId));
        }
        delay(2000);
      }
      break;

    case DELETE_ALL:
      {
        if (finger.emptyDatabase() == FINGERPRINT_OK) {
          updateDisplay("All Deleted!", "Memory cleared");
          Serial.println("✅ SUCCESS: All fingerprints deleted!");
        } else {
          updateDisplay("Delete Failed", "Error occurred");
          Serial.println("❌ ERROR: Failed to delete all fingerprints");
        }
        delay(2000);
      }
      break;

    case MATCH:
      {
        Serial.println("=== FINGERPRINT MATCHING TEST ===");
        updateDisplay("Scan Test", "Place finger...");

        int found_id = getFingerprintID();
        if (found_id > 0) {
          updateDisplay("Match Found", "Slot #" + String(found_id));
          Serial.println("✅ SUCCESS: Match found for slot #" + String(found_id));

          int class_roll_id = floor((found_id - 1) / 2) + 1;
          Serial.println("--> Corresponding Roll ID: #" + String(class_roll_id));
        } else if (found_id == -1) {
          updateDisplay("No Match", "In database");
          Serial.println("ℹ️  No match found in database");
        } else {
          updateDisplay("Scan Error", "Try again");
          Serial.println("❌ ERROR: Scanning failed");
        }
        delay(3000);
      }
      break;
  }

  currentAdminTask = NONE;
  adminTaskId = 0;
  Serial.println("\n--- Admin Task Complete. Returning to normal operation. ---");
}

// =============================================
// SETUP
// =============================================

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n\n--- A.R.I.S.E. Firmware v3.3 (Queue & Bulk Sync) Booting ---");

  loadAllConfig();

  Serial.println("Loaded Configuration:");
  Serial.println(" WiFi: " + String(ssid));
  Serial.println(" Server: " + String(server_ip));

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("CRITICAL FAILURE: SSD1306 allocation failed.");
    for (;;)
      ;
  }

  updateDisplay("Calibrating", "ADC...");
  setupADCCalibration();
  updateBatteryPercentage();
  checkBatterySafety();

  updateDisplay("Booting...");
  Serial.println("[OK] OLED Display Initialized.");
  delay(1000);

  Serial.println("\n--- Initializing Universal Fingerprint Sensor ---");
  updateDisplay("Init Sensor...");
  sensorSerial.begin(57600, SERIAL_8N1, 16, 17);
  delay(2000);

  while (sensorSerial.available()) {
    sensorSerial.read();
  }

  bool sensorInitialized = false;
  for (int attempt = 0; attempt < 3; attempt++) {
    if (finger.begin()) {
      sensorInitialized = true;

      if (finger.getSensorName().indexOf("R307") != -1) {
        Serial.println("⚠️  Wrong detection! Forcing AS608 mode...");
      }

      break;
    }
    Serial.println("Retrying sensor initialization...");
    delay(1000);
  }

  if (sensorInitialized) {
    Serial.println("SUCCESS! " + finger.getSensorName() + " detected.");
    updateDisplay("Sensor OK!");
    checkFingerprintDatabase();
    delay(1500);
  } else {
    Serial.println("FAILURE! Did not find fingerprint sensor.");
    updateDisplay("Sensor Error!");
    Serial.println("Continuing in limited mode without fingerprint sensor.");
  }

  updateDisplay("Connecting...");
  Serial.println("\n--- Attempting to Connect to WiFi ---");
  WiFi.begin(ssid, password);

  int wifi_timeout_counter = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(". ");
    wifi_timeout_counter++;

    updateBatteryPercentage();
    checkBatterySafety();

    updateDisplay("Connecting...");
    if (wifi_timeout_counter >= 40) {
      Serial.println("\nFAILURE: WiFi Connection Timed Out!");
      break;
    }
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nSUCCESS! WiFi Connected.");
    updateDisplay("Connected!");
    delay(1500);
  } else {
    Serial.println("\nWARNING: Proceeding in offline mode.");
    updateDisplay("WiFi Error!");
    delay(2000);
  }

  Serial.println("\n--- Setup Complete. Awaiting Session. ---");
  Serial.println("--- A.R.I.S.E. Admin Interface ---");
  showHelpMenu();
}

// =============================================
// ✅ MAIN LOOP (UPDATED)
// =============================================

void loop() {
  unsigned long currentTime = millis();

  updateBatteryNonBlocking();
  handleSerialCommands();

  if (WiFi.status() == WL_CONNECTED) {
    if (currentTime - lastStatusCheck > statusCheckInterval) {
      checkServerSessionStatus();
      lastStatusCheck = currentTime;
    }

    if (currentTime - lastHeartbeat > heartbeatInterval) {
      sendHeartbeat();
      lastHeartbeat = currentTime;
    }

    // ✅ NEW: Bulk sync queue when items are pending
    if (queueCount > 0) {
      tryToSyncQueue();
    }
  }

  if (currentAdminTask != NONE) {
    executeAdminTask();
  } else if (isSessionActive) {
    int sensor_id = getFingerprintID();
    if (sensor_id > 0) {
      int class_roll_id = floor((sensor_id - 1) / 2) + 1;
      updateDisplay("Identified", "Roll #" + String(class_roll_id));
      delay(500);

      // ✅ ENHANCED: Check if already in queue before adding
      if (WiFi.status() != WL_CONNECTED) {
        // Offline mode
        if (isInQueue(class_roll_id)) {
          updateDisplay("Already Queued!", "Roll #" + String(class_roll_id));
          delay(1500);
        } else {
          addToQueue(class_roll_id);
        }
      } else {
        // Online mode
        sendToServer(class_roll_id);
      }
    }
  } else {
    updateDisplay("Ready For", "Session...");
    delay(200);
  }
}