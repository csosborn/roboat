#include "RoboatAHRS.h"

#include "Arduino.h"
#include <Adafruit_Sensor.h>
#include <Adafruit_FXAS21002C.h>
#include <Adafruit_FXOS8700.h>
#include <Madgwick.h>


namespace Roboat {
    
    namespace IMU {

        // allow the AHRS to settle for 5s before using data
        const uint32_t SETTLING_DELAY = 5e6;

        // reset after 10s on error
        const uint32_t ERROR_RESET_DELAY = 10e6;

        // degrees per radian for conversion
        const float DEG_PER_RAD = 57.2958F;

        // Mag calibration values are calculated via ahrs_calibration.
        // These values must be determined for each baord/environment.
        // See the image in this sketch folder for the values used
        // below.

        // Offsets applied to raw x/y/z mag values
        const float mag_offsets[3]            = { 0.93F, -7.47F, -35.23F };

        // Soft iron error compensation matrix
        const float mag_softiron_matrix[3][3] = { {  0.943,  0.011,  0.020 },
                                                {  0.022,  0.918, -0.008 },
                                                {  0.020, -0.008,  1.156 } };

        const float mag_field_strength        = 50.23F;

        // Offsets applied to compensate for gyro zero-drift error for x/y/z
        const float gyro_zero_offsets[3]      = { 0.0F, 0.0F, 0.0F };


        AHRS::AHRS(DigitalOut& imuResetPin) :
            StateMachine(STARTUP, "AHRS"),
            imuReset(imuResetPin),
            gyro(Adafruit_FXAS21002C(0x0021002C)),
            accelmag(Adafruit_FXOS8700(0x8700A, 0x8700B)),
            requestedActive(false)
        {}

        void AHRS::setActive(bool active) {
            requestedActive = active;
        }

        bool AHRS::update() {
            switch (getState()) {
                case STARTUP:
                    imuReset.low();
                    goToState(DISABLED, 10);
                    break;

                case ERROR:
                    goToState(DISABLED, ERROR_RESET_DELAY);
                    break;

                case DISABLED:
                    if (requestedActive) {
                        imuReset.high();
                        goToState(ACTIVATING_1, 10);
                    } else {
                        imuReset.low();
                        goToState(DISABLED, 1e5);
                    }
                    break;

                case ACTIVATING_1:
                    if (gyro.begin()) {
                        goToState(ACTIVATING_2);
                    } else {
                        Serial.println("Gyro begin failed. Will retry.");
                        goToState(ACTIVATING_1, 5e6);
                    }
                    break;

                case ACTIVATING_2:
                    if (accelmag.begin(ACCEL_RANGE_2G)) {
                        // start the AHRS filter, then give it time to settle
                        filter.begin(100);
                        goToState(SETTLING);
                    } else {
                        Serial.println("Accel/Mag begin failed. Will retry.");
                        goToState(ACTIVATING_2, 5e6);
                    }
                    break;

                case SETTLING:
                    updateFilter();
                    if (getTimeInState() >= SETTLING_DELAY) {
                        goToState(RUNNING);
                    }
                    break;

                case RUNNING:
                    if (!requestedActive) {
                        goToState(DEACTIVATING);
                    } else {
                        updateFilter();
                        goToState(RUNNING, 1e4);    // 10ms period for 100Hz IMU updates
                    }
                    break;
                    
                case DEACTIVATING:
                    goToState(DISABLED);
                    break;

                default:
                    Serial.println("Unexpected state encountered!");
                    goToState(ERROR);
            }

            return false;
        }

        void AHRS::updateFilter() {
            sensors_event_t gyro_event;
            sensors_event_t accel_event;
            sensors_event_t mag_event;
        
            // Get new data samples
            gyro.getEvent(&gyro_event);
            accelmag.getEvent(&accel_event, &mag_event);
        
            // Apply mag offset compensation (base values in uTesla)
            float x = mag_event.magnetic.x - mag_offsets[0];
            float y = mag_event.magnetic.y - mag_offsets[1];
            float z = mag_event.magnetic.z - mag_offsets[2];
        
            // Apply mag soft iron error compensation
            float mx = x * mag_softiron_matrix[0][0] + y * mag_softiron_matrix[0][1] + z * mag_softiron_matrix[0][2];
            float my = x * mag_softiron_matrix[1][0] + y * mag_softiron_matrix[1][1] + z * mag_softiron_matrix[1][2];
            float mz = x * mag_softiron_matrix[2][0] + y * mag_softiron_matrix[2][1] + z * mag_softiron_matrix[2][2];
        
            // Apply gyro zero-rate error compensation
            float gx = gyro_event.gyro.x + gyro_zero_offsets[0];
            float gy = gyro_event.gyro.y + gyro_zero_offsets[1];
            float gz = gyro_event.gyro.z + gyro_zero_offsets[2];
        
            // The filter library expects gyro data in degrees/s, but adafruit sensor
            // uses rad/s so we need to convert them first (or adapt the filter lib
            // where they are being converted)
            gx *= DEG_PER_RAD;
            gy *= DEG_PER_RAD;
            gz *= DEG_PER_RAD;
        
            // Update the filter
            filter.update(gx, gy, gz,
                        accel_event.acceleration.x, accel_event.acceleration.y, accel_event.acceleration.z,
                        mx, my, mz);
            roll = filter.getRoll();
            pitch = filter.getPitch();
            heading = filter.getYaw();
        }

        const char* AHRS::getStateName(const State aState) const {
            switch (aState) {
                case STARTUP:
                    return "STARTUP";
                case ERROR:
                    return "ERROR";
                case DISABLED:
                    return "DISABLED";
                case ACTIVATING_1:
                    return "ACTIVATING_1";
                case ACTIVATING_2:
                    return "ACTIVATING_2";
                case SETTLING:
                    return "SETTLING";
                case RUNNING:
                    return "RUNNING";
                case DEACTIVATING:
                    return "DEACTIVATING";

                default:
                    return "<INVALID>";
            }
        }

        float AHRS::getHeading() const {
            return heading;
        }
 
        String AHRS::getLogString() const {

            String logStr(getState());
            logStr.concat(",");
            if (getState() == Roboat::IMU::State::RUNNING) {
              logStr.concat(getHeading());
            } else {
              logStr.concat("-");
            }
            return logStr;
        }
    }
}