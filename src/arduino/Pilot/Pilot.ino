#include <RoboatAHRS.h>

#include <EEPROM.h>
#include <TinyGPS++.h>

#include <AnalogIn.h>
#include <DigitalIn.h>
#include <DigitalOut.h>
#include <Pin.h>
#include <PwmOut.h>
#include <SafetyPin.h>

#include <SPI.h>
#include "SdFat.h"

#include <i2c_t3.h>
#include <Adafruit_INA219.h>


// SD Card
bool sdCardAvailable = false;
SdFatSdioEX sd;
uint32_t sdCardSize;

uint32_t nextLogTime;
static uint32_t logInterval = 1e6;  // 1 full second
uint32_t statusBlinkEndTime = 0;
uint32_t lastLoopStartTime;


class BoatLog {

  private:
    uint32_t m_logNumber;
    
    ostream &m_serialEcho;
    bool m_enableEcho;
    
    String m_linePrefix;

    String m_fileName;
    ofstream m_fileStream;

  public:
    BoatLog(uint32_t logNumber, FatVolume &sdVolume, ostream &serialEcho) : 
      m_logNumber(logNumber),
      m_serialEcho(serialEcho),
      m_enableEcho(true),
      m_linePrefix(String(m_logNumber) + ",") {

      m_enableEcho = true;
      m_fileName = String("Log_").concat(m_logNumber).concat(".csv");
      m_fileStream.open(m_fileName.c_str(), ios_base::out | ios_base::app);
    }

    BoatLog(uint32_t logNumber, ostream &serialEcho) : 
      m_logNumber(logNumber),
      m_serialEcho(serialEcho),
      m_enableEcho(true),
      m_linePrefix(String(m_logNumber) + ",") {
      
      m_serialEcho << F("Creating boat log #") << m_logNumber << F(" WITHOUT SD CARD. No persistent log will be kept.") << endl;
    }

    void writeln(const String& line) {
      if (m_enableEcho) {
        m_serialEcho << F("LOG: ") << m_linePrefix.c_str() << millis() << "," << line.c_str() << endl;
      }
      if (m_fileStream.is_open()) {
        m_fileStream << m_linePrefix.c_str() << millis() << "," << line.c_str() << endl;
        m_fileStream.flush();
      }
    }

    void setEnableEcho(bool enableEcho) {
      m_enableEcho = enableEcho;
    }
  
};


///////////////////////////////////////////////////////////////////
// Pin and Interface Assignments
///////////////////////////////////////////////////////////////////

DigitalOut onboardLed(LED_BUILTIN);
DigitalOut rpiBootTrigger(26);  // trigger for triggering RPi boot when it is idle

// Subsystem Enables
DigitalOut drivePowerEnable(24);     // enable the motor drives
DigitalOut navPowerEnable(32);       // enable 3.3v power to the IMU and GPS
DigitalOut navLightCommsEnable(39);   // enable communications to the navigation lights

// Battery Charger
// all three of the charger status inputs are open-drain, so enable pullups to differentiate
// between low and hi-Z states.
DigitalIn batteryChargerPG(23, true);
DigitalIn batteryChargerStat1(21, true);
DigitalIn batteryChargerStat2(22, true);

// Right Thruster
PwmOut rightDrive1(30);
PwmOut rightDrive2(29);

// Left Thruster
PwmOut leftDrive1(35);
PwmOut leftDrive2(36);

// IMU (via I2C, on the "Wire" interface)
auto &imuI2CWire(Wire);
DigitalOut imuReset(17);
DigitalIn imuAI1(6);
DigitalIn imuAI2(5);
DigitalIn imuGI1(8);
DigitalIn imuGI2(7);
Roboat::AHRS ahrs(imuReset);


// Power monitor (via I2C, on the "Wire1" interface)
auto &powerSenseI2CWire(Wire1);
Adafruit_INA219 powerMonitor(INA219_ADDRESS, powerSenseI2CWire);

