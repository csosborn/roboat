#ifndef ROBOAT_GPSMANAGER_H
#define ROBOAT_GPSMANAGER_H

#include "Arduino.h"
#include "RoboatStateMachine.h"
#include <TinyGPS++.h>

namespace Roboat {

    namespace GPS {

        typedef enum {
            STARTUP,
            ERROR,
            ACTIVATING,
            SEARCHING,
            REACQUIRING,
            RUNNING
        } State;
        

        class Manager : public StateMachine<State, Manager> {

            // Serial port
            HardwareSerial& port;

            // GPS Parser
            TinyGPSPlus parser;

            // Read and parse any new serial data and update state variables.
            // Returns true if new data was incorporated (if not, then the state
            // will be unchanged). 
            bool readAndParse();

            float lat;
            float lon;
            float satsUsed;
            float fixAge;

        public:
            Manager(HardwareSerial& serialPort);

            // Advance the state machine.
            bool update();
                        
            const char * getStateName(const State aState) const;
            
            String getLogString() const;
            
        };

    }

}

#endif