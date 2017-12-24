#include "Arduino.h"
#include "RoboatPowerManager.h"


namespace Roboat {

    // reset after 10s on error
    const uint32_t ERROR_RESET_DELAY = 10e6;

    const uint32_t RUNNING_UPDATE_INTERVAL = 10e4;

    // sanity check ranges for voltage and current; outside these
    // bounds we assume an error
    const float MIN_VALID_VOLTAGE = 1.0;
    const float MAX_VALID_VOLTAGE = 10.0;
    const float MIN_VALID_CURRENT = 20.0;
    const float MAX_VALID_CURRENT = 2000.0; 

    namespace Power {

        Manager::Manager(const DigitalIn& chargerPGPin, const DigitalIn& chargerStat1Pin, const DigitalIn& chargerStat2Pin,
            i2c_t3& ina219Wire, int ina219Address) :
            StateMachine(STARTUP, "Power"),
            powerMonitor(ina219Address, ina219Wire),
            chargerPG(chargerPGPin), chargerStat1(chargerStat1Pin), chargerStat2(chargerStat2Pin)
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
                    powerMonitor.begin();
                    dispatchToRunningState();
                    measurePowerState();
                    break;
                
                case ERROR_BATT_TEMP:
                case NO_BATTERY:
                case BATTERY:
                case CHARGING:
                case MAINTAINING:
                    dispatchToRunningState();
                    measurePowerState();
                    break;
                
                default:
                    Serial.println("Unexpected state encountered!");
                    goToState(ERROR);
            }

            return false;
        }

        void Manager::dispatchToRunningState() {
            bool pg = !chargerPG.read();
            bool stat1 = !chargerStat1.read();
            bool stat2 = !chargerStat2.read();
        
            if (pg) {
                if (!(stat1 && stat2)) {
                //   debugOut << F("On external power.");
                  if (!stat1 && !stat2) {
                    // debugOut << F("  No battery present.");
                    goToState(NO_BATTERY, RUNNING_UPDATE_INTERVAL);
                  } else if (!stat1 && stat2) {
                    // debugOut << F("  Charge complete.");
                    goToState(MAINTAINING, RUNNING_UPDATE_INTERVAL);
                  } else if (stat1 && !stat2) {
                    // debugOut << F("  Charging...");
                    goToState(CHARGING, RUNNING_UPDATE_INTERVAL);
                  }
                } else {
                //   debugOut << F("Battery temperature fault.");
                  goToState(ERROR_BATT_TEMP);
                }
              } else {
                // debugOut << F("On battery power.");
                goToState(BATTERY, RUNNING_UPDATE_INTERVAL);
              }
        }

        void Manager::measurePowerState() {
            voltage = powerMonitor.getBusVoltage_V();
            current = -1 * powerMonitor.getCurrent_mA();    // Roboat α current sense wired backwards
            if (voltage < MIN_VALID_VOLTAGE || voltage > MAX_VALID_VOLTAGE ||
                current < MIN_VALID_CURRENT || current > MAX_VALID_CURRENT) 
            {
                goToState(ERROR);
            }
        }

        float Manager::getVoltage() {
            return voltage;
        }

        float Manager::getCurrent() {
            return current;
        }

        float Manager::getPower() {
            return (voltage * current / 1000);
        }

        const char* Manager::getStateName(const State aState) {
            switch (aState) {
                case STARTUP:
                    return "STARTUP";
                case ERROR:
                    return "ERROR";
                case ACTIVATING:
                    return "ACTIVATING";
                case NO_BATTERY:
                    return "NO_BATTERY";
                case BATTERY:
                    return "BATTERY";
                case CHARGING:
                    return "CHARGING";
                case MAINTAINING:
                    return "MAINTAINING";

                default:
                    return "<INVALID>";
            }
        }
    }

}