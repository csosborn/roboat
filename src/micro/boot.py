# Runs before main.py on every reset. It must stay trivial: if anything here
# raised, the Pi's power state would be left to chance.
from machine import Pin

# Hold the Pi's power relay on. The hardware pull-up already does this while
# the RP2040 is in reset; driving it keeps it on through main.py's startup.
Pin(11, Pin.OUT, value=1)
