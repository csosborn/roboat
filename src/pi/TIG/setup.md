
## Cleanup

```
sudo apt remove rpi-connect
```

## Installations

``` 
sudo apt-get update
sudo apt install chrony   # replaces systemd-timesyncd; see src/pi/etc/chrony

curl -fsSL https://tailscale.com/install.sh | sh

```



## Configure Users and Groups

```
sudo apt install docker.io docker-compose
sudo useradd telegraf
sudo usermod -a -G docker csosborn
sudo usermod -a -G docker telegraf
sudo chmod 666 /var/run/docker.sock
```

## Configure Hardware

The RP2040 link uses the Pi's UART4: TX on header pin 24 (GPIO8), RX on pin 21 (GPIO9), at 115200 baud, as `/dev/ttyAMA4`. It's a full PL011 UART, and unlike UART0 it isn't shared with Bluetooth or the serial console. Pins 21 and 24 are the Pi's SPI0, which must stay off (no `dtparam=spi=on`). See [here](https://raspberrypi.stackexchange.com/questions/45570/how-do-i-make-serial-work-on-the-raspberry-pi3-pizerow-pi4-or-later-models/107780#107780).

In /boot/firmware/config.txt:
```
[all]
dtoverlay=uart4
```

UART0 (pins 8 and 10) was tried first, on 2026-11-16, but roboat1's GPIO15 input is damaged: it reads high whatever is on the pin. roboat1 still has `dtoverlay=disable-bt` and its serial console turned off from that test; neither is needed for UART4.

The v0.1 avionics board wires the link to UART3 instead (TX pin 7, RX pin 29). With one fitted, add `dtoverlay=uart3` and set `PI_LINK_PORT=/dev/ttyAMA3` in `src/pi/monitor/monitor.env`. Both overlays can be on at once.

## Configure Secrets

Credentials live in `*.env` files in this directory, which are gitignored. Create each one from its template and fill in real values:

```
cp telegraf.env.example telegraf.env
cp influxdb.env.example influxdb.env
cp grafana.env.example grafana.env
cp ../monitor/monitor.env.example ../monitor/monitor.env
```

Telegraf and the monitor service use separate InfluxDB tokens. Telegraf's (in `telegraf.env`) writes the `compute` bucket. The monitor's (in `src/pi/monitor/monitor.env`, loaded by `roboat-monitor.service`) writes the `roboat_01` bucket.