import time

INTERVAL_SAMPLES = 10

def locate_interpolation(source_curve, value, dest_curve):
    # todo: use ulab instead of this hand-coded array nonsense
    if value <= source_curve[0]:
        return dest_curve[0]
    for i in range(len(source_curve)-1):
        if value >= source_curve[i] and value <= source_curve[i+1]:
            proportion = (value - source_curve[i]) / (source_curve[i+1] - source_curve[i])
            interpolant = dest_curve[i] + proportion * (dest_curve[i+1] - dest_curve[i])
            return interpolant
    return dest_curve[-1]

class BatteryModel():

    def __init__(self, nominal_v, nominal_ah):
        self.nom_v_ = nominal_v
        self.nom_ah_ = nominal_ah

        # Capacity estimate bracket, in C
        self.capacity_est_ = self.nom_ah_ * 3600 * 0.5
        self.cap_est_min_ = 0
        self.cap_est_max_ = self.nom_ah_ * 3600

        self.last_ticks_ = None
        self.last_i_ = None

        self.curve_soc_ = [0.0, 0.1, 0.5, 0.9, 1.0]
        self.curve_charge_v_ = [12.1, 13.3, 13.6, 13.95, 14.6]
        self.curve_discharge_v_ = [0.0, 12.19, 12.56, 12.74, 13.7]

        self.cap_delta_sum_ = 0.0
        self.cap_delta_samples_ = 0

    def update(self, now_ms, voltage, current):
        made_change = False
        if self.last_ticks_ is None:
            soc_estimate = self.estimate_soc(voltage, current)
            if soc_estimate < 0:
                return
    
            self.capacity_est_ = self.nom_ah_ * 3600 * soc_estimate
            print("initial soc estimate: {}, cap estimate: {}C".format(soc_estimate, self.capacity_est_))
            made_change = True

        else:
            interval_i = (self.last_i_ + current) / 2.0  # avg current in A
            interval_t = now_ms - self.last_ticks_   # time interval in ms
            interval_c = interval_i * interval_t  # interval charge in mC

            self.cap_delta_sum_ += interval_c
            self.cap_delta_samples_ += 1
                        
            print("interval i: {}A  interval c: {}mC  interval t: {}ms".format(interval_i, interval_c, interval_t))
            print("sum {}mC for {} samples".format(self.cap_delta_sum_, self.cap_delta_samples_))
            
            if self.cap_delta_samples_ >= INTERVAL_SAMPLES:
                self.dump_subsamples_()
                print("cap estimate: {} ({}Ah)".format(self.capacity_est_, self.capacity_est_/3600))
                made_change = True

        self.last_ticks_ = now_ms
        self.last_i_ = current

        return made_change


    def dump_subsamples_(self):
        additional_ah = (self.cap_delta_sum_ / 1000.0)
        self.capacity_est_ += additional_ah
        self.cap_est_min_ += additional_ah
        self.cap_est_max_ += additional_ah

        self.capacity_est_ = min(self.capacity_est_, self.nom_ah_ * 3600)
        self.cap_est_max_ = min(self.cap_est_max_, self.nom_ah_ * 3600)
        self.cap_est_min_ = min(self.cap_est_min_, self.capacity_est_)

        self.capacity_est_ = max(self.capacity_est_, 0)
        self.cap_est_max_ = max(self.cap_est_max_, self.capacity_est_)
        self.cap_est_min_ = max(self.cap_est_min_, 0)

        self.cap_delta_sum_ = 0.0
        self.cap_delta_samples_ = 0


    def estimate_soc(self, voltage, current):
        if current > 0:
            # use charge curve
            return locate_interpolation(self.curve_charge_v_, voltage, self.curve_soc_)
        else:
            # use discharge curve
            return locate_interpolation(self.curve_discharge_v_, voltage, self.curve_soc_)


