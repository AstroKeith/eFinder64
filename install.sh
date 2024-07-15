#!/bin/sh

echo "eFinder install"
echo "This will take some time! ( > 30 minutes)"
echo " "
echo "*****************************************************************************"
echo "Updating Pi OS & packages"
echo "*****************************************************************************"
sudo apt update
sudo apt upgrade -y
echo " "
echo "*****************************************************************************"
echo "Installing additional Debian and Python packages"
echo "*****************************************************************************"
sudo apt install -y python3-pil.imagetk
sudo apt install -y imagemagick

HOME=/home/efinder
echo " "
echo "*****************************************************************************"
echo "Installing new astrometry packages"
echo "*****************************************************************************"
sudo apt-get install -y libcairo2-dev libnetpbm11-dev netpbm libpng-dev libjpeg-dev zlib1g-dev libbz2-dev swig libcfitsio-dev
sudo apt install -y python3-fitsio
sudo apt install -y python3-skyfield
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

python -m venv /home/efinder/venv-efinder --system-site-packages
venv-efinder/bin/python venv-efinder/bin/pip install astropy pyfits
mkdir /home/efinder/Solver
mkdir /home/efinder/Solver/Stills
mkdir /home/efinder/Solver/data
mkdir /home/efinder/Solver/images

echo " "
echo "*****************************************************************************"
echo "Downloading Tetra databases"
echo "*****************************************************************************"
venv-efinder/bin/python venv-efinder/bin/pip install gdown
venv-efinder/bin/gdown  --output /home/efinder/Solver/data --folder https://drive.google.com/drive/folders/1uxbdttpg0Dpp8OuYUDY9arYoeglfZzcX
venv-efinder/bin/python venv-efinder/bin/pip install git+https://github.com/esa/tetra3.git
cd /home/efinder/venv-efinder/lib/python3.11/site-packages/tetra3
sudo wget https://cdsarc.u-strasbg.fr/ftp/cats/I/239/hip_main.dat



cd $HOME

sudo -u efinder git clone https://github.com/AstroKeith/eFinder64.git

cd eFinder64

tar xf ASI_linux_mac_SDK_V1.31.tar.bz2
cd ASI_linux_mac_SDK_V1.31/lib

sudo mkdir /lib/zwoasi
sudo mkdir /lib/zwoasi/armv8
sudo cp armv8/*.* /lib/zwoasi/armv8
sudo install asi.rules /lib/udev/rules.d

cd $HOME

venv-efinder/bin/python venv-efinder/bin/pip install zwoasi

cd $HOME

echo "tmpfs /var/tmp tmpfs nodev,nosuid,size=100M 0 0" | sudo tee -a /etc/fstab > /dev/null


sudo apt install -y samba samba-common-bin
sudo tee -a /etc/samba/smb.conf > /dev/null <<EOT
[efindershare]
path = /home/efinder
writeable=Yes
create mask=0777
directory mask=0777
public=no
EOT
username="efinder"
pass="efinder"
(echo $pass; sleep 1; echo $pass) | sudo smbpasswd -a -s $username
sudo systemctl restart smbd

echo ""
cp /home/efinder/eFinder64/Solver/*.* /home/efinder/Solver
cp /home/efinder/eFinder64/Solver/de421.bsp /home/efinder
cp /home/efinder/eFinder_Lite/Solver/starnames.csv /home/efinder/Solver/data
cp /home/efinder/eFinder_Lite/Solver/generate_database.py /home/venv-efinder/lib/python3.11/site-packages/tetra3

mkdir /home/efinder/.config/autostart
cp /home/efinder/eFinder64/efinder.desktop /home/efinder/.config/autostart

sudo raspi-config nonint do_vnc 0
sudo raspi-config nonint do_hostname efinder
sudo raspi-config nonint do_blanking 1
sudo raspi-config nonint do_ssh 0
sudo raspi-config nonint do_serial_hw 0
sudo raspi-config nonint do_serial_cons 1
sudo raspi-config nonint do_vnc_resolution 1920x1080

echo "after the reboot vnc and ssh should be available at 'efinder.local'"
