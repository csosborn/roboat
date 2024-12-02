from roboat_fsm import *


roboat = RoboatSM()

assert roboat.state == "Init"
roboat.dispatch(WAKE)
assert roboat.state == "Monitor"
roboat.dispatch(MAIN_POWER_UP)
assert roboat.state == "AwaitPower"
roboat.dispatch(ENERGY_OK)
assert roboat.state == "PiOff"
roboat.dispatch(START_PI)
assert roboat.state == "NoPiComms"
roboat.dispatch(PI_HEARTBEAT)
assert roboat.state == "PiAlive"
roboat.dispatch(PI_HEARTBEAT_TO)
assert roboat.state == "NoPiComms"
roboat.dispatch(PI_HEARTBEAT)
assert roboat.state == "PiAlive"
roboat.dispatch(STOP_PI)
assert roboat.state == "PiStopping"
roboat.dispatch(PI_STOPPED)
assert roboat.state == "PiOff"
roboat.dispatch(MAIN_POWER_DOWN)
assert roboat.state == "Monitor"