// Debug (USB) serial connection
auto &debugSerial(Serial);
const int DEBUG_SERIAL_BAUD = 115200;
ArduinoOutStream debugOut(debugSerial);

// Serial connection to GPS receiver
auto &gpsSerial(Serial1);
const int GPS_SERIAL_BAUD = 9600;

// Serial connection to Raspberry Pi
auto &rpiSerial(Serial2);
const int RPI_SERIAL_BAUD = 115200;
ArduinoOutStream rpiOut(rpiSerial);


///////////////////////////////////////////////////////////////////
// Other Globals
///////////////////////////////////////////////////////////////////

// GPS Parser
TinyGPSPlus gps;

uint16_t epoch = 0;
static const int EPOCH_ADDRESS_LSB = 512;
static const int EPOCH_ADDRESS_MSB = 513;


void setEpoch(uint16_t newEpoch) {
  uint8_t msb = (newEpoch & 0xFF00) >> 8;
  uint8_t lsb = (newEpoch & 0x00FF);
  EEPROM.write(EPOCH_ADDRESS_MSB, msb);
  EEPROM.write(EPOCH_ADDRESS_LSB, lsb);
}

uint16_t getAndIncrementEpoch() {
  uint8_t msb = EEPROM.read(EPOCH_ADDRESS_MSB);
  uint8_t lsb = EEPROM.read(EPOCH_ADDRESS_LSB);
  uint32_t epoch = msb;
  epoch <<= 8;
  epoch += lsb;
  epoch += 1;
  setEpoch(epoch);
  return epoch;
}

BoatLog *boatLog = NULL;

