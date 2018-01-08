#ifndef ROBOAT_LOGGER_H
#define ROBOAT_LOGGER_H

#include "Arduino.h"
#include <RoboatStateMachine.h>

#include "SdFat.h"

namespace Roboat {
    
    namespace Log {

        static const int EPOCH_ADDRESS_LSB = 512;
        static const int EPOCH_ADDRESS_MSB = 513;
    
        typedef enum {
            STARTUP,
            ERROR,
            ACTIVATING,
            ERROR_NO_CARD,
            ERROR_CARD_FULL,            
            READY
        } State;
        

        class Manager : public StateMachine<State, Manager> {

            SdFatSdioEX sd;
            uint32_t cardSize;
            uint32_t freeSpace;
            uint16_t epoch;
            bool enableEcho;
            
            const String linePrefix;
            const String fileName;
            ofstream fileStream;
            
            ostream &serialEcho;
            
            void measureFreeSpace();

            void setEpoch(uint16_t newEpoch);
              
            uint16_t getAndIncrementEpoch();

        public:
            Manager(ostream &serialEcho);

            // Advance the state machine.
            bool update();

            const char * getStateName(const State aState) const;
            
            // return free space in Kb
            uint32_t getFreeSpace() const;

            uint16_t getEpoch() const;

            void writeln(const String& line);

            String getLogString() const;

            // Manager& operator << (const String& str);
        };


        // Manager& endl(Manager& os);

    }

}


#endif