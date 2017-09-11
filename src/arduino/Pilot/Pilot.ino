#include <TinyGPS++.h>

#include <AnalogIn.h>
#include <DigitalIn.h>
#include <DigitalOut.h>
#include <Pin.h>
#include <PwmOut.h>
#include <SafetyPin.h>


DigitalOut onboardLed(LED_BUILTIN);
DigitalOut rpiBootTrigger(28);  // trigger for triggering RPi boot when it is idle

// Left Thruster
DigitalOut leftThrusterEn(24);
PwmOut leftThrusterFor(35);
PwmOut leftThrusterRev(36);

// Right Thruster
DigitalOut rightThrusterEn(25);
PwmOut rightThrusterFor(37);
PwmOut rightThrusterRev(38);

// Debug (USB) serial connection
usb_serial_class &debugSerial(Serial);
const int DEBUG_SERIAL_BAUD = 115200;

// Serial connection to GPS receiver
//HardwareSerial &gpsSerial(Serial1);
HardwareSerial &gpsSerial(Serial2);
const int GPS_SERIAL_BAUD = 9600;

// Serial connection to Raspberry Pi
//HardwareSerial &rpiSerial(Serial2);
HardwareSerial &rpiSerial(Serial1);
const int RPI_SERIAL_BAUD = 115200;

// GPS Parser
TinyGPSPlus gps;

void setup() {
  // Set up debug serial output first
  debugSerial.begin(DEBUG_SERIAL_BAUD);
  
  delay(1000);
  debugSerial.println("Beginning Roboat startup...");
  delay(1000);

  debugSerial.println("Disabling RPi boot trigger.");
  rpiBootTrigger.high();

  debugSerial.print("Configuring GPS serial port for ");
  debugSerial.print(GPS_SERIAL_BAUD);
  debugSerial.println(" baud.");
  gpsSerial.begin(GPS_SERIAL_BAUD);

  debugSerial.print("Configuring RPi serial port for ");
  debugSerial.print(RPI_SERIAL_BAUD);
  debugSerial.println(" baud.");
  rpiSerial.begin(RPI_SERIAL_BAUD);

  debugSerial.println("Startup complete.");
  debugSerial.println("===============================");
}

void loop() {

  // Feed any new GPS data into the parser.
  if (gpsSerial.available() > 0) {
    while (gpsSerial.available() > 0) {
      gps.encode(gpsSerial.read());
    }

    if (gps.location.isValid()) {
      if (gps.location.isUpdated()) {
        onboardLed.write(gps.location.age() < 1000);
        debugSerial.print(gps.location.age());
        debugSerial.print("ms  ");
        debugSerial.print(gps.time.hour());
        debugSerial.print(":");
        debugSerial.print(gps.time.minute());
        debugSerial.print(":");
        debugSerial.print(gps.time.second());
        debugSerial.print("  (");
        debugSerial.print(gps.location.lat(), 8);
        debugSerial.print(", ");
        debugSerial.print(gps.location.lng(), 8);
        debugSerial.print(") : ");
        debugSerial.println(gps.speed.mph());
      } else {
    //    debugSerial.println("No valid GPS data.");
      }
    }
  }
}
