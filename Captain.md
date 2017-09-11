
# Roboat Captain Module

## Hardware: Raspberry Pi Zero W

### Notes

The Pi can be in a halted state most of the time if necessary, and be woken by the pilot as necessary by pulling GPIO pin 5 (GPIO03) low. _Tested, works well._

Consider powering the Pi via a [3.3v buck converter with enable](https://www.adafruit.com/product/2745), both to provide better power efficiency and to let it be powered down completely (or hard reset if need be). _Not yet tested._

Turning off HDMI upon bootup can save something like ~30mA. Add `/usr/bin/tvservice -o` to the `/etc/rc.local` file.



### Bootstrap

```
# install Teensy loader CLI
sudo apt-get install libusb-dev
git clone https://github.com/PaulStoffregen/teensy_loader_cli.git
cd teensy_loader_cli
make


wget https://www.arduino.cc/download_handler.php?f=/arduino-1.8.4-linuxarm.tar.xz
tar -xf arduino-1.8.4-linuxarm.tar.xz

# install Teensyduino for Linux ARM6
https://www.pjrc.com/teensy/td_139/TeensyduinoInstall.linuxarm
sudo apt-get install -y libxext6 libfontconfig1 libxft2
```


### Programming Teensy from the Pi

```

teensy_loader_cli --mcu=mk66fx1m0 -w program.hex


```