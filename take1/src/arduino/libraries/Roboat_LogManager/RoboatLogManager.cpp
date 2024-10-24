#include "Arduino.h"
#include <RoboatLogManager.h>
// #include <iostream.h>

#include <EEPROM.h>

namespace Roboat {

    namespace Log {

        // reset after 10s on error
        const uint32_t ERROR_RESET_DELAY = 10e6;
    
        const uint32_t ERROR_LOOP_PERIOD = 1e6;  // recheck error conditions at 1Hz
        
        const uint32_t READY_LOOP_PERIOD = 1e4;  // handle log ops at 100Hz

        Manager::Manager(ostream &serialEcho) :
            StateMachine(STARTUP, "Log"),
            cardSize(0),
            freeSpace(0),
            epoch(getAndIncrementEpoch()),
            enableEcho(true),
            linePrefix(String(getEpoch()) + ","),
            fileName(String("Log_").concat(getEpoch()).concat(".csv")),
            serialEcho(serialEcho)            
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

        const char * Manager::getStateName(const State aState) const {
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

        uint32_t Manager::getFreeSpace() const {
            return freeSpace;
        }

        uint16_t Manager::getEpoch() const {
            return epoch;
        }

        void Manager::setEpoch(uint16_t newEpoch) {
            uint8_t msb = (newEpoch & 0xFF00) >> 8;
            uint8_t lsb = (newEpoch & 0x00FF);
            EEPROM.write(EPOCH_ADDRESS_MSB, msb);
            EEPROM.write(EPOCH_ADDRESS_LSB, lsb);
        }
          
        uint16_t Manager::getAndIncrementEpoch() {
            uint8_t msb = EEPROM.read(EPOCH_ADDRESS_MSB);
            uint8_t lsb = EEPROM.read(EPOCH_ADDRESS_LSB);
            uint32_t epoch_tmp = msb;
            epoch_tmp <<= 8;
            epoch_tmp += lsb;
            epoch_tmp += 1;
            setEpoch(epoch_tmp);
            return epoch_tmp;
        }

        void Manager::writeln(const String& line) {
            if (enableEcho) {
                serialEcho << F("LOG: ") << linePrefix.c_str() << millis() << "," << line.c_str() << endl;
            }
            if (fileStream.is_open()) {
                fileStream << linePrefix.c_str() << millis() << "," << line.c_str() << endl;
                fileStream.flush();
            }
        }
      
        String Manager::getLogString() const {
            String logStr(getState());
            logStr.concat(",");
            logStr.concat(getFreeSpace());
            return logStr;        
        }

        // Manager& Manager::operator << (const String& str) {
        //     return *this;
        // }
        

          
    }

}