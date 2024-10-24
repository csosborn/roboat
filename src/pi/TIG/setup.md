

sudo apt remove rpi-connect

sudo apt install docker.io docker-compose

sudo useradd telegraf

sudo usermod -a -G docker csosborn
sudo usermod -a -G docker telegraf

sudo chmod 666 /var/run/docker.sock


