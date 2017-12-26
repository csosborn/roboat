#include "Arduino.h"
#include <RoboatLogManager.h>


namespace Roboat {

    namespace Log {

        // reset after 10s on error
        const uint32_t ERROR_RESET_DELAY = 10e6;
    
        const uint32_t ERROR_LOOP_PERIOD = 1e6;  // recheck error conditions at 1Hz
        
        const uint32_t READY_LOOP_PERIOD = 1e4;  // handle log ops at 100Hz

        Manager::Manager() :
            StateMachine(STARTUP, "Log"),
            cardSize(0),
            freeSpace(0)
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
                    if (sd.cardBegin()) {
                        cardSize = sd.card()->cardSize();
                        if (sd.fsBegin()) {
                            measureFreeSpace();
                            goToState(READY);
                        }
                    } else {
                        Serial.println(F("Failed to initialize SD card. Will retry."));
                    }
                    break;
                    
                case ERROR_NO_CARD:
                case ERROR_CARD_FULL:
                    // these are unrecoverable errors, so we stay here
                    remain(ERROR_LOOP_PERIOD);
                    break;
                    
                case READY:
                    // the normal loop, writing and reading
                    remain(READY_LOOP_PERIOD);
                    break;
                
                default:
                    Serial.println("Unexpected state encountered!");
                    goToState(ERROR);
            }

            return false;
        }

        void Manager::measureFreeSpace() {
            uint32_t volFree = sd.vol()->freeClusterCount();
            freeSpace = 0.512 * volFree * sd.vol()->blocksPerCluster();
        }

        const char * Manager::getStateName(const State aState) {
            switch (aState) {
                case STARTUP:
                    return "STARTUP";
                case ERROR:
                    return "ERROR";
                case ACTIVATING:
                    return "ACTIVATING";
                case ERROR_NO_CARD:
                    return "ERROR_NO_CARD";
                case ERROR_CARD_FULL:
                    return "ERROR_CARD_FULL";
                case READY:
                    return "READY";

                default:
                    return "<INVALID>";
            }
        }

        uint32_t Manager::getFreeSpace() {
            return freeSpace;
        }
    }

}