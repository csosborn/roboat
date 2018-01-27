#include "RoboatGPSManager.h"

namespace Roboat {

    namespace GPS {

        // reset after 10s on error
        const uint32_t ERROR_RESET_DELAY = 10e6;

        // time after which a fix is considered stale
        const uint32_t MAX_FIX_AGE = 3000;     // three seconds

        const int GPS_SERIAL_BAUD = 9600;
                
        Manager::Manager(HardwareSerial& serialPort):
            StateMachine(STARTUP, "GPS"),    
            port(serialPort)
        {}

        bool Manager::update() {
            switch (getState()) {
                case STARTUP:
                    goToState(ACTIVATING, 10);
                    break;

                case ERROR:
                    goToState(STARTUP, ERROR_RESET_DELAY);
                    break;

                case ACTIVATING:
                    Serial.print(F("Configuring GPS serial port for "));
                    Serial.print(GPS_SERIAL_BAUD);
                    Serial.println(F(" baud."));
                    port.begin(GPS_SERIAL_BAUD);
                    goToState(SEARCHING);
                    break;

                case SEARCHING:
                    readAndParse();
                    if (parser.location.isValid()) {
                        goToState(RUNNING);
                    }
                    break;
                
                case REACQUIRING:
                    readAndParse();
                    if (parser.location.age() < MAX_FIX_AGE) {
                        goToState(RUNNING);
                    }
                    break;
                
                case RUNNING:
                    readAndParse();
                    if (!parser.location.isValid()) {
                        goToState(SEARCHING);
                    }
                    if (parser.location.age() > MAX_FIX_AGE) {
                        goToState(REACQUIRING);
                    }
                    break;
                
                default:
                    Serial.println("Unexpected state encountered!");
                    goToState(ERROR);
            }

            return false;
        }

        bool Manager::readAndParse() {
            if (port.available() > 0) {
                // Ooh look, data. Read it and update state.
                while (port.available() > 0) {
                  parser.encode(port.read());
                }
                lat = parser.location.lat();
                lon = parser.location.lng();
                satsUsed = parser.satellites.value();
                fixAge = parser.location.age();
                return true;
            } else {
                // nothing this time around
                return false;
            }
        }

        String Manager::getLogString() const {
            String logStr(getState());
            logStr.concat(",");

            if (getState() == RUNNING) {
                logStr.concat(String(lat, 12));
                logStr.concat(",");
                logStr.concat(String(lon, 12));
                logStr.concat(",");
            } else {
                logStr.concat("0,0,");
            }
            logStr.concat(int(satsUsed));
            logStr.concat(",");
            logStr.concat(fixAge);

            return logStr;
        }

        const char * Manager::getStateName(const State aState) const {
            switch (aState) {
                case STARTUP:
                    return "STARTUP";
                case ERROR:
                    return "ERROR";
                case ACTIVATING:
                    return "ACTIVATING";
                case SEARCHING:
                    return "SEARCHING";
                case REACQUIRING:
                    return "REACQUIRING";
                case RUNNING:
                    return "RUNNING";                    
                default:
                    return "<INVALID>";
            }
        }


    }

}