
## Cleanup

```
sudo apt remove rpi-connect
```

## Installations

``` 
sudo apt-get update
sudo apt install gpsd

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