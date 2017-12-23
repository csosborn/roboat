#ifndef ROBOAT_AHRS_H
#define ROBOAT_AHRS_H

#include "Arduino.h"
#include "SafetyPin.h"

#include <Adafruit_Sensor.h>
#include <Adafruit_FXAS21002C.h>
#include <Adafruit_FXOS8700.h>
#include <Madgwick.h>


namespace Roboat {

    typedef enum {
        STARTUP,
        ERROR,
        DISABLED,
        ACTIVATING_1,
        ACTIVATING_2,
        SETTLING,
        RUNNING,
        DEACTIVATING
    } AHRSState;


    class AHRS {
        AHRSState state;
        AHRSState nextState;
        uint32_t lastUpdateTime;
        uint32_t nextUpdateTime;
        uint32_t stateEntryTime;
        float roll;
        float pitch;
        float heading;

        DigitalOut& imuReset;
        Adafruit_FXAS21002C gyro;
        Adafruit_FXOS8700 accelmag;
        Madgwick filter;

        bool requestedActive;

        void goToState(AHRSState newState, uint32_t transitionDelay = 0);
        const char * stateName(const AHRSState aState);
        void updateFilter();
        
    public:
        AHRS(DigitalOut& imuResetPin);

        // Set to true to enable AHRS functions, false to disable.
        void setActive(bool active);

        // Advance the state machine. Returns true if the update results in any
        // change in external state, false if the update is a noop or affects only
        // state internal to the RoboatAHRS instance.
        bool update(const uint32_t now);

        // The time spent so far in the current state (in us).
        uint32_t timeInState();

        // The current state.
        AHRSState getState();

        float getHeading();
    };

}

#endif