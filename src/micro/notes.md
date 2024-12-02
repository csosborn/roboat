

```
drive_power = Pin(7, Pin.OUT)
drive_power.on()  # power up the ESC

servo = PWM(Pin(8), freq=50)
servo.duty_ns(1500000)  # arm servo, zero power
servo.duty_ns(1000000)  # full forward
servo.duty_ns(2000000)  # full reverse

drive_power.off()  # power down the ESC
```

The ESC will pull a sharp current pulse when adjusting to a large change in setpoint. To avoid this, use gradual ramps. Sudden changes aren't required for boat propulsion anyway.