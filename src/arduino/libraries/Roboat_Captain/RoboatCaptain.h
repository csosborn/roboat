#ifndef ROBOAT_CAPTAIN_H
#define ROBOAT_CAPTAIN_H

#include "Arduino.h"
#include <RoboatStateMachine.h>
#include <SafetyPin.h>

namespace Roboat {
    namespace Conn {

        typedef enum {
            STARTUP,
            ERROR,
            ACTIVATING,
            ASLEEP,
            WAKING,
            ONDECK
        } State;
        

        class Captain : public StateMachine<State, Captain> {

            HardwareSerial& port;
            DigitalOut& wakeSignal;

        public:
            Captain(HardwareSerial& serialPort, DigitalOut& wakeSignalPin);

            // Advance the state machine.
            bool update();
                        
            const char * getStateName(const State aState) const;
            
            String getLogString() const;

        };

    }
}

#endif