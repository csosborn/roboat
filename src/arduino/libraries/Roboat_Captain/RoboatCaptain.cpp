#include "RoboatCaptain.h"

namespace Roboat {
    namespace Conn {

        // reset after 10s on error
        const uint32_t ERROR_RESET_DELAY = 10e6;
                
        const int RPI_SERIAL_BAUD = 115200;
        
        Captain::Captain(HardwareSerial& serialPort, DigitalOut& wakeSignalPin) :
            StateMachine(STARTUP, "Captain"),
            port(serialPort),
            wakeSignal(wakeSignalPin)
        {}

        bool Captain::update() {
            switch (getState()) {
                case STARTUP:
                    goToState(ACTIVATING, 10);
                    break;

                case ERROR:
                    goToState(STARTUP, ERROR_RESET_DELAY);
                    break;

                case ACTIVATING:
                    Serial.print(F("Configuring RPI serial port for "));
                    Serial.print(RPI_SERIAL_BAUD);
                    Serial.println(F(" baud."));
                    port.begin(RPI_SERIAL_BAUD);

                    // The captain should start the cruise awake (and as it happens the
                    // RPI will boot when the system powers up whether we like it or not).
                    goToState(WAKING);
                    break;

                case ASLEEP:
                    if (port.available() > 0) {
                        // this is unexpected
                        Serial.println("Found data on RPI serial channel, but RPI expected to be asleep.");
                        goToState(ERROR);
                    } else {
                        // TODO: see if captain should be awakened
                    }
                    break;
                
                case WAKING:
                    // driving wake signal pin low to trigger RPI boot
                    wakeSignal.low();
                    // TODO: wait for ready signal on serial port indicating
                    // RPI is up and running
                    if (port.available() > 0) {
                        // captain is awake
                        goToState(ONDECK);
                    }
                    break;
                
                case ONDECK:
                    // TODO
                    break;
                
                default:
                    Serial.println("Unexpected state encountered!");
                    goToState(ERROR);
            }

            return false;
        }

        String Captain::getLogString() const {
            String logStr(getState());
            return logStr;
        }

        const char * Captain::getStateName(const State aState) const {
            switch (aState) {
                case STARTUP:
                    return "STARTUP";
                case ERROR:
                    return "ERROR";
                case ACTIVATING:
                    return "ACTIVATING";
                case ASLEEP:
                    return "ASLEEP";
                case WAKING:
                    return "WAKING";
                case ONDECK:
                    return "ONDECK";                    
                default:
                    return "<INVALID>";
            }
        }
    
    }
}