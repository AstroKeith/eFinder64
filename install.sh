#!/bin/sh

echo "eFinder install"
echo "This will take some time! ( > 30 minutes)"
echo " "
echo "*****************************************************************************"
sudo rpi-update -y

sudo apt update
sudo apt upgrade -y

HOME=/home/efinder

sudo apt-get install -y libcairo2-dev libnetpbm11-dev netpbm libpng-dev libjpeg-dev zlib1g-dev libbz2-dev swig libcfitsio-dev
# sudo -u efinder python3 -m pip install --upgrade pip

sudo apt install python3-fitsio
sudo apt install -y imagemagick
sudo apt install -y python3-skyfield
sudo apt install python3-pil.imagetk

python -m venv /home/efinder/venv-efinder --system-site-packages
venv-efinder/bin/python venv-efinder/bin/pip install astropy pyfits

cd $HOME
sudo -u efinder git clone https://github.com/dstndstn/astrometry.net.git
echo ""


cd $HOME/astrometry.net
make
make py
make extra
sudo make install

sudo sh -c "echo export PATH=$PATH:/usr/local/astrometry/bin >> /etc/profile"

cd /usr/local/astrometry/data
sudo wget http://data.astrometry.net/4100/index-4107.fits
sudo wget http://data.astrometry.net/4100/index-4108.fits
sudo wget http://data.astrometry.net/4100/index-4109.fits
sudo wget http://data.astrometry.net/4100/index-4110.fits
sudo wget http://data.astrometry.net/4100/index-4111.fits

sudo mkdir /usr/local/astrometry/annotate_data
cd /usr/local/astrometry/annotate_data
sudo wget http://data.astrometry.net/hd.fits
sudo wget http://data.astrometry.net/hip.fits
sudo wget https://github.com/dstndstn/astrometry.net/tree/main/catalogs/abell-all.fits

cd $HOME

sudo -u efinder git clone https://github.com/AstroKeith/eFinder64.git

cd eFinder64
tar xf ASI_linux_mac_SDK_V1.31.tar.bz2
cp /home/efinder/Solver/de421.bsp /home/efinder
cd ASI_linux_mac_SDK_V1.31/lib

sudo mkdir /lib/zwoasi
sudo mkdir /lib/zwoasi/armv8
sudo cp armv8/*.* /lib/zwoasi/armv8
sudo install asi.rules /lib/udev/rules.d

cd $HOME

venv-efinder/bin/python venv-efinder/bin/pip install zwoasi

cd $HOME

echo "tmpfs /var/tmp tmpfs nodev,nosuid,size=100M 0 0" | sudo tee -a /etc/fstab > /dev/null


mkdir /home/efinder/Solver
mkdir /home/efinder/Solver/Stills

echo ""
cp /home/efinder/eFinder64/Solver/*.* /home/efinder/Solver
cp /home/efinder/eFinder64/Solver/de421.bsp /home/efinder

mkdir /home/efinder/.config/autostart
cp /home/efinder/eFinder64/efinder.desktop /home/efinder/.config/autostart

sudo raspi-config nonint do_wayland W1
sudo raspi-config nonint do_hostname efinder
sudo raspi-config nonint do_blanking 1
sudo raspi-config nonint do_ssh 0
sudo raspi-config nonint do_serial_hw 0
sudo raspi-config nonint do_serial_cons 1
sudo raspi-config nonint do_vnc_resolution 1920x1080

echo "after the reboot vnc and ssh should be available at 'efinder.local'"