// Logged status values
bool gpsFixValid = false;
uint32_t gpsFixAge = 0;
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
  epoch = getAndIncrementEpoch();
  debugOut << F("Epoch Number: ") << epoch << endl;

  // Start by turning off everything that can be turned off.
  // Will bring it up gradually while doing system checks.
  debugOut << F("Disabling drive, nav sensor, and nav light subsystems.") << endl;
  drivePowerEnable.low();
  navPowerEnable.low();
  navLightCommsEnable.low();

  debugOut << F("Turning on power monitor.") << endl;
  powerMonitor.begin();

  debugOut << F("Disabling RPi boot trigger.") << endl;
  rpiBootTrigger.high();

  // Attempt to set up the SD card
  if (!sd.cardBegin()) {
    debugOut << F("Failed to initialize SD card.") << endl;
  } else {
    sdCardSize = sd.card()->cardSize();
    if (sdCardSize == 0) {
      debugOut << F("Failed to read size of SD card.") << endl;
    } else if (!sd.fsBegin()) {
      debugOut << F("Failed to start filesystem on SD card.") << endl;
    } else {
      uint32_t volFree = sd.vol()->freeClusterCount();
      float fs = 0.000512 * volFree * sd.vol()->blocksPerCluster();
      debugOut << F("Successfully started up SD card with ") << fs << F(" MB of free space.") << endl;
      sdCardAvailable = true;
    }
  }

  debugOut << F("Configuring GPS serial port for ") << GPS_SERIAL_BAUD << F(" baud.") << endl;
  gpsSerial.begin(GPS_SERIAL_BAUD);

  debugOut << F("Configuring RPi serial port for ") << RPI_SERIAL_BAUD << F(" baud.") << endl;
  rpiSerial.begin(RPI_SERIAL_BAUD);

  if (sdCardAvailable) {
    boatLog = new BoatLog(epoch, *sd.vol(), rpiOut);
  } else {
    boatLog = new BoatLog(epoch, rpiOut);
  }

  debugOut << F("Enabling nav power...") << endl;
  navPowerEnable.high();
  
  debugOut << F("Connecting to IMU...") << endl;
  imuI2CWire.begin();

  ahrs.setActive(true);
  
  nextLogTime = micros();
  lastLoopStartTime = nextLogTime;


  SdFile file;
  sd.vwd()->rewind();
  while (file.openNext(sd.vwd(), O_READ)) {
    file.printFileSize(&debugSerial);
    debugSerial.write(' ');
    file.printModifyDateTime(&debugSerial);
    debugSerial.write(' ');
    file.printName(&debugSerial);
    if (file.isDir()) {
      // Indicate a directory.
      debugSerial.write('/');
    }
    debugSerial.println();
    file.close();
  }
  debugSerial.println("Done!");


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

  ahrs.update(currentMicros);

  if (currentMicros >= nextLogTime) {
    onboardLed.high();

    String logLine = lastLoopDuration;

    logLine.concat(",");
    logLine.concat(int(navPowerEnable.read()));
    
    if (gpsFixValid) {
      logLine.concat(",1,");
      logLine.concat(String(gps.location.lat(), 12));
      logLine.concat(",");
      logLine.concat(String(gps.location.lng(), 12));
      logLine.concat(",");
    } else {
      logLine.concat(",0,0,0,");
    }
    logLine.concat(int(gps.satellites.value()));
    logLine.concat(",");
    logLine.concat(int(gpsFixAge));

    float busvoltage = powerMonitor.getBusVoltage_V();
    float current_mA = -1 * powerMonitor.getCurrent_mA();

    logLine.concat(",");
    logLine.concat(String(busvoltage, 8));
    logLine.concat(",");
    logLine.concat(String(current_mA/1000, 8));

    bool pg = !batteryChargerPG.read();
    bool stat1 = !batteryChargerStat1.read();
    bool stat2 = !batteryChargerStat2.read();

    logLine.concat(",");
    logLine.concat(String(pg));
    logLine.concat(",");
    logLine.concat(String(stat1));
    logLine.concat(",");
    logLine.concat(String(stat2));

    logLine.concat(ahrs.getState());
    logLine.concat(",");
    if (ahrs.getState() == Roboat::AHRSState::RUNNING) {
      logLine.concat(ahrs.getHeading());
    } else {
      logLine.concat("-");
    }

    boatLog->writeln(logLine);

    nextLogTime += logInterval;
    statusBlinkEndTime = currentMicros + 1000;
    maxLoopTime = 0;

//    debugOut << (pg ? "O " : "X ") << (stat1 ? "O " : "X ") << (stat2 ? "O " : "X ") << endl;
    if (pg) {
      if (!(stat1 && stat2)) {
        debugOut << F("On external power.");
        if (!stat1 && !stat2) {
          debugOut << F("  No battery present.");
        } else if (!stat1 && stat2) {
          debugOut << F("  Charge complete.");
        } else if (stat1 && !stat2) {
          debugOut << F("  Charging...");
        }
      } else {
        debugOut << F("Battery temperature fault.");
      }
    } else {
      debugOut << F("On battery power.");
    }

    debugOut << "  Bus Voltage: " << busvoltage << " V";
    debugOut << "  Current: " << current_mA << " mA";
    debugOut << "  Power: " << (busvoltage * current_mA / 1000) << " W";

    debugOut << endl;

    
  } else if (currentMicros >= statusBlinkEndTime) {
    onboardLed.low();
  }


  // Feed any new GPS data into the parser.
  if (gpsSerial.available() > 0) {
    while (gpsSerial.available() > 0) {
      gps.encode(gpsSerial.read());
    }

    gpsFixValid = gps.location.isValid();
    gpsFixAge = gps.location.age();

//    if (gpsFixValid) {
//      if (gps.location.isUpdated()) {
//        debugOut << int(gps.location.age()) << "ms  " << int(gps.time.hour()) << ":" << int(gps.time.minute()) << ":" << int(gps.time.second())
//                 << "  (" << setprecision(8) << gps.location.lat() << ", " << gps.location.lng() << ") : " << setprecision(3) << gps.speed.mph() << "mph" << endl;
//      }
//    }

  }
}
