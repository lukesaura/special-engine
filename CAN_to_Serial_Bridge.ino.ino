// ECU_Smooth_NoHorn_withHeadlight.ino
#include <SPI.h>
#include <mcp_can.h>

const int CAN0_CS = 10;
MCP_CAN CAN0(CAN0_CS);

#define MCP_SPEED MCP_8MHZ  // or MCP_16MHZ if your modules are 16MHz
const long CAN_BAUD = CAN_500KBPS;

uint8_t throttle = 0;  // 0..255
bool brakeFlag = false;
bool leftInd = false;
bool rightInd = false;
bool headlight = false;

// Throttle dynamics
const float ACCEL_PER_SEC = 120.0;
const float COAST_DECEL_PER_SEC = 40.0;
unsigned long lastTx = 0;
unsigned long lastDyn = 0;
const unsigned long TX_INTERVAL_MS = 50;
const unsigned long DYN_STEP_MS = 20;

bool upHeld = false;
bool downHeld = false;

void setup() {
  Serial.begin(115200);
  while (!Serial) {}
  Serial.println(F("ECU with Headlight starting..."));
  if (CAN0.begin(MCP_ANY, CAN_BAUD, MCP_SPEED) == CAN_OK) {
    Serial.println(F("MCP2515 Initialized Successfully"));
  } else {
    Serial.println(F("MCP2515 init fail"));
    while (1) delay(1000);
  }
  CAN0.setMode(MCP_NORMAL);
  lastDyn = millis();
}

void handleSerialLine(String s) {
  s.trim();
  if (s.length() == 0) return;
  if (s.startsWith("UP:")) {
    int v = s.substring(3).toInt();
    upHeld = (v != 0);
  } else if (s.startsWith("DOWN:")) {
    int v = s.substring(5).toInt();
    downHeld = (v != 0);
    brakeFlag = downHeld;
  } else if (s == "LEFT_TOGGLE") {
    leftInd = !leftInd;
  } else if (s == "RIGHT_TOGGLE") {
    rightInd = !rightInd;
  } else if (s == "HEAD_TOGGLE") {
    headlight = !headlight;
  } else if (s == "RESET_IND") {
    leftInd = rightInd = false;
  }
}

void applyThrottleDynamics() {
  unsigned long now = millis();
  unsigned long dt_ms = now - lastDyn;
  if (dt_ms < DYN_STEP_MS) return;
  lastDyn = now;

  float dt = dt_ms / 1000.0f;
  float t = throttle;
  if (upHeld) t += ACCEL_PER_SEC * dt;
  else t -= COAST_DECEL_PER_SEC * dt;

  if (t < 0.0f) t = 0.0f;
  if (t > 255.0f) t = 255.0f;
  throttle = (uint8_t)(t + 0.5f);
}

void loop() {
  while (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    handleSerialLine(line);
  }

  applyThrottleDynamics();

  unsigned long now = millis();
  if (now - lastTx >= TX_INTERVAL_MS) {
    lastTx = now;
    uint8_t buf[8];
    buf[0] = throttle;
    buf[1] = brakeFlag ? 1 : 0;
    buf[2] = leftInd ? 1 : 0;
    buf[3] = rightInd ? 1 : 0;
    buf[4] = headlight ? 1 : 0;  // HEADLIGHT
    buf[5] = buf[6] = buf[7] = 0;
    CAN0.sendMsgBuf(0x300, 0, 8, buf);
  }
}
