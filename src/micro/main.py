# The entry point MicroPython runs at boot. The firmware itself is app.py.
#
# If the firmware fails before it's up and running (a broken import, say),
# this reports the failure to the Pi and moves the REPL onto the Pi link's
# UART, so a deploy over the serial link can repair it without a USB cable.
# Failures once it's running are handled in app.py: crash log, reset, and
# after repeated crashes, safe mode.
try:
    import app
except Exception as e:
    import sys
    sys.print_exception(e)
    try:
        import json
        import os
        from machine import Pin, UART
        uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1), rxbuf=4096, txbuf=1024)
        uart.write(json.dumps({"offset_s": 0, "src": "status", "event": "startup_failed",
                               "error": repr(e)}) + "\r\n")
        try:
            import supervisor
            supervisor.record_crash(e, 0)
        except Exception:
            pass
        os.dupterm(uart)
    except Exception:
        pass
