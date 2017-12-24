#ifndef ROBOAT_POWERMANAGER_H
#define ROBOAT_POWERMANAGER_H

#include "Arduino.h"
#include "RoboatStateMachine.h"
#include "SafetyPin.h"
#include <i2c_t3.h>
#include <Adafruit_INA219.h>


namespace Roboat {

    namespace Power {
        
        typedef enum {
            STARTUP,            // initial startup state, no information available
            ERROR,              // invalid battery manager state or unable to read I/V
            ERROR_BATT_TEMP,    // battery is too hot and charging has stopped
            ACTIVATING,         // connecting to power monitor
            NO_BATTERY,         // externally powered, but no battery detected
            BATTERY,            // running exclusively on battery
            CHARGING,           // battery is charging (or possibly supplementing external power)
            MAINTAINING         // battery fully charged and being maintained
        } State;


        class Manager : public StateMachine<State, Manager> {

            Adafruit_INA219 powerMonitor;

            const DigitalIn& chargerPG;
            const DigitalIn& chargerStat1;
            const DigitalIn& chargerStat2;

            float voltage;  // bus voltage (V)
            float current;  // Manager current draw (mA)

            void dispatchToRunningState();
            void measurePowerState();
            
        public:
            Manager(const DigitalIn& chargerPGPin, const DigitalIn& chargerStat1Pin, const DigitalIn& chargerStat2Pin,
                i2c_t3& ina219Wire, int ina219Address);
            
            bool update();
            const char * getStateName(const State aState);
    
            float getVoltage();
            float getCurrent();
            float getPower();
    
        };
            
    }


}

#endif