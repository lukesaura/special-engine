#include <Arduino_BuiltIn.h>

// Actuator_FixedPrintf.ino
#include <SPI.h>
#include <mcp_can.h>

const int CAN0_CS = 10;
const int CAN0_INT = 2;
MCP_CAN CAN0(CAN0_CS);

#define MCP_SPEED MCP_8MHZ
const long CAN_BAUD = CAN_500KBPS;

uint8_t lastThrottle = 0;
bool lastBrake = false;
bool leftInd = false;
bool rightInd = false;
bool headlight = false;

float speedKmh = 0.0f;
const float MAX_SPEED = 80.0f;
const float MAX_ACCEL = 3.5f;
const float BRAKE_DECEL = 8.0f;
const float DRAG = 0.04f;
unsigned long lastSim = 0;
const unsigned long SIM_DT_MS = 50;

float odometer_km = 0.0f;
const float MILEAGE_KM_PER_L = 40.0f;
float tank_capacity_l = 4.0f;
float fuel_liters = tank_capacity_l;

const int IDLE_RPM = 800;
const int MAX_RPM = 8000;

unsigned long lastSerialOut = 0;
const unsigned long SERIAL_OUT_MS = 100;

void setup() {
  Serial.begin(115200);
  while (!Serial) {}
  Serial.println("Actuator (fixed float printing) starting...");

  if (CAN0.begin(MCP_ANY, CAN_BAUD, MCP_SPEED) == CAN_OK) {
    Serial.println("MCP2515 Initialized Successfully");
  } else {
    Serial.println("MCP2515 init fail");
    while (1) delay(1000);
  }
  CAN0.setMode(MCP_NORMAL);
  lastSim = millis();
}

// physics update: dt in seconds
void stepSimulation(float dt) {
  float throttleFrac = (float)lastThrottle / 255.0f;
  float accel_kmh_s = throttleFrac * MAX_ACCEL * 3.6f;
  float brake_kmh_s = lastBrake ? BRAKE_DECEL * 3.6f : 0.0f;
  float drag_kmh_s = DRAG * speedKmh;
  float net_change = accel_kmh_s - drag_kmh_s;
  if (lastBrake) net_change -= brake_kmh_s;
  speedKmh += net_change * dt;
  if (speedKmh < 0.0f) speedKmh = 0.0f;
  if (speedKmh > MAX_SPEED) speedKmh = MAX_SPEED;
  odometer_km += speedKmh * dt / 3600.0f;
  float dist_this_step = speedKmh * dt / 3600.0f;
  float fuel_used = (dist_this_step > 0.0f) ? dist_this_step / MILEAGE_KM_PER_L : 0.0f;
  fuel_liters -= fuel_used;
  if (fuel_liters < 0.0f) fuel_liters = 0.0f;
  if (fuel_liters <= 0.001f) {
    speedKmh -= 5.0f * dt;
    if (speedKmh < 0.0f) speedKmh = 0.0f;
  }
}

int computeRPM() {
  float throttleFrac = (float)lastThrottle / 255.0f;
  float rpm = IDLE_RPM + throttleFrac * (MAX_RPM - IDLE_RPM);
  rpm += speedKmh * 20.0f;
  if (rpm > MAX_RPM) rpm = MAX_RPM;
  return (int)rpm;
}

void loop() {
  // CAN input
  if (CAN0.checkReceive() == CAN_MSGAVAIL) {
    unsigned long rxId;
    uint8_t len;
    uint8_t buf[8];
    CAN0.readMsgBuf(&rxId, &len, buf);
    if (rxId == 0x300 && len >= 5) {
      lastThrottle = buf[0];
      lastBrake = (buf[1] != 0);
      leftInd = (buf[2] != 0);
      rightInd = (buf[3] != 0);
      headlight = (buf[4] != 0);
    }
  }

  unsigned long now = millis();
  if (now - lastSim >= SIM_DT_MS) {
    unsigned long steps = (now - lastSim) / SIM_DT_MS;
    for (unsigned long i = 0; i < steps; ++i) stepSimulation(SIM_DT_MS / 1000.0f);
    lastSim += steps * SIM_DT_MS;
  }

  if (now - lastSerialOut >= SERIAL_OUT_MS) {
    int rpm = computeRPM();
    int fuelBars = (int)floor((fuel_liters / tank_capacity_l) * 4.0f + 0.0001f);
    if (fuelBars < 0) fuelBars = 0;
    if (fuelBars > 4) fuelBars = 4;

    // Print each field with Serial.print — this avoids %f issues on AVR
    // Format: SPD:xx.xx;RPM:yyyy;THR:zz;BRK:0;L:0;R:0;ODO:xx.xxx;FUEL:x.xx;FB:n;HL:0
    Serial.print("SPD:"); Serial.print(speedKmh, 2); Serial.print(";");
    Serial.print("RPM:"); Serial.print(rpm); Serial.print(";");
    Serial.print("THR:"); Serial.print(lastThrottle); Serial.print(";");
    Serial.print("BRK:"); Serial.print(lastBrake ? 1 : 0); Serial.print(";");
    Serial.print("L:"); Serial.print(leftInd ? 1 : 0); Serial.print(";");
    Serial.print("R:"); Serial.print(rightInd ? 1 : 0); Serial.print(";");
    Serial.print("ODO:"); Serial.print(odometer_km, 3); Serial.print(";");
    Serial.print("FUEL:"); Serial.print(fuel_liters, 2); Serial.print(";");
    Serial.print("FB:"); Serial.print(fuelBars); Serial.print(";");
    Serial.print("HL:"); Serial.print(headlight ? 1 : 0);
    Serial.print("\n");

    lastSerialOut = now;
  }
}
