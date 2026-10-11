from pysm import State, StateMachine, Event

MAIN_POWER_UP = 'main_power_up'
MAIN_POWER_DOWN = 'main_power_down'
ENERGY_OK = 'energy_ok'
ENERGY_LOW = 'energy_low'
START_PI = 'start_pi'
PI_ALREADY_ON = 'pi_already_on'
PI_HEARTBEAT = 'pi_hb'
PI_HEARTBEAT_TO = 'pi_hb_to'
STOP_PI = 'stop_pi'
PI_STOPPED = 'pi_stopped'
START_DRIVE = 'start_drive'

PI_SHUTDOWN_WAIT_MS = 30000
ESC_ARM_DELAY_MS = 7000


class RoboatSM():
    """Power-management state machine.

    The Pi's power is only ever changed deliberately, and each change is passed
    to record_pi_power(on) so boot.py can restore it after a watchdog reset.
    The FSM never touches the relay at startup; boot.py has already set it.

    schedule(delay_ms, fn) must call fn later from the main loop, never from an
    interrupt, so that dispatches can't nest.
    """

    def __init__(self, neopixel, pi_power_pin, drive_power_pin, drive_pwm,
                 schedule, on_pi_power_on=None, record_pi_power=None):
        self.neopixel_ = neopixel
        self.pi_power_ = pi_power_pin
        self.drive_power_ = drive_power_pin
        self.drive_pwm_ = drive_pwm
        self.schedule_ = schedule
        self.on_pi_power_on_ = on_pi_power_on
        self.record_pi_power_ = record_pi_power
        self.sm = self._get_state_machine()
        self.drive_power_.off()
        self._set_led(2, 2, 2)

    def _get_state_machine(self):

        sm = StateMachine('roboat')

        # Main substates
        init_s = State('Init')
        no_main_power_sm = StateMachine('NoMainPower')
        main_power_sm = StateMachine('MainPower')

        sm.add_state(init_s, initial=True)
        sm.add_state(no_main_power_sm)
        sm.add_state(main_power_sm)

        # NoMainPower substates
        monitor_s = State('Monitor')
        no_main_power_sm.add_state(monitor_s, initial=True)

        # MainPower substates
        await_power_s = State('AwaitPower')
        no_pi_comms_s = State('NoPiComms')
        pi_alive_s = State('PiAlive')
        pi_stopping_s = State('PiStopping')
        pi_off_s = State('PiOff')

        main_power_sm.add_state(await_power_s, initial=True)
        main_power_sm.add_state(no_pi_comms_s)
        main_power_sm.add_state(pi_alive_s)
        main_power_sm.add_state(pi_stopping_s)
        main_power_sm.add_state(pi_off_s)

        # Init waits for the first real power reading before deciding anything.
        sm.add_transition(init_s, main_power_sm, events=[MAIN_POWER_UP])
        sm.add_transition(init_s, no_main_power_sm, events=[MAIN_POWER_DOWN])
        sm.add_transition(no_main_power_sm, main_power_sm, events=[MAIN_POWER_UP])
        sm.add_transition(main_power_sm, no_main_power_sm, events=[MAIN_POWER_DOWN])
        main_power_sm.add_transition(await_power_s, pi_off_s, events=[ENERGY_OK])
        main_power_sm.add_transition(await_power_s, no_pi_comms_s, events=[PI_ALREADY_ON])
        main_power_sm.add_transition(pi_off_s, await_power_s, events=[ENERGY_LOW])
        main_power_sm.add_transition(pi_off_s, no_pi_comms_s, events=[START_PI], action=self.start_pi)
        main_power_sm.add_transition(no_pi_comms_s, pi_alive_s, events=[PI_HEARTBEAT])
        main_power_sm.add_transition(pi_alive_s, no_pi_comms_s, events=[PI_HEARTBEAT_TO])
        main_power_sm.add_transition(pi_alive_s, pi_stopping_s, events=[STOP_PI], action=self.stop_pi)
        main_power_sm.add_transition(no_pi_comms_s, None, events=[START_DRIVE], action=self.start_drive)
        main_power_sm.add_transition(pi_stopping_s, pi_off_s, events=[PI_STOPPED], action=self.cut_pi_power)

        # Attach enter/exit handlers
        states = [sm, no_main_power_sm, main_power_sm, init_s, monitor_s,
                  await_power_s, no_pi_comms_s, pi_alive_s, pi_stopping_s, pi_off_s]
        for state in states:
            state.handlers = {'enter': self.on_enter, 'exit': self.on_exit}
        no_main_power_sm.handlers['enter'] = self.enter_no_main_power
        main_power_sm.handlers['enter'] = self.enter_main_power
        pi_off_s.handlers['enter'] = self.enter_pi_off

        sm.initialize()
        return sm

    @property
    def state(self):
        return self.sm.leaf_state.name

    def _set_pi_power(self, on):
        if on:
            self.pi_power_.on()
        else:
            self.pi_power_.off()
        if self.record_pi_power_ is not None:
            self.record_pi_power_(on)

    def _set_led(self, r, g, b):
        self.neopixel_[0] = (r, g, b)
        self.neopixel_.write()

    def enter_main_power(self, state, event):
        print('enter state {0}'.format(state.name))
        self._set_led(0, 0, 2)

    def enter_no_main_power(self, state, event):
        print('enter state {0}'.format(state.name))
        self._set_led(2, 0, 0)
        self._set_pi_power(False)
        self.drive_power_.off()

    def enter_pi_off(self, state, event):
        print('enter state {0}'.format(state.name))
        self._set_led(0, 2, 1)

    def start_pi(self, state, event):
        print("Enabling power to RPi.")
        was_on = self.pi_power_.value()
        self._set_pi_power(True)
        if not was_on and self.on_pi_power_on_ is not None:
            self.on_pi_power_on_()

    def start_drive(self, state, event):
        print("Enabling power to Drive.")
        self.drive_power_.on()
        self.schedule_(ESC_ARM_DELAY_MS, self.init_esc)

    def init_esc(self):
        print("Arming drive ESC")
        self.drive_pwm_.duty_ns(1500000)
        print("Drive ESC duty cycle now {}ns.".format(self.drive_pwm_.duty_ns()))

    def stop_pi(self, state, event):
        print("Signaling RPi to shut down.")
        self.schedule_(PI_SHUTDOWN_WAIT_MS, lambda: self.dispatch(PI_STOPPED))

    def cut_pi_power(self, state, event):
        print("Cutting power to RPi.")
        self._set_pi_power(False)

    def on_enter(self, state, event):
        print('enter state {0}'.format(state.name))

    def on_exit(self, state, event):
        pass

    def dispatch(self, event_name):
        self.sm.dispatch(Event(event_name))
        # AwaitPower means "not enough energy to start the Pi". If the Pi is
        # already running (e.g. after an RP2040 reset), it's left running and
        # the state moves on to reflect that.
        if self.state == 'AwaitPower' and self.pi_power_.value():
            self.sm.dispatch(Event(PI_ALREADY_ON))
