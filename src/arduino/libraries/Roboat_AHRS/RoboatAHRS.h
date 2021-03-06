#ifndef ROBOAT_AHRS_H
#define ROBOAT_AHRS_H

#include "Arduino.h"
#include "SafetyPin.h"
#include "RoboatStateMachine.h"

#include <Adafruit_Sensor.h>
#include <Adafruit_FXAS21002C.h>
#include <Adafruit_FXOS8700.h>
#include <Madgwick.h>


namespace Roboat {

    namespace IMU {

        typedef enum {
            STARTUP,
            ERROR,
            DISABLED,
            ACTIVATING_1,
            ACTIVATING_2,
            SETTLING,
            RUNNING,
            DEACTIVATING
        } State;


        class AHRS : public StateMachine<State, AHRS> {
            DigitalOut& imuReset;
            Adafruit_FXAS21002C gyro;
            Adafruit_FXOS8700 accelmag;
            Madgwick filter;

            bool requestedActive;

            float roll;
            float pitch;
            float heading;

            void updateFilter();
            
        public:
            AHRS(DigitalOut& imuResetPin);

            // Set to true to enable AHRS functions, false to disable.
            void setActive(bool active);

            // Advance the state machine. Returns true if the update results in any
            // change in external state, false if the update is a noop or affects only
            // state internal to the RoboatAHRS instance.
            bool update();

            const char * getStateName(const State aState) const;
            
            float getHeading() const;

            String getLogString() const;
        };

    }

}

#endif