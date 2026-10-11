
## Cleanup

```
sudo apt remove rpi-connect
```

## Installations

``` 
sudo apt-get update

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

Enable UART3, which has TX pin 7, RX pin 29 (see [here](https://raspberrypi.stackexchange.com/questions/45570/how-do-i-make-serial-work-on-the-raspberry-pi3-pizerow-pi4-or-later-models/107780#107780))

In /boot/firmware/config.txt:
```
[all]
enable_uart=1
dtoverlay=uart3
```

## Configure Secrets

Credentials live in `*.env` files in this directory, which are gitignored. Create each one from its template and fill in real values:

```
cp telegraf.env.example telegraf.env
cp influxdb.env.example influxdb.env
cp grafana.env.example grafana.env
cp ../monitor/monitor.env.example ../monitor/monitor.env
```

Telegraf and the monitor service use separate InfluxDB tokens. Telegraf's (in `telegraf.env`) writes the `compute` bucket. The monitor's (in `src/pi/monitor/monitor.env`, loaded by `roboat-monitor.service`) writes the `roboat_01` bucket.