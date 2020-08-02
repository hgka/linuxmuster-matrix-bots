# linuxmuster-matrix-bots
Bots for a Matrix-installation connected to linuxmuster.net

## System requirements

* Linux using python3.6+
* tested only with Ubuntu 18.04 

## Installation

```
sudo apt-get install python3-venv
cd /opt
git clone https://github.com/hgka/linuxmuster-matrix-bots.git
cd /opt/linuxmuster-matrix-bots
./setup.sh
```

## Configuration

Copy config.example.ini to config.ini and edit all configuration
variable to match the one in your system.

- Create a bot user on the matrix-synapse server like this:
```
matrix-synapse-register-user enrol-bot Geheim 0
matrix-synapse-register-user kick-bot Geheim 0
```
then your config.ini becomes
```
[bot]
id = @enrol-bot:my-domain.org
passwd = Geheim
```
use config.example.ini as a template

## Run manually

```
cd /opt/linuxmuster-matrix-bots
source matrix-nio-env/bin/activate
./linuxmuster-enrol-classes-bot.py
...
deactivate
```

You can stop using CTRL-C.

## Run as a service

Edit linuxmuster-matrix-*bot.service to your needs (or leave unchanged
if you used the described folder location above) then copy to systemd
and enable and start it:

```
cp linuxmuster-matrix-enrol-bot.service /etc/systemd/system/
systemctl enable linuxmuster-matrix-enrol-bot
systemctl start linuxmuster-matrix-enrol-bot
...
```
