from ulab import numpy as np
import time

class LFPSoCEstimator:
    def __init__(self, capacity_ah=20.0, initial_soc=1.0):
        self.capacity_ah = capacity_ah  # Nominal battery capacity (Ah)
        self.soc = initial_soc  # Initial state of charge (0 to 1)
        self.last_update_time = None  # Track last timestamp
        
        self.voltage_table = {
            12.1: 0.0, 13.3: 0.1, 13.6: 0.5, 13.95: 0.9, 14.6: 1.0
        }
        
        self.Q_error = 0.001  # Process noise covariance (for Kalman filter)
        self.R_error = 0.005  # Measurement noise covariance (for Kalman filter)
        self.P = 1.0  # Estimation uncertainty (for Kalman filter)
        self.internal_resistance = 0.02  # Initial estimated internal resistance (Ohms)
        self.temp_coefficient = 0.0005  # Initial temperature coefficient for resistance
        self.resistance_temp_history = []  # Store (temperature, resistance) pairs
    
    def coulomb_counting(self, current, dt):
        """ Update SoC using Coulomb counting with a dynamic time step. """
        if dt <= 0:
            return  # Prevent division by zero
        delta_soc = (current * dt / 3600) / self.capacity_ah  # Convert seconds to hours
        #print(f"Delta soc: {delta_soc}")
        self.soc = max(0, min(1, self.soc + delta_soc))  # Keep within [0,1]
    
    def voltage_based_estimation(self, voltage):
        """ Estimate SoC from voltage using interpolation. """
        voltages = np.array(list(self.voltage_table.keys()))
        soc_values = np.array(list(self.voltage_table.values()))
        return np.interp(voltage, voltages, soc_values)
    
    def kalman_filter(self, measured_soc):
        """ Apply a simple Kalman filter to correct SoC estimation. """
        K_gain = self.P / (self.P + self.R_error)
        self.soc += K_gain * (measured_soc - self.soc)
        self.P = (1 - K_gain) * self.P + self.Q_error
        print(f"K_gain: {K_gain}  measured_soc: {measured_soc}  soc: {self.soc}  P: {self.P}  R_error: {self.R_error}")
        self.soc = max(0, min(1, self.soc[0]))  # Keep within bounds
    
    def update_internal_resistance(self, voltage, current, temperature):
        """ Update internal resistance based on voltage drop and temperature. """
        if abs(current) > 0.5:  # Only update if significant current is flowing
            estimated_r = abs(voltage / current)  # Approximate internal resistance
            self.internal_resistance = 0.95 * self.internal_resistance + 0.05 * estimated_r  # EWMA filter
        
        self.resistance_temp_history.append((temperature, self.internal_resistance))
        if len(self.resistance_temp_history) > 50:  # Keep history manageable
            self.resistance_temp_history.pop(0)
        
        if len(self.resistance_temp_history) > 5:
            temps, resistances = zip(*self.resistance_temp_history)
            temp_diffs = np.array(temps) - 25
            resistance_diffs = np.array(resistances) - self.internal_resistance
            if np.std(temp_diffs) > 0:  # Avoid division by zero
                self.temp_coefficient = np.cov(temp_diffs, resistance_diffs)[0, 1] / np.var(temp_diffs)
    
    def update(self, voltage, current, temperature, timestamp=None):
        """ Main update function: integrates Coulomb counting and voltage correction with dynamic dt handling. """
        if timestamp is None:
            timestamp = time.time()
        
        if self.last_update_time is None:
            self.last_update_time = timestamp  # Initialize first time
            return self.soc
        
        dt = timestamp - self.last_update_time  # Compute time difference
        self.last_update_time = timestamp
        
        self.coulomb_counting(current, dt)
        self.update_internal_resistance(voltage, current, temperature)
        estimated_soc_from_voltage = self.voltage_based_estimation(voltage)
        if abs(current) < 0.1:  # Only correct when battery is at rest
            self.kalman_filter(estimated_soc_from_voltage)
        return self.soc

# Example usage
if __name__ == "__main__":
    estimator = LFPSoCEstimator()
    test_data = [  # Simulated (voltage, current, temperature, timestamp) readings
        (13.2, -2.0, 25.0, 0), (13.1, -1.5, 26.0, 1), (12.9, -3.0, 27.0, 2),
        (12.7, -1.0, 28.0, 3), (12.6, 0.0, 25.0, 4), (12.4, 2.0, 24.0, 5)
    ]
    
    start_time = time.time()
    for voltage, current, temperature, seconds in test_data:
        timestamp = start_time + seconds
        soc = estimator.update(voltage, current, temperature, timestamp)
        print(f"Voltage: {voltage:.2f}V, Current: {current:.2f}A, Temperature: {temperature:.1f}°C, Estimated SoC: {soc:.2%}, Temp Coeff: {estimator.temp_coefficient:.6f}")

