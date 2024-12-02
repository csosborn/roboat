from pysm import State, StateMachine, Event
from machine import Timer

WAKE = 'wake'
MAIN_POWER_UP = 'main_power_up'
MAIN_POWER_DOWN = 'main_power_down'
ENERGY_OK = 'energy_ok'
ENERGY_LOW = 'energy_low'
START_PI = 'start_pi'
PI_HEARTBEAT = 'pi_hb'
PI_HEARTBEAT_TO = 'pi_hb_to'
STOP_PI = 'stop_pi'
PI_STOPPED = 'pi_stopped'


class RoboatSM():

    def __init__(self):
        self.sm = self._get_state_machine()
        #    self.timer = threading.Timer(Oven.TIMEOUT, self.on_timeout)

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

        sm.add_transition(init_s, no_main_power_sm, events=[WAKE])
        sm.add_transition(no_main_power_sm, main_power_sm, events=[MAIN_POWER_UP])
        sm.add_transition(main_power_sm, no_main_power_sm, events=[MAIN_POWER_DOWN])
        main_power_sm.add_transition(await_power_s, pi_off_s, events=[ENERGY_OK])
        main_power_sm.add_transition(pi_off_s, await_power_s, events=[ENERGY_LOW])
        main_power_sm.add_transition(pi_off_s, no_pi_comms_s, events=[START_PI], action=self.start_pi)
        main_power_sm.add_transition(no_pi_comms_s, pi_alive_s, events=[PI_HEARTBEAT])
        main_power_sm.add_transition(pi_alive_s, no_pi_comms_s, events=[PI_HEARTBEAT_TO])
        main_power_sm.add_transition(pi_alive_s, pi_stopping_s, events=[STOP_PI], action=self.stop_pi)
        main_power_sm.add_transition(pi_stopping_s, pi_off_s, events=[PI_STOPPED], action=self.cut_pi_power)
            
        # Attach enter/exit handlers
        states = [sm, no_main_power_sm, main_power_sm, init_s, monitor_s,
                  await_power_s, no_pi_comms_s, pi_alive_s, pi_stopping_s, pi_off_s]
        for state in states:
            state.handlers = {'enter': self.on_enter, 'exit': self.on_exit}

        sm.initialize()
        return sm

    @property
    def state(self):
        return self.sm.leaf_state.name
    
    def start_pi(self, state, event):
        print("Enabling power to RPi.")

    def stop_pi(self, state, event):
        print("Signaling RPi to shut down.")
        Timer(period=30000, mode=Timer.ONE_SHOT, callback=lambda t: self.dispatch(PI_STOPPED))

    def cut_pi_power(self, state, event):
        print("Cutting power to RPi.")

    def on_enter(self, state, event):
        print('enter state {0}'.format(state.name))
        
    def on_exit(self, state, event):
        pass
        #     print('exit state {0}'.format(state.name))

    def dispatch(self, event_name):
        self.sm.dispatch(Event(event_name))

