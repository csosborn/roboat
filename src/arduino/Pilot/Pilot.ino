#include <RoboatPowerManager.h>
#include <RoboatLogManager.h>
#include <RoboatAHRS.h>
#include <RoboatGPSManager.h>

#include <SafetyPin.h>
#include <SPI.h>
#include <i2c_t3.h>

// Debug (USB) serial connection
auto &debugSerial(Serial);
const int DEBUG_SERIAL_BAUD = 115200;
ArduinoOutStream debugOut(debugSerial);

Roboat::Log::Manager logManager(debugOut);


uint32_t nextLogTime;
static uint32_t logInterval = 1e6;  // 1 full second
uint32_t statusBlinkEndTime = 0;
uint32_t lastLoopStartTime;



///////////////////////////////////////////////////////////////////
// Pin and Interface Assignments
///////////////////////////////////////////////////////////////////

DigitalOut onboardLed(LED_BUILTIN);
DigitalOut rpiBootTrigger(26);  // trigger for triggering RPi boot when it is idle

// Subsystem Enables
DigitalOut drivePowerEnable(24);     // enable the motor drives
DigitalOut navPowerEnable(32);       // enable 3.3v power to the IMU and GPS
DigitalOut navLightCommsEnable(39);   // enable communications to the navigation lights

// Right Thruster
PwmOut rightDrive1(30);
PwmOut rightDrive2(29);

// Left Thruster
PwmOut leftDrive1(35);
PwmOut leftDrive2(36);

// IMU (via I2C on the "Wire" interface)
auto &imuI2CWire(Wire);
DigitalOut imuReset(17);
DigitalIn imuAI1(6), imuAI2(5), imuGI1(8), imuGI2(7);
Roboat::IMU::AHRS ahrs(imuReset);

// Power monitor (via I2C on the "Wire1" interface)
auto &powerSenseI2CWire(Wire1);

// Battery Charger
// (all three of the charger status inputs are open-drain, so enable pullups to differentiate between low and hi-Z states)
DigitalIn chargerPG(23, true), chargerStat1(21, true), chargerStat2(22, true);

// Power manager state machine, communicating with INA219 I/V sensor and battery charger
Roboat::Power::Manager powerManager(chargerPG, chargerStat1, chargerStat2, powerSenseI2CWire, INA219_ADDRESS);

// GPS manager state machine, communicating with GPS hardware on Serial1
Roboat::GPS::Manager gpsManager(Serial1);

// Serial connection to Raspberry Pi
auto &rpiSerial(Serial2);
const int RPI_SERIAL_BAUD = 115200;
ArduinoOutStream rpiOut(rpiSerial);


///////////////////////////////////////////////////////////////////
// Other Globals
///////////////////////////////////////////////////////////////////

uint32_t maxLoopTime = 0;


///////////////////////////////////////////////////////////////////
// Setup and Loop
///////////////////////////////////////////////////////////////////

void setup() {
  // Turn on the orange LED for the duration of setup, then go to normal diagnostic blink mode.
  onboardLed.high();

  // Set up debug serial output first
  debugSerial.begin(DEBUG_SERIAL_BAUD);

  delay(1000);
  debugOut << F("Beginning Roboat startup...") << endl;
  delay(100);
  debugOut << F("Epoch Number: ") << logManager.getEpoch() << endl;

  // Start by turning off everything that can be turned off.
  // Will bring it up gradually while doing system checks.
  debugOut << F("Disabling drive, nav sensor, and nav light subsystems.") << endl;
  drivePowerEnable.low();
  navPowerEnable.low();
  navLightCommsEnable.low();

  debugOut << F("Disabling RPi boot trigger.") << endl;
  rpiBootTrigger.high();

  debugOut << F("Configuring RPi serial port for ") << RPI_SERIAL_BAUD << F(" baud.") << endl;
  rpiSerial.begin(RPI_SERIAL_BAUD);

  debugOut << F("Enabling nav power...") << endl;
  navPowerEnable.high();
  
  debugOut << F("Connecting to IMU...") << endl;
  imuI2CWire.begin();

  ahrs.setActive(true);
  
  nextLogTime = micros();
  lastLoopStartTime = nextLogTime;

  debugOut << F("Startup complete.") << endl;
  debugOut << F("===============================") << endl;

  onboardLed.low();
}

void loop() {
  // The main loop logs a status message every second.

  uint32_t currentMicros = micros();
  uint32_t lastLoopDuration = currentMicros - lastLoopStartTime;
  if (lastLoopDuration > maxLoopTime) {
    maxLoopTime = lastLoopDuration;
  }
  lastLoopStartTime = currentMicros;

  // Advance all subsystem state machines.
  ahrs.advance(currentMicros);
  powerManager.advance(currentMicros);
  logManager.advance(currentMicros);
  gpsManager.advance(currentMicros);

  if (currentMicros >= nextLogTime) {
    onboardLed.high();

    String logLine = lastLoopDuration;

    logLine.concat(",");
    logLine.concat(int(navPowerEnable.read()));
    
    logLine.concat(",");
    logLine.concat(logManager.getLogString());
    
    logLine.concat(",");
    logLine.concat(powerManager.getLogString());

    logLine.concat(",");
    logLine.concat(gpsManager.getLogString());

    logLine.concat(",");
    logLine.concat(ahrs.getLogString());

    logManager.writeln(logLine);

    nextLogTime += logInterval;
    statusBlinkEndTime = currentMicros + 1000;
    maxLoopTime = 0;
    
  } else if (currentMicros >= statusBlinkEndTime) {
    onboardLed.low();
  }

}
